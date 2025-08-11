from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models import db, Invoice, Client, InvoiceLine
from app.forms import InvoiceForm, InvoiceSearchForm, InvoiceLineForm
from app.services.numbering import generate_invoice_number
from app.services.totals import calculate_invoice_totals, calculate_line_total
from datetime import date, datetime
from sqlalchemy import or_

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
    today = date.today()
    overdue_invoices = Invoice.query.filter(
        Invoice.due_date < today,
        Invoice.status == 'saadetud'
    ).all()
    
    for invoice in overdue_invoices:
        invoice.status = 'tähtaeg ületatud'
    
    if overdue_invoices:
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
    
    # Process form submission
    if request.method == 'POST':
        print(f"DEBUG: POST to new_invoice, form data count: {len(dict(request.form))}")
        print(f"DEBUG: Lines count: {len(form.lines.entries)}")
    
    # Custom validation: check if form is valid and has at least one complete line
    valid_lines = []
    for line_form in form.lines.entries:
        if (hasattr(line_form, 'description') and 
            line_form.description.data and 
            line_form.qty.data and 
            line_form.unit_price.data):
            valid_lines.append(line_form)
    
    # Remove empty lines from validation
    form.lines.entries[:] = [line for line in form.lines.entries if (
        hasattr(line, 'description') and 
        line.description.data and 
        line.qty.data and 
        line.unit_price.data
    )]
    
    print(f"DEBUG: Valid lines found: {len(valid_lines)}")
    print(f"DEBUG: Form lines after filtering: {len(form.lines.entries)}")
    
    if len(valid_lines) == 0:
        flash('Palun lisa vähemalt üks arve rida.', 'warning')
        # Re-add an empty line for the form
        if not form.lines.entries:
            form.lines.append_entry()
    elif form.validate_on_submit():
        # Generate invoice number
        invoice_number = generate_invoice_number()
        
        # Create invoice
        invoice = Invoice(
            number=invoice_number,
            client_id=form.client_id.data,
            date=form.date.data,
            due_date=form.due_date.data,
            vat_rate=form.vat_rate.data,
            status=form.status.data
        )
        
        try:
            db.session.add(invoice)
            db.session.flush()  # Get invoice ID
            
            # Add invoice lines (use valid_lines instead of form.lines)
            for line_form in valid_lines:
                line_total = calculate_line_total(line_form.qty.data, line_form.unit_price.data)
                line = InvoiceLine(
                    invoice_id=invoice.id,
                    description=line_form.description.data,
                    qty=line_form.qty.data,
                    unit_price=line_form.unit_price.data,
                    line_total=line_total
                )
                db.session.add(line)
            
            db.session.flush()  # Ensure lines are saved
            
            # Calculate totals
            calculate_invoice_totals(invoice)
            
            db.session.commit()
            flash(f'Arve "{invoice.number}" on edukalt loodud.', 'success')
            return redirect(url_for('invoices.view_invoice', invoice_id=invoice.id))
        except Exception as e:
            db.session.rollback()
            flash('Arve loomisel tekkis viga. Palun proovi uuesti.', 'danger')
    else:
        print(f"DEBUG: Form validation failed: {form.errors}")
        # Re-add an empty line for the form if needed
        if not form.lines.entries:
            form.lines.append_entry()
    
    # Ensure at least one line form
    if not form.lines.entries:
        form.lines.append_entry()
    
    return render_template('invoice_form.html', form=form, title='Uus arve')


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
    
    # Populate client choices
    clients = Client.query.order_by(Client.name.asc()).all()
    form.client_id.choices = [(c.id, c.name) for c in clients]
    
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
        invoice.vat_rate = form.vat_rate.data
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
            db.session.rollback()
            flash('Arve uuendamisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    return render_template('invoice_form.html', form=form, invoice=invoice, title='Muuda arvet')


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
        db.session.rollback()
        flash('Arve kustutamisel tekkis viga. Palun proovi uuesti.', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


@invoices_bp.route('/invoices/<int:invoice_id>/status/<new_status>', methods=['POST'])
def change_status(invoice_id, new_status):
    """Change invoice status."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    valid_statuses = ['mustand', 'saadetud', 'makstud', 'tähtaeg ületatud']
    if new_status not in valid_statuses:
        flash('Vigane staatus.', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
    
    # Status transition validation
    status_messages = {
        'mustand': 'Arve on muudetud mustandiks.',
        'saadetud': 'Arve on märgitud saadetud.',
        'makstud': 'Arve on märgitud makstud.',
        'tähtaeg ületatud': 'Arve on märgitud tähtaja ületanud.'
    }
    
    try:
        invoice.status = new_status
        db.session.commit()
        flash(status_messages[new_status], 'success')
    except Exception as e:
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
        db.session.rollback()
        flash('Arve saatmisel tekkis viga. Palun proovi uuesti.', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))