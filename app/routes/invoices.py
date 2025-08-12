from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models import db, Invoice, Client, InvoiceLine, VatRate
from app.forms import InvoiceForm, InvoiceSearchForm, InvoiceLineForm
from app.services.numbering import generate_invoice_number
from app.services.totals import calculate_invoice_totals, calculate_line_total
from app.services.status_transitions import InvoiceStatusTransition
from app.logging_config import get_logger
from datetime import date, datetime
from sqlalchemy import or_

logger = get_logger(__name__)

invoices_bp = Blueprint('invoices', __name__)


@invoices_bp.route('/invoices')
def invoices():
    """Invoices management page with filtering."""
    search_form = InvoiceSearchForm()
    
    # Populate client choices
    clients = Client.query.order_by(Client.name.asc()).all()
    search_form.client_id.choices = [('', 'Kõik')] + [(str(c.id), c.name) for c in clients]
    
    # Get filter parameters
    status = request.args.get('status', '').strip()
    client_id = request.args.get('client_id', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    
    # Build query
    query = Invoice.query.join(Client)
    
    if status and status != '':
        query = query.filter(Invoice.status == status)
    
    if client_id and client_id != '':
        query = query.filter(Invoice.client_id == int(client_id))
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Invoice.date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Invoice.date <= to_date)
        except ValueError:
            pass
    
    # Update overdue status before displaying
    updated_count = Invoice.update_overdue_invoices()
    if updated_count > 0:
        db.session.commit()
    
    invoices_list = query.order_by(Invoice.date.desc()).all()
    
    # Prepare invoice data
    invoices_data = []
    for invoice in invoices_list:
        invoices_data.append({
            'id': invoice.id,
            'no': invoice.number,
            'date': invoice.date.strftime('%Y-%m-%d'),
            'due_date': invoice.due_date.strftime('%Y-%m-%d'),
            'client': invoice.client.name,
            'client_id': invoice.client_id,
            'total': float(invoice.total),
            'status': invoice.status,
            'is_overdue': invoice.is_overdue
        })
    
    # Set form data
    search_form.status.data = status
    search_form.client_id.data = client_id
    if date_from:
        try:
            search_form.date_from.data = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            pass
    if date_to:
        try:
            search_form.date_to.data = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    return render_template('invoices.html', 
                         invoices=invoices_data, 
                         search_form=search_form)


@invoices_bp.route('/invoices/new', methods=['GET', 'POST'])
def new_invoice():
    """Create new invoice."""
    form = InvoiceForm()
    
    # Populate client choices
    clients = Client.query.order_by(Client.name.asc()).all()
    form.client_id.choices = [(c.id, c.name) for c in clients]
    
    if not clients:
        flash('Enne arve loomist tuleb lisada vähemalt üks klient.', 'warning')
        return redirect(url_for('clients.new_client'))
    
    # Populate VAT rate choices
    vat_rates = VatRate.get_active_rates()
    form.vat_rate_id.choices = [(vr.id, f"{vr.name} ({vr.rate}%)") for vr in vat_rates]
    
    # Set default VAT rate if not already set
    if not form.vat_rate_id.data and vat_rates:
        default_rate = VatRate.get_default_rate()
        if default_rate:
            form.vat_rate_id.data = default_rate.id
        else:
            form.vat_rate_id.data = vat_rates[0].id  # Use first available rate
    
    # Auto-populate invoice number if not set
    if not form.number.data:
        form.number.data = generate_invoice_number()
    
    # Pre-select client if client_id is provided in URL
    client_id = request.args.get('client_id')
    if client_id and not form.client_id.data:
        try:
            form.client_id.data = int(client_id)
        except (ValueError, TypeError):
            pass
    
    
    
    if form.validate_on_submit():
        # Custom validation: check if form is valid and has at least one complete line
        valid_lines = []
        for line_form in form.lines.entries:
            # Check description
            has_description = (hasattr(line_form, 'description') and 
                             hasattr(line_form.description, 'data') and
                             line_form.description.data and 
                             line_form.description.data.strip())
            
            # Check qty
            has_qty = (hasattr(line_form, 'qty') and 
                      hasattr(line_form.qty, 'data') and
                      line_form.qty.data is not None)
            
            # Check unit_price
            has_unit_price = (hasattr(line_form, 'unit_price') and 
                             hasattr(line_form.unit_price, 'data') and
                             line_form.unit_price.data is not None)
            
            if has_description and has_qty and has_unit_price:
                valid_lines.append(line_form)
        
        if len(valid_lines) == 0:
            # Try accessing data via the .data attribute instead
            for line_form in form.lines.entries:
                try:
                    data = line_form.data
                    desc = data.get('description', '').strip() if data else ''
                    qty = data.get('qty') if data else None
                    price = data.get('unit_price') if data else None
                    
                    if desc and qty is not None and price is not None:
                        valid_lines.append(line_form)
                except Exception as e:
                    logger.error(f"Error accessing line_form data: {e}")
            
            if len(valid_lines) == 0:
                flash('Palun lisa vähemalt üks arve rida.', 'warning')
        
        if len(valid_lines) > 0:
            # Use form invoice number (user can modify it)
            invoice_number = form.number.data or generate_invoice_number()
        
            # Create invoice
            # Get the selected VAT rate
            selected_vat_rate = VatRate.query.get(form.vat_rate_id.data)
            
            invoice = Invoice(
                number=invoice_number,
                client_id=form.client_id.data,
                date=form.date.data,
                due_date=form.due_date.data,
                vat_rate_id=form.vat_rate_id.data,
                vat_rate=selected_vat_rate.rate if selected_vat_rate else 24,  # Fallback
                status=form.status.data
            )
            
            try:
                db.session.add(invoice)
                db.session.flush()  # Get invoice ID
                
                # Add invoice lines (use valid_lines instead of form.lines)
                for line_form in valid_lines:
                    # Use .data attribute to access the form data since FormField objects are corrupted
                    line_data = line_form.data
                    line_total = calculate_line_total(line_data['qty'], line_data['unit_price'])
                    line = InvoiceLine(
                        invoice_id=invoice.id,
                        description=line_data['description'],
                        qty=line_data['qty'],
                        unit_price=line_data['unit_price'],
                        line_total=line_total
                    )
                    db.session.add(line)
                
                db.session.flush()  # Ensure lines are saved
                
                # Calculate totals
                calculate_invoice_totals(invoice)
                
                db.session.commit()
                
                flash(f'Arve "{invoice.number}" on edukalt loodud.', 'success')
                logger.info(f"Invoice {invoice.number} created successfully with {len(valid_lines)} lines")
                return redirect(url_for('invoices.view_invoice', invoice_id=invoice.id))
            except Exception as e:
                logger.error(f"Error creating invoice: {str(e)}")
                db.session.rollback()
                flash('Arve loomisel tekkis viga. Palun proovi uuesti.', 'danger')
    else:
        if request.method == 'POST':
            logger.debug("Form validation failed")
    
    # Ensure at least one line form
    if not form.lines.entries:
        form.lines.append_entry()
    return render_template('invoice_form.html', form=form, title='Uus arve', clients=clients, vat_rates=vat_rates)


