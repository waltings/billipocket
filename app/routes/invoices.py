from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models import db, Invoice, Client, InvoiceLine, VatRate
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
    
    
    if request.method == 'POST':
        print(f"\n--- POST REQUEST DATA ANALYSIS ---")
        print(f"request.form keys: {list(request.form.keys())}")
        print(f"request.form data: {dict(request.form)}")
        
        # Debug: Analyze form data structure
        line_fields = {}
        for key, value in request.form.items():
            if key.startswith('lines-'):
                line_fields[key] = value
        print(f"Line fields from request.form: {line_fields}")
        
        # Debug: Check form validation
        print(f"\n--- FORM VALIDATION ANALYSIS ---")
        print(f"form.validate_on_submit(): {form.validate_on_submit()}")
        print(f"form.errors: {form.errors}")
        print(f"form.client_id.data: {form.client_id.data}")
        print(f"form.date.data: {form.date.data}")
        print(f"form.due_date.data: {form.due_date.data}")
        print(f"form.vat_rate_id.data: {form.vat_rate_id.data}")
        print(f"form.status.data: {form.status.data}")
        
        # Debug: Analyze form.lines structure
        print(f"\n--- FORM LINES ANALYSIS ---")
        print(f"form.lines type: {type(form.lines)}")
        print(f"form.lines.entries length: {len(form.lines.entries)}")
        
        for i, line_form in enumerate(form.lines.entries):
            print(f"\n  Line {i}:")
            print(f"    line_form type: {type(line_form)}")
            print(f"    hasattr(line_form, 'description'): {hasattr(line_form, 'description')}")
            if hasattr(line_form, 'description'):
                print(f"    line_form.description type: {type(line_form.description)}")
                print(f"    hasattr(line_form.description, 'data'): {hasattr(line_form.description, 'data')}")
                if hasattr(line_form.description, 'data'):
                    print(f"    line_form.description.data: '{line_form.description.data}'")
                    print(f"    line_form.description.data stripped: '{line_form.description.data.strip() if line_form.description.data else None}'")
                print(f"    line_form.description.errors: {getattr(line_form.description, 'errors', 'NO_ERRORS_ATTR')}")
            
            print(f"    hasattr(line_form, 'qty'): {hasattr(line_form, 'qty')}")
            if hasattr(line_form, 'qty'):
                print(f"    line_form.qty type: {type(line_form.qty)}")
                print(f"    hasattr(line_form.qty, 'data'): {hasattr(line_form.qty, 'data')}")
                if hasattr(line_form.qty, 'data'):
                    print(f"    line_form.qty.data: {line_form.qty.data}")
                print(f"    line_form.qty.errors: {getattr(line_form.qty, 'errors', 'NO_ERRORS_ATTR')}")
            
            print(f"    hasattr(line_form, 'unit_price'): {hasattr(line_form, 'unit_price')}")
            if hasattr(line_form, 'unit_price'):
                print(f"    line_form.unit_price type: {type(line_form.unit_price)}")
                print(f"    hasattr(line_form.unit_price, 'data'): {hasattr(line_form.unit_price, 'data')}")
                if hasattr(line_form.unit_price, 'data'):
                    print(f"    line_form.unit_price.data: {line_form.unit_price.data}")
                print(f"    line_form.unit_price.errors: {getattr(line_form.unit_price, 'errors', 'NO_ERRORS_ATTR')}")
            
            # Check line form overall errors
            if hasattr(line_form, 'errors'):
                print(f"    line_form.errors: {line_form.errors}")
    
    if form.validate_on_submit():
        print(f"\n--- FORM VALIDATION PASSED - PROCESSING LINES ---")
        
        # Custom validation: check if form is valid and has at least one complete line
        valid_lines = []
        for i, line_form in enumerate(form.lines.entries):
            print(f"\n  Validating Line {i}:")
            
            # Check description
            has_description = (hasattr(line_form, 'description') and 
                             hasattr(line_form.description, 'data') and
                             line_form.description.data and 
                             line_form.description.data.strip())
            print(f"    has_description: {has_description}")
            
            # Check qty
            has_qty = (hasattr(line_form, 'qty') and 
                      hasattr(line_form.qty, 'data') and
                      line_form.qty.data is not None)
            print(f"    has_qty: {has_qty}")
            
            # Check unit_price
            has_unit_price = (hasattr(line_form, 'unit_price') and 
                             hasattr(line_form.unit_price, 'data') and
                             line_form.unit_price.data is not None)
            print(f"    has_unit_price: {has_unit_price}")
            
            if has_description and has_qty and has_unit_price:
                print(f"    Line {i} IS VALID - adding to valid_lines")
                valid_lines.append(line_form)
            else:
                print(f"    Line {i} IS INVALID - skipping")
        
        print(f"\n--- VALID LINES SUMMARY ---")
        print(f"Number of valid_lines: {len(valid_lines)}")
        
        if len(valid_lines) == 0:
            print("NO VALID LINES FOUND - trying alternate data access method")
            # The issue is that FormField objects are corrupted during template rendering
            # Let's try accessing data via the .data attribute instead
            for i, line_form in enumerate(form.lines.entries):
                print(f"  Trying alternate access for line {i}:")
                try:
                    data = line_form.data
                    print(f"    line_form.data: {data}")
                    desc = data.get('description', '').strip() if data else ''
                    qty = data.get('qty') if data else None
                    price = data.get('unit_price') if data else None
                    print(f"    desc: '{desc}', qty: {qty}, price: {price}")
                    
                    if desc and qty is not None and price is not None:
                        print(f"    Line {i} HAS VALID DATA via .data!")
                        valid_lines.append(line_form)
                except Exception as e:
                    print(f"    Error accessing line_form.data: {e}")
            
            print(f"After alternate method - valid_lines: {len(valid_lines)}")
            
            if len(valid_lines) == 0:
                flash('Palun lisa vähemalt üks arve rida.', 'warning')
        
        if len(valid_lines) > 0:
            print("VALID LINES FOUND - proceeding with invoice creation")
            # Use form invoice number (user can modify it)
            invoice_number = form.number.data or generate_invoice_number()
            print(f"Using invoice number: {invoice_number}")
        
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
            print(f"Created invoice object: {invoice}")
            
            try:
                db.session.add(invoice)
                db.session.flush()  # Get invoice ID
                print(f"Invoice added to DB, ID: {invoice.id}")
                
                # Add invoice lines (use valid_lines instead of form.lines)
                for i, line_form in enumerate(valid_lines):
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
                    print(f"Added line {i}: {line.description}, qty={line.qty}, price={line.unit_price}, total={line.line_total}")
                
                db.session.flush()  # Ensure lines are saved
                print("Lines flushed to DB")
                
                # Calculate totals
                calculate_invoice_totals(invoice)
                print(f"Totals calculated - subtotal: {invoice.subtotal}, vat: {invoice.vat_amount}, total: {invoice.total}")
                
                db.session.commit()
                print("Transaction committed successfully")
                
                flash(f'Arve "{invoice.number}" on edukalt loodud.', 'success')
                print(f"SUCCESS - redirecting to view_invoice")
                return redirect(url_for('invoices.view_invoice', invoice_id=invoice.id))
            except Exception as e:
                print(f"EXCEPTION during invoice creation: {str(e)}")
                print(f"Exception type: {type(e)}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                db.session.rollback()
                flash('Arve loomisel tekkis viga. Palun proovi uuesti.', 'danger')
    else:
        if request.method == 'POST':
            print("\n--- FORM VALIDATION FAILED ---")
            print("Form did not validate - returning to template")
    
    # Ensure at least one line form
    if not form.lines.entries:
        print("No line entries found - adding empty line")
        form.lines.append_entry()
    else:
        print(f"Found {len(form.lines.entries)} existing line entries")
    
    print("=== RETURNING TO TEMPLATE ===")
    print(f"form.client_id.choices: {form.client_id.choices}")
    print(f"Clients being passed to template: {[(c.id, c.name) for c in clients]}")
    print()
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
        db.session.rollback()
        flash('Arve kustutamisel tekkis viga. Palun proovi uuesti.', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


@invoices_bp.route('/invoices/<int:invoice_id>/status/<new_status>', methods=['POST'])
def change_status(invoice_id, new_status):
    """Change invoice status."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Use the new validation logic
    can_change, error_message = invoice.can_change_status_to(new_status)
    if not can_change:
        flash(error_message, 'warning')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
    
    # Status transition validation
    status_messages = {
        'mustand': 'Arve on muudetud mustandiks.',
        'saadetud': 'Arve on märgitud saadetud.',
        'makstud': 'Arve on märgitud makstud.',
        'tähtaeg ületatud': 'Arve on märgitud tähtaja ületanud.'
    }
    
    try:
        invoice.set_status(new_status)
        db.session.commit()
        flash(status_messages[new_status], 'success')
    except ValueError as ve:
        flash(str(ve), 'warning')
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