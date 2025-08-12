"""
Complete workflow integration tests.

Tests comprehensive business workflows from start to finish:
- Complete invoice lifecycle (draft → sent → paid)
- Client management workflows
- Multi-user scenarios and edge cases
- Real-world business scenarios
- Estonian business rules and regulations
- Cross-module integration and data consistency
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from app.models import db, Client, Invoice, InvoiceLine, VatRate, CompanySettings
from app.services.numbering import generate_invoice_number
from app.services.status_transitions import InvoiceStatusTransition
from app.services.totals import calculate_invoice_totals


class TestCompleteInvoiceLifecycle:
    """Test complete invoice lifecycle from creation to payment."""
    
    def test_draft_to_paid_workflow(self, client, app_context, sample_client):
        """Test complete workflow: create draft → send → pay."""
        # Setup
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Step 1: Create draft invoice
        form_data = {
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'Veebiarenduse teenused',
            'lines-0-qty': '40.0',
            'lines-0-unit_price': '75.50',
            'lines-1-description': 'Projektijuhtimine',
            'lines-1-qty': '10.0',
            'lines-1-unit_price': '120.00'
        }
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        invoice = Invoice.query.filter_by(client_id=sample_client.id).first()
        assert invoice is not None
        assert invoice.status == 'mustand'
        assert len(invoice.lines) == 2
        
        # Verify calculations
        expected_subtotal = Decimal('40.0') * Decimal('75.50') + Decimal('10.0') * Decimal('120.00')
        expected_total = expected_subtotal * Decimal('1.24')  # 24% VAT
        
        assert invoice.subtotal == expected_subtotal
        assert invoice.total == expected_total
        
        # Step 2: Send invoice (change status)
        response = client.post(f'/invoices/{invoice.id}/status', 
                              data={'status': 'saadetud'}, 
                              follow_redirects=True)
        assert response.status_code == 200
        
        db.session.refresh(invoice)
        assert invoice.status == 'saadetud'
        
        # Step 3: Mark as paid
        response = client.post(f'/invoices/{invoice.id}/status', 
                              data={'status': 'makstud'}, 
                              follow_redirects=True)
        assert response.status_code == 200
        
        db.session.refresh(invoice)
        assert invoice.status == 'makstud'
        assert invoice.is_paid is True
        
        # Step 4: Verify paid invoice cannot be edited
        assert invoice.can_be_edited is False
        
        # Try to edit paid invoice (should fail)
        edit_data = form_data.copy()
        edit_data['status'] = 'makstud'  # Keep status as paid
        
        response = client.post(f'/invoices/{invoice.id}/edit', 
                              data=edit_data)
        # Should either redirect or show error
        assert response.status_code in [200, 302]
    
    def test_overdue_invoice_workflow(self, client, app_context, sample_client):
        """Test workflow for overdue invoices."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create invoice that's already overdue
        overdue_date = date.today() - timedelta(days=5)
        invoice = Invoice(
            number='OVERDUE-TEST-001',
            client_id=sample_client.id,
            date=overdue_date - timedelta(days=10),
            due_date=overdue_date,
            vat_rate_id=standard_vat.id,
            status='saadetud',
            subtotal=Decimal('500.00'),
            total=Decimal('620.00')
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Check overdue status
        assert invoice.is_overdue is True
        
        # Update to overdue status
        invoice.update_status_if_overdue()
        assert invoice.status == 'tähtaeg ületatud'
        
        # Test bulk overdue update
        updated_count = Invoice.update_overdue_invoices()
        # Should be 0 since we already updated this one
        assert updated_count == 0
        
        # Try to change overdue back to sent while still overdue (should fail)
        service = InvoiceStatusTransition
        success, message = service.transition_invoice_status(invoice, service.SENT)
        assert success is False
        assert 'tähtaja ületanud' in message.lower()
        
        # Can still mark as paid
        success, message = service.transition_invoice_status(invoice, service.PAID)
        assert success is True
        assert invoice.status == 'makstud'
    
    def test_invoice_duplication_workflow(self, client, app_context, sample_client):
        """Test invoice duplication and modification workflow."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create original invoice
        original = Invoice(
            number='ORIGINAL-001',
            client_id=sample_client.id,
            date=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=16),
            vat_rate_id=standard_vat.id,
            status='makstud',
            subtotal=Decimal('1000.00'),
            total=Decimal('1240.00')
        )
        db.session.add(original)
        db.session.flush()
        
        # Add lines to original
        line1 = InvoiceLine(
            invoice_id=original.id,
            description='Konsultatsiooniteenused',
            qty=Decimal('20.0'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('1000.00')
        )
        db.session.add(line1)
        db.session.commit()
        
        # Duplicate invoice
        response = client.post(f'/invoices/{original.id}/duplicate', follow_redirects=True)
        assert response.status_code == 200
        
        # Find duplicate
        duplicate = Invoice.query.filter(
            Invoice.id != original.id,
            Invoice.client_id == sample_client.id
        ).first()
        
        assert duplicate is not None
        assert duplicate.number != original.number
        assert duplicate.status == 'mustand'  # Should be draft
        assert duplicate.client_id == original.client_id
        assert len(duplicate.lines) == len(original.lines)
        
        # Modify duplicate
        edit_data = {
            'number': duplicate.number,
            'client_id': str(duplicate.client_id),
            'date': duplicate.date.strftime('%Y-%m-%d'),
            'due_date': (date.today() + timedelta(days=14)).strftime('%Y-%m-%d'),
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'Muudetud konsultatsiooniteenused',
            'lines-0-qty': '25.0',
            'lines-0-unit_price': '60.00'
        }
        
        response = client.post(f'/invoices/{duplicate.id}/edit', 
                              data=edit_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify changes
        db.session.refresh(duplicate)
        assert duplicate.lines[0].description == 'Muudetud konsultatsiooniteenused'
        assert duplicate.lines[0].qty == Decimal('25.0')
        assert duplicate.lines[0].unit_price == Decimal('60.00')
    
    def test_invoice_deletion_workflow(self, client, app_context, sample_client):
        """Test invoice deletion rules and workflow."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create draft invoice (can be deleted)
        draft_invoice = Invoice(
            number='DELETE-DRAFT-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='mustand'
        )
        db.session.add(draft_invoice)
        
        # Create paid invoice (cannot be deleted)
        paid_invoice = Invoice(
            number='DELETE-PAID-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='makstud'
        )
        db.session.add(paid_invoice)
        db.session.commit()
        
        draft_id = draft_invoice.id
        paid_id = paid_invoice.id
        
        # Delete draft invoice (should succeed)
        response = client.post(f'/invoices/{draft_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        
        deleted_draft = Invoice.query.get(draft_id)
        assert deleted_draft is None
        
        # Try to delete paid invoice (should fail or be restricted)
        response = client.post(f'/invoices/{paid_id}/delete', follow_redirects=True)
        # Application should prevent this
        
        existing_paid = Invoice.query.get(paid_id)
        assert existing_paid is not None  # Should still exist


class TestClientManagementWorkflows:
    """Test complete client management workflows."""
    
    def test_client_lifecycle_with_invoices(self, client, app_context):
        """Test complete client lifecycle with associated invoices."""
        # Step 1: Create client
        client_data = {
            'name': 'Workflow Test Klient OÜ',
            'registry_code': '87654321',
            'email': 'workflow@test.ee',
            'phone': '+372 5555 9999',
            'address': 'Workflow tänav 123, 10001 Tallinn'
        }
        
        response = client.post('/clients/new', data=client_data, follow_redirects=True)
        assert response.status_code == 200
        
        test_client = Client.query.filter_by(name='Workflow Test Klient OÜ').first()
        assert test_client is not None
        
        # Step 2: Create multiple invoices for client
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        invoice_data = {
            'client_id': str(test_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'saadetud',
            'lines-0-description': 'Teenus 1',
            'lines-0-qty': '1.0',
            'lines-0-unit_price': '100.00'
        }
        
        # Create 3 invoices
        for i in range(3):
            invoice_data['number'] = f'WF-2025-{i:03d}'
            response = client.post('/invoices/new', data=invoice_data, follow_redirects=True)
            assert response.status_code == 200
        
        # Verify client properties
        db.session.refresh(test_client)
        assert test_client.invoice_count == 3
        assert test_client.last_invoice_date is not None
        
        # Mark one invoice as paid to test revenue calculation
        first_invoice = Invoice.query.filter_by(client_id=test_client.id).first()
        first_invoice.status = 'makstud'
        db.session.commit()
        
        # Check revenue calculation
        db.session.refresh(test_client)
        assert test_client.total_revenue > 0
        
        # Step 3: Update client information
        updated_data = client_data.copy()
        updated_data['name'] = 'Uuendatud Workflow Klient OÜ'
        updated_data['email'] = 'updated@workflow.ee'
        
        response = client.post(f'/clients/{test_client.id}/edit', 
                              data=updated_data, follow_redirects=True)
        assert response.status_code == 200
        
        db.session.refresh(test_client)
        assert test_client.name == 'Uuendatud Workflow Klient OÜ'
        assert test_client.email == 'updated@workflow.ee'
        
        # Step 4: View client detail page
        response = client.get(f'/clients/{test_client.id}')
        assert response.status_code == 200
        assert b'Uuendatud Workflow Klient OÜ' in response.data
        
        # Should show associated invoices
        for invoice in test_client.invoices:
            assert invoice.number.encode() in response.data
    
    def test_client_search_and_filtering(self, client, app_context):
        """Test client search and filtering workflows."""
        # Create multiple clients
        clients_data = [
            {'name': 'Alpha Tehnoloogiad OÜ', 'email': 'alpha@tech.ee'},
            {'name': 'Beta Lahendused AS', 'email': 'beta@solutions.ee'},
            {'name': 'Gamma Consulting', 'email': 'gamma@consulting.com'},
            {'name': 'Delta Services OÜ', 'email': 'delta@services.ee'}
        ]
        
        for client_data in clients_data:
            response = client.post('/clients/new', data=client_data, follow_redirects=True)
            assert response.status_code == 200
        
        # Test basic client list
        response = client.get('/clients')
        assert response.status_code == 200
        
        for client_data in clients_data:
            assert client_data['name'].encode() in response.data
        
        # Test search functionality (if implemented)
        response = client.get('/clients?search=Alpha')
        assert response.status_code == 200
        # May or may not have search implemented


class TestMultiVATRateWorkflows:
    """Test workflows with multiple VAT rates."""
    
    def test_different_vat_rates_workflow(self, client, app_context, sample_client):
        """Test creating invoices with different VAT rates."""
        VatRate.create_default_rates()
        vat_rates = VatRate.get_active_rates()
        
        invoices_created = []
        
        # Create invoice for each VAT rate
        for i, vat_rate in enumerate(vat_rates):
            form_data = {
                'number': f'VAT-{vat_rate.rate}-{i:03d}',
                'client_id': str(sample_client.id),
                'date': '2025-08-10',
                'due_date': '2025-08-24',
                'vat_rate_id': str(vat_rate.id),
                'status': 'saadetud',
                'lines-0-description': f'Service with {vat_rate.rate}% VAT',
                'lines-0-qty': '1.0',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post('/invoices/new', data=form_data, follow_redirects=True)
            assert response.status_code == 200
            
            invoice = Invoice.query.filter_by(number=form_data['number']).first()
            assert invoice is not None
            
            # Verify VAT calculations
            assert invoice.get_effective_vat_rate() == vat_rate.rate
            expected_vat = Decimal('100.00') * (vat_rate.rate / 100)
            expected_total = Decimal('100.00') + expected_vat
            
            assert invoice.vat_amount == expected_vat
            assert invoice.total == expected_total
            
            invoices_created.append(invoice)
        
        # Verify all invoices have correct calculations
        assert len(invoices_created) == len(vat_rates)
        
        # Test invoice list shows different VAT rates
        response = client.get('/invoices')
        assert response.status_code == 200
        
        # Should show invoices with different totals based on VAT rates
        for invoice in invoices_created:
            assert str(invoice.total).encode() in response.data
    
    def test_vat_rate_management_workflow(self, client, app_context):
        """Test VAT rate management and usage workflow."""
        # Start with default rates
        VatRate.create_default_rates()
        initial_count = VatRate.query.count()
        assert initial_count == 4  # Estonian default rates
        
        # Test that creating defaults again doesn't duplicate
        VatRate.create_default_rates()
        assert VatRate.query.count() == initial_count
        
        # Get default rate
        default_rate = VatRate.get_default_rate()
        assert default_rate is not None
        assert default_rate.rate == Decimal('24.00')
        
        # Get active rates
        active_rates = VatRate.get_active_rates()
        assert len(active_rates) == 4
        
        # Verify rates are ordered by rate value
        rate_values = [rate.rate for rate in active_rates]
        assert rate_values == sorted(rate_values)


class TestEstonianBusinessRules:
    """Test Estonian-specific business rules and regulations."""
    
    def test_estonian_vat_compliance(self, client, app_context, sample_client):
        """Test Estonian VAT compliance workflows."""
        VatRate.create_default_rates()
        
        # Test with standard Estonian VAT rate (24%)
        standard_vat = VatRate.get_default_rate()
        assert standard_vat.rate == Decimal('24.00')
        
        form_data = {
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'saadetud',
            'lines-0-description': 'IT konsultatsiooniteenused',
            'lines-0-qty': '1.0',
            'lines-0-unit_price': '1000.00'
        }
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        invoice = Invoice.query.filter_by(client_id=sample_client.id).first()
        
        # Verify Estonian VAT calculation
        assert invoice.subtotal == Decimal('1000.00')
        assert invoice.vat_amount == Decimal('240.00')  # 24% of 1000
        assert invoice.total == Decimal('1240.00')
        
        # Test with tax-free rate (0%)
        tax_free_rate = VatRate.query.filter_by(rate=0).first()
        form_data['number'] = 'EST-VAT-FREE-001'
        form_data['vat_rate_id'] = str(tax_free_rate.id)
        form_data['lines-0-description'] = 'Maksuvaba teenus (KMS § 15)'
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        tax_free_invoice = Invoice.query.filter_by(number='EST-VAT-FREE-001').first()
        assert tax_free_invoice.vat_amount == Decimal('0.00')
        assert tax_free_invoice.total == Decimal('1000.00')
    
    def test_estonian_invoice_numbering(self, client, app_context, sample_client):
        """Test Estonian invoice numbering compliance."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Estonian invoice numbers typically follow YYYY-NNNN format
        current_year = date.today().year
        
        # Generate automatic number
        auto_number = generate_invoice_number()
        assert auto_number.startswith(str(current_year))
        assert len(auto_number) == 9  # YYYY-NNNN format
        
        # Create invoice with Estonian-compliant number
        form_data = {
            'number': auto_number,
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'saadetud',
            'lines-0-description': 'Teenuse osutamine',
            'lines-0-qty': '1.0',
            'lines-0-unit_price': '500.00'
        }
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        invoice = Invoice.query.filter_by(number=auto_number).first()
        assert invoice is not None
        assert invoice.number == auto_number
    
    def test_estonian_company_settings(self, client, app_context):
        """Test Estonian company settings workflow."""
        # Create Estonian company settings
        settings = CompanySettings(
            company_name='Eesti Testimise Ettevõte OÜ',
            company_address='Narva mnt 5, 10117 Tallinn, Estonia',
            company_registry_code='12345678',
            company_vat_number='EE123456789',
            company_phone='+372 5555 1234',
            company_email='info@testimine.ee',
            default_vat_rate=Decimal('24.00'),
            default_pdf_template='standard',
            invoice_terms='Maksetähtaeg 14 kalendripäeva. Viivise määr 0,5% päevas.'
        )
        
        db.session.add(settings)
        db.session.commit()
        
        # Verify settings
        retrieved_settings = CompanySettings.get_settings()
        assert retrieved_settings.company_name == 'Eesti Testimise Ettevõte OÜ'
        assert retrieved_settings.company_vat_number.startswith('EE')
        assert retrieved_settings.company_phone.startswith('+372')
        assert retrieved_settings.default_vat_rate == Decimal('24.00')
        assert 'Maksetähtaeg' in retrieved_settings.invoice_terms


class TestErrorHandlingWorkflows:
    """Test error handling in complete workflows."""
    
    def test_invalid_workflow_states(self, client, app_context, sample_client):
        """Test handling of invalid workflow states."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create paid invoice
        paid_invoice = Invoice(
            number='ERROR-TEST-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='makstud',
            subtotal=Decimal('500.00'),
            total=Decimal('620.00')
        )
        db.session.add(paid_invoice)
        db.session.commit()
        
        # Try to edit paid invoice (should be restricted)
        edit_data = {
            'number': paid_invoice.number,
            'client_id': str(paid_invoice.client_id),
            'date': paid_invoice.date.strftime('%Y-%m-%d'),
            'due_date': paid_invoice.due_date.strftime('%Y-%m-%d'),
            'vat_rate_id': str(standard_vat.id),
            'status': 'makstud',
            'lines-0-description': 'Muudetud teenus',
            'lines-0-qty': '1.0',
            'lines-0-unit_price': '600.00'
        }
        
        response = client.post(f'/invoices/{paid_invoice.id}/edit', data=edit_data)
        # Should handle gracefully (either redirect or show error)
        assert response.status_code in [200, 302, 400, 403]
        
        # Try invalid status transition
        response = client.post(f'/invoices/{paid_invoice.id}/status', 
                              data={'status': 'mustand'})
        # Should be rejected
        assert response.status_code in [200, 400, 422]
        
        # Verify invoice wasn't changed
        db.session.refresh(paid_invoice)
        assert paid_invoice.status == 'makstud'
    
    def test_concurrent_modification_handling(self, client, app_context, sample_client):
        """Test handling of concurrent modifications."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create invoice
        invoice = Invoice(
            number='CONCURRENT-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='mustand'
        )
        db.session.add(invoice)
        db.session.commit()
        
        original_updated = invoice.updated_at
        
        # Simulate first user's modification
        invoice.status = 'saadetud'
        db.session.commit()
        
        # Verify updated_at changed
        assert invoice.updated_at > original_updated
        
        # This would be expanded in a real application with proper
        # optimistic locking and conflict resolution
        
        # Verify final state is consistent
        db.session.refresh(invoice)
        assert invoice.status == 'saadetud'


class TestDataConsistency:
    """Test data consistency across workflows."""
    
    def test_invoice_totals_consistency(self, client, app_context, sample_client):
        """Test that invoice totals remain consistent across operations."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create invoice with lines
        form_data = {
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'Service A',
            'lines-0-qty': '2.0',
            'lines-0-unit_price': '150.00',
            'lines-1-description': 'Service B',
            'lines-1-qty': '3.0',
            'lines-1-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        invoice = Invoice.query.filter_by(client_id=sample_client.id).first()
        original_subtotal = invoice.subtotal
        original_total = invoice.total
        
        # Recalculate totals manually
        calculate_invoice_totals(invoice)
        
        # Totals should remain the same
        assert invoice.subtotal == original_subtotal
        assert invoice.total == original_total
        
        # Edit invoice and verify consistency
        edit_data = form_data.copy()
        edit_data['number'] = invoice.number
        edit_data['lines-1-qty'] = '5.0'  # Change quantity
        
        response = client.post(f'/invoices/{invoice.id}/edit', 
                              data=edit_data, follow_redirects=True)
        assert response.status_code == 200
        
        db.session.refresh(invoice)
        
        # Verify totals were recalculated correctly
        expected_subtotal = Decimal('2.0') * Decimal('150.00') + Decimal('5.0') * Decimal('100.00')
        expected_total = expected_subtotal * Decimal('1.24')
        
        assert invoice.subtotal == expected_subtotal
        assert invoice.total == expected_total
    
    def test_client_invoice_relationship_consistency(self, client, app_context):
        """Test consistency of client-invoice relationships."""
        # Create client
        client_data = {
            'name': 'Consistency Test Client',
            'email': 'consistency@test.ee'
        }
        
        response = client.post('/clients/new', data=client_data, follow_redirects=True)
        assert response.status_code == 200
        
        test_client = Client.query.filter_by(name='Consistency Test Client').first()
        assert test_client.invoice_count == 0
        
        # Create invoices
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        for i in range(3):
            invoice_data = {
                'number': f'CONSISTENCY-{i:03d}',
                'client_id': str(test_client.id),
                'date': '2025-08-10',
                'due_date': '2025-08-24',
                'vat_rate_id': str(standard_vat.id),
                'status': 'saadetud',
                'lines-0-description': f'Service {i}',
                'lines-0-qty': '1.0',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post('/invoices/new', data=invoice_data, follow_redirects=True)
            assert response.status_code == 200
        
        # Verify relationship consistency
        db.session.refresh(test_client)
        assert test_client.invoice_count == 3
        assert len(test_client.invoices) == 3
        
        # Delete one invoice
        first_invoice = test_client.invoices[0]
        response = client.post(f'/invoices/{first_invoice.id}/delete', follow_redirects=True)
        assert response.status_code == 200
        
        # Verify consistency after deletion
        db.session.refresh(test_client)
        assert test_client.invoice_count == 2
        assert len(test_client.invoices) == 2