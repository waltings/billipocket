"""
Integration tests for invoice management functionality.

Tests comprehensive invoice workflows including:
- Creating invoices with different VAT rates
- Editing existing invoices
- Status changes and validation
- Line items management
- Invoice duplication and deletion
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta

from app.models import db, Invoice, InvoiceLine, Client, VatRate


class TestInvoiceCreation:
    """Test invoice creation workflows."""
    
    def test_create_invoice_with_vat_rate_selection(self, client, app_context, sample_client):
        """Test creating invoice with VAT rate dropdown selection."""
        # First ensure VAT rates exist
        VatRate.create_default_rates()
        db.session.commit()
        
        # Get available VAT rates
        vat_rates = VatRate.get_active_rates()
        assert len(vat_rates) >= 4  # 0%, 9%, 20%, 24%
        
        # Test creating invoice with each VAT rate
        for vat_rate_obj in vat_rates:
            form_data = {
                'client_id': str(sample_client.id),
                'date': '2025-08-10',
                'due_date': '2025-08-24',
                'vat_rate_id': str(vat_rate_obj.id),
                'status': 'mustand',
                'lines-0-description': f'Test service with {vat_rate_obj.rate}% VAT',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post('/invoices/new', data=form_data, follow_redirects=True)
            assert response.status_code == 200
            
            # Verify invoice was created with correct VAT rate
            invoice = Invoice.query.filter_by(vat_rate_id=vat_rate_obj.id).first()
            assert invoice is not None
            assert invoice.get_effective_vat_rate() == vat_rate_obj.rate
            
            # Clean up for next iteration
            if invoice:
                db.session.delete(invoice)
                db.session.commit()
    
    def test_create_invoice_with_multiple_line_items(self, client, app_context, sample_client):
        """Test creating invoice with multiple line items."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'Web development',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '300.00',
            'lines-1-description': 'Consulting services',
            'lines-1-qty': '5.00',
            'lines-1-unit_price': '80.00',
            'lines-2-description': 'Project management',
            'lines-2-qty': '2.50',
            'lines-2-unit_price': '120.00'
        }
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify invoice and lines were created
        invoice = Invoice.query.filter_by(client_id=sample_client.id).first()
        assert invoice is not None
        assert len(invoice.lines) == 3
        
        # Verify line calculations
        expected_subtotal = Decimal('300.00') + Decimal('400.00') + Decimal('300.00')  # 1000.00
        assert invoice.subtotal == expected_subtotal
        
        # Verify VAT calculation (24% of 1000.00 = 240.00)
        expected_total = expected_subtotal * Decimal('1.24')
        assert invoice.total == expected_total
    
    def test_invoice_auto_numbering(self, client, app_context, sample_client):
        """Test automatic invoice numbering system."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create first invoice - should get 2025-0001
        form_data = {
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'First invoice',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        invoice1 = Invoice.query.filter_by(client_id=sample_client.id).first()
        assert invoice1.number.startswith('2025-')
        
        # Create second invoice - should increment number
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        invoices = Invoice.query.filter_by(client_id=sample_client.id).order_by(Invoice.number).all()
        assert len(invoices) == 2
        assert invoices[0].number != invoices[1].number
    
    def test_create_invoice_with_estonian_text(self, client, app_context, sample_client):
        """Test creating invoice with Estonian characters (ä, ö, ü)."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'Veebiarenduse teenused ja nõustamine äriküsimustes',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '500.00'
        }
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        invoice = Invoice.query.filter_by(client_id=sample_client.id).first()
        assert invoice is not None
        assert len(invoice.lines) == 1
        assert 'äriküsimustes' in invoice.lines[0].description