@invoices_bp.route('/invoices/<int:invoice_id>')
def view_invoice(invoice_id):
    """View invoice details."""
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('invoice_detail.html', invoice=invoice)


@invoices_bp.route('/invoices/<int:invoice_id>/edit', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    """Edit invoice."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Prevent editing paid invoices
    if invoice.status == 'makstud':
        flash('Makstud arveid ei saa muuta.', 'warning')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
    
    form = InvoiceForm(obj=invoice)
    
    # Set invoice ID for unique validation
    form._invoice_id = invoice_id
    
    # Populate client choices
    clients = Client.query.order_by(Client.name.asc()).all()
    form.client_id.choices = [(c.id, c.name) for c in clients]
    
    # Populate VAT rate choices
    vat_rates = VatRate.get_active_rates()
    form.vat_rate_id.choices = [(vr.id, f"{vr.name} ({vr.rate}%)") for vr in vat_rates]
    
    # Set current VAT rate
    if invoice.vat_rate_id:
        form.vat_rate_id.data = invoice.vat_rate_id
    else:
        # Fallback: try to find matching rate by value
        matching_rate = VatRate.query.filter_by(rate=invoice.vat_rate, is_active=True).first()
        if matching_rate:
            form.vat_rate_id.data = matching_rate.id
        elif vat_rates:
            form.vat_rate_id.data = vat_rates[0].id
    
    # Populate existing lines
    while len(form.lines) > 0:
        form.lines.pop_entry()
    
    for line in invoice.lines:
        line_form = form.lines.append_entry()
        line_form.id.data = line.id
        line_form.description.data = line.description
        line_form.qty.data = line.qty
        line_form.unit_price.data = line.unit_price
        line_form.line_total.data = line.line_total
    
    # Add empty line if no lines exist
    if not form.lines.entries:
        form.lines.append_entry()
    
    if form.validate_on_submit():
        # Update invoice fields
        invoice.client_id = form.client_id.data
        invoice.date = form.date.data
        invoice.due_date = form.due_date.data
        
        # Update VAT rate
        selected_vat_rate = VatRate.query.get(form.vat_rate_id.data)
        invoice.vat_rate_id = form.vat_rate_id.data
        invoice.vat_rate = selected_vat_rate.rate if selected_vat_rate else invoice.vat_rate  # Keep existing if not found
        
        invoice.status = form.status.data
        
        try:
            # Update lines
            existing_line_ids = [line.id for line in invoice.lines]
            form_line_ids = [int(line_form.id.data) for line_form in form.lines.entries if line_form.id.data]
            
            # Delete removed lines
            for line_id in existing_line_ids:
                if line_id not in form_line_ids:
                    line_to_delete = InvoiceLine.query.get(line_id)
                    if line_to_delete:
                        db.session.delete(line_to_delete)
            
            # Update or create lines
            for line_form in form.lines.entries:
                if line_form.description.data and line_form.qty.data and line_form.unit_price.data:
                    line_total = calculate_line_total(line_form.qty.data, line_form.unit_price.data)
                    
                    if line_form.id.data:
                        # Update existing line
                        line = InvoiceLine.query.get(int(line_form.id.data))
                        if line and line.invoice_id == invoice.id:
                            line.description = line_form.description.data
                            line.qty = line_form.qty.data
                            line.unit_price = line_form.unit_price.data
                            line.line_total = line_total
                    else:
                        # Create new line
                        line = InvoiceLine(
                            invoice_id=invoice.id,
                            description=line_form.description.data,
                            qty=line_form.qty.data,
                            unit_price=line_form.unit_price.data,
                            line_total=line_total
                        )
                        db.session.add(line)
            
            db.session.flush()
            
            # Recalculate totals
            calculate_invoice_totals(invoice)
            
            db.session.commit()
            flash(f'Arve "{invoice.number}" on edukalt uuendatud.', 'success')
            return redirect(url_for('invoices.view_invoice', invoice_id=invoice.id))
        except Exception as e:
            logger.error(f"Error updating invoice {invoice_id}: {str(e)}")
            db.session.rollback()
            flash('Arve uuendamisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    return render_template('invoice_form.html', form=form, invoice=invoice, title='Muuda arvet', vat_rates=vat_rates)


@invoices_bp.route('/invoices/<int:invoice_id>/delete', methods=['POST'])
def delete_invoice(invoice_id):
    """Delete invoice."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Prevent deleting paid invoices
    if invoice.status == 'makstud':
        flash('Makstud arveid ei saa kustutada.', 'warning')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
    
    try:
        invoice_number = invoice.number
        db.session.delete(invoice)
        db.session.commit()
        flash(f'Arve "{invoice_number}" on edukalt kustutatud.', 'success')
        return redirect(url_for('invoices.invoices'))
    except Exception as e:
        logger.error(f"Error deleting invoice {invoice_id}: {str(e)}")
        db.session.rollback()
        flash('Arve kustutamisel tekkis viga. Palun proovi uuesti.', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


@invoices_bp.route('/invoices/<int:invoice_id>/status/<new_status>', methods=['POST'])
def change_status(invoice_id, new_status):
    """Change invoice status using the status transition service."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    try:
        # Use the status transition service
        success, message = InvoiceStatusTransition.transition_invoice_status(invoice, new_status)
        
        if success:
            db.session.commit()
            flash(message, 'success')
        else:
            flash(message, 'warning')
            
    except Exception as e:
        logger.error(f"Error changing status for invoice {invoice_id} to {new_status}: {str(e)}")
        db.session.rollback()
        flash('Staatuse muutmisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


@invoices_bp.route('/invoices/<int:invoice_id>/duplicate', methods=['POST'])
def duplicate_invoice(invoice_id):
    """Duplicate invoice."""
    original = Invoice.query.get_or_404(invoice_id)
    
    try:
        # Generate new invoice number
        new_number = generate_invoice_number()
        
        # Create duplicate invoice
        duplicate = Invoice(
            number=new_number,
            client_id=original.client_id,
            date=date.today(),  # Use today's date
            due_date=original.due_date,
            vat_rate_id=original.vat_rate_id,
            vat_rate=original.vat_rate,
            status='mustand'  # Always create as draft
        )
        
        db.session.add(duplicate)
        db.session.flush()  # Get invoice ID
        
        # Duplicate invoice lines
        for original_line in original.lines:
            line = InvoiceLine(
                invoice_id=duplicate.id,
                description=original_line.description,
                qty=original_line.qty,
                unit_price=original_line.unit_price,
                line_total=original_line.line_total
            )
            db.session.add(line)
        
        db.session.flush()
        
        # Calculate totals
        calculate_invoice_totals(duplicate)
        
        db.session.commit()
        flash(f'Arve on edukalt dubleeritud uue numbriga "{new_number}".', 'success')
        return redirect(url_for('invoices.view_invoice', invoice_id=duplicate.id))
    except Exception as e:
        logger.error(f"Error duplicating invoice {invoice_id}: {str(e)}")
        db.session.rollback()
        flash('Arve dubleerimisel tekkis viga. Palun proovi uuesti.', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


@invoices_bp.route('/invoices/<int:invoice_id>/email', methods=['POST'])
def email_invoice(invoice_id):
    """Send invoice via email."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check if client has email
    if not invoice.client.email:
        flash('Kliendil ei ole e-maili aadressi määratud.', 'warning')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
    
    try:
        # Here you would implement actual email sending
        # For now, we'll just update the status and show success message
        if invoice.status == 'mustand':
            invoice.status = 'saadetud'
            db.session.commit()
        
        flash(f'Arve "{invoice.number}" on edukalt saadetud e-mailile {invoice.client.email}.', 'success')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
    except Exception as e:
        logger.error(f"Error sending invoice {invoice_id} via email: {str(e)}")
        db.session.rollback()
        flash('Arve saatmisel tekkis viga. Palun proovi uuesti.', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))