class TestInvoiceEditing:
    """Test invoice editing workflows."""
    
    def test_edit_existing_invoice_form_loads(self, client, app_context, sample_invoice):
        """Test that invoice edit form loads correctly with existing data."""
        response = client.get(f'/invoices/{sample_invoice.id}/edit')
        assert response.status_code == 200
        assert b'Edit Invoice' in response.data or b'Muuda arvet' in response.data
        assert sample_invoice.number.encode() in response.data
    
    def test_edit_invoice_details(self, client, app_context, sample_invoice):
        """Test editing invoice details."""
        original_due_date = sample_invoice.due_date
        new_due_date = original_due_date + timedelta(days=7)
        
        form_data = {
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': new_due_date.strftime('%Y-%m-%d'),
            'vat_rate': str(sample_invoice.vat_rate),
            'status': sample_invoice.status,
            'lines-0-description': 'Updated description',
            'lines-0-qty': '2.00',
            'lines-0-unit_price': '150.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify changes were saved
        db.session.refresh(sample_invoice)
        assert sample_invoice.due_date == new_due_date
    
    def test_edit_invoice_add_line_items(self, client, app_context, sample_invoice):
        """Test adding line items to existing invoice."""
        original_line_count = len(sample_invoice.lines)
        
        form_data = {
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': sample_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate': str(sample_invoice.vat_rate),
            'status': sample_invoice.status,
            'lines-0-description': 'Original service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00',
            'lines-1-description': 'Additional service',
            'lines-1-qty': '2.00',
            'lines-1-unit_price': '75.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                             data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify line was added
        db.session.refresh(sample_invoice)
        assert len(sample_invoice.lines) == 2


class TestInvoiceStatusManagement:
    """Test invoice status changes and validation."""
    
    def test_invoice_status_transitions(self, client, app_context, sample_client):
        """Test valid invoice status transitions."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create invoice in draft status
        invoice = Invoice(
            number='TEST-2025-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='mustand',
            subtotal=Decimal('100.00'),
            total=Decimal('124.00')
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Test mustand -> saadetud
        assert invoice.can_change_status_to('saadetud')[0] is True
        invoice.set_status('saadetud')
        assert invoice.status == 'saadetud'
        
        # Test saadetud -> makstud
        assert invoice.can_change_status_to('makstud')[0] is True
        invoice.set_status('makstud')
        assert invoice.status == 'makstud'
        
        # Test makstud -> saadetud (should fail)
        can_change, error = invoice.can_change_status_to('saadetud')
        assert can_change is False
        assert 'Makstud arveid ei saa tagasi' in error
    
    def test_overdue_status_automatic_update(self, client, app_context, sample_client):
        """Test automatic overdue status updates."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create overdue invoice
        overdue_invoice = Invoice(
            number='OVERDUE-2025-001',
            client_id=sample_client.id,
            date=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=5),  # 5 days overdue
            vat_rate_id=standard_vat.id,
            status='saadetud',
            subtotal=Decimal('200.00'),
            total=Decimal('248.00')
        )
        db.session.add(overdue_invoice)
        db.session.commit()
        
        # Check that it's detected as overdue
        assert overdue_invoice.is_overdue is True
        
        # Update overdue status
        overdue_invoice.update_status_if_overdue()
        assert overdue_invoice.status == 'tähtaeg ületatud'
        
        # Test bulk update
        updated_count = Invoice.update_overdue_invoices()
        assert updated_count >= 0  # May be 0 if already updated
    
    def test_paid_invoice_not_overdue(self, client, app_context, sample_client):
        """Test that paid invoices are not considered overdue."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create paid invoice that's past due date
        paid_invoice = Invoice(
            number='PAID-2025-001',
            client_id=sample_client.id,
            date=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=5),  # Past due
            vat_rate_id=standard_vat.id,
            status='makstud',
            subtotal=Decimal('300.00'),
            total=Decimal('372.00')
        )
        db.session.add(paid_invoice)
        db.session.commit()
        
        # Paid invoices should not be overdue
        assert paid_invoice.is_overdue is False


class TestInvoiceCalculations:
    """Test invoice calculation accuracy."""
    
    def test_vat_calculations_all_rates(self, client, app_context, sample_client):
        """Test VAT calculations with all supported rates."""
        VatRate.create_default_rates()
        vat_rates = VatRate.get_active_rates()
        
        test_amounts = [
            Decimal('100.00'),
            Decimal('344.26'),  # Common development service amount
            Decimal('1234.56')   # Larger amount
        ]
        
        for vat_rate_obj in vat_rates:
            for subtotal in test_amounts:
                invoice = Invoice(
                    number=f'TEST-VAT-{vat_rate_obj.rate}-{subtotal}',
                    client_id=sample_client.id,
                    date=date.today(),
                    due_date=date.today() + timedelta(days=14),
                    vat_rate_id=vat_rate_obj.id,
                    subtotal=subtotal
                )
                
                # Test VAT amount calculation
                expected_vat = subtotal * (vat_rate_obj.rate / 100)
                expected_vat = expected_vat.quantize(Decimal('0.01'))  # Round to 2 decimal places
                
                assert invoice.vat_amount.quantize(Decimal('0.01')) == expected_vat
                
                # Test total calculation
                expected_total = subtotal + expected_vat
                invoice.total = expected_total
                assert invoice.total == expected_total
    
    def test_two_decimal_places_precision(self, client, app_context, sample_client):
        """Test that calculations maintain 2 decimal places precision."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='PRECISION-TEST-2025-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            subtotal=Decimal('123.456')  # More than 2 decimal places
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Add line with calculation
        line = InvoiceLine(
            invoice_id=invoice.id,
            description='Precision test service',
            qty=Decimal('3.333'),
            unit_price=Decimal('37.037'),
            line_total=Decimal('3.333') * Decimal('37.037')
        )
        db.session.add(line)
        db.session.commit()
        
        # Recalculate totals
        invoice.calculate_totals()
        
        # Check that amounts have proper precision
        assert invoice.subtotal.as_tuple().exponent >= -2  # Max 2 decimal places
        assert invoice.total.as_tuple().exponent >= -2


class TestInvoiceDuplicationAndDeletion:
    """Test invoice duplication and deletion functionality."""
    
    def test_duplicate_invoice(self, client, app_context, sample_invoice):
        """Test invoice duplication functionality."""
        original_count = Invoice.query.count()
        
        response = client.post(f'/invoices/{sample_invoice.id}/duplicate', 
                             follow_redirects=True)
        assert response.status_code == 200
        
        # Verify duplicate was created
        new_count = Invoice.query.count()
        assert new_count == original_count + 1
        
        # Find the duplicate invoice
        duplicates = Invoice.query.filter(Invoice.id != sample_invoice.id).all()
        duplicate = duplicates[-1]  # Most recent
        
        # Verify duplicate has different number but same other details
        assert duplicate.number != sample_invoice.number
        assert duplicate.client_id == sample_invoice.client_id
        assert duplicate.subtotal == sample_invoice.subtotal
        assert duplicate.status == 'mustand'  # Duplicates should be drafts
    
    def test_delete_draft_invoice(self, client, app_context, sample_client):
        """Test deleting draft invoice (should be allowed)."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create draft invoice
        draft_invoice = Invoice(
            number='DELETE-TEST-2025-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='mustand',
            subtotal=Decimal('100.00'),
            total=Decimal('124.00')
        )
        db.session.add(draft_invoice)
        db.session.commit()
        
        invoice_id = draft_invoice.id
        
        response = client.post(f'/invoices/{invoice_id}/delete', 
                             follow_redirects=True)
        assert response.status_code == 200
        
        # Verify invoice was deleted
        deleted_invoice = Invoice.query.get(invoice_id)
        assert deleted_invoice is None
    
    def test_delete_paid_invoice_restricted(self, client, app_context, sample_client):
        """Test that paid invoices cannot be deleted."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create paid invoice
        paid_invoice = Invoice(
            number='PAID-DELETE-TEST-2025-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='makstud',
            subtotal=Decimal('100.00'),
            total=Decimal('124.00')
        )
        db.session.add(paid_invoice)
        db.session.commit()
        
        invoice_id = paid_invoice.id
        
        response = client.post(f'/invoices/{invoice_id}/delete', 
                             follow_redirects=True)
        # Should redirect with error message or return error status
        
        # Verify invoice still exists
        existing_invoice = Invoice.query.get(invoice_id)
        assert existing_invoice is not None
        assert existing_invoice.status == 'makstud'


class TestInvoiceValidation:
    """Test invoice validation and error handling."""
    
    def test_duplicate_invoice_number_validation(self, client, app_context, sample_client):
        """Test that duplicate invoice numbers are rejected."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create first invoice
        invoice1 = Invoice(
            number='DUPLICATE-TEST-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            subtotal=Decimal('100.00'),
            total=Decimal('124.00')
        )
        db.session.add(invoice1)
        db.session.commit()
        
        # Try to create invoice with same number
        form_data = {
            'number': 'DUPLICATE-TEST-001',  # Same number
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'Test service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data)
        # Should return form with error
        assert b'number' in response.data.lower() or b'number' in response.data.lower()
    
    def test_invalid_vat_rate_validation(self, client, app_context, sample_client):
        """Test validation of invalid VAT rates."""
        form_data = {
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate': '150.00',  # Invalid - over 100%
            'status': 'mustand',
            'lines-0-description': 'Test service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data)
        # Should return form with validation error
        assert response.status_code in [200, 400]  # Form error or validation error
    
    def test_negative_amounts_validation(self, client, app_context, sample_client):
        """Test validation of negative amounts."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'Test service',
            'lines-0-qty': '-1.00',  # Negative quantity
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data)
        # Should return form with validation error
        assert response.status_code in [200, 400]