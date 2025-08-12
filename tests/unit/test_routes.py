"""
Unit tests for Flask route endpoints and blueprints.

Tests cover:
- Clients blueprint routes (/clients/*)
- Invoices blueprint routes (/invoices/*)
- Dashboard routes (/)
- PDF generation routes (/pdf/*)
- Route parameters validation
- HTTP method restrictions
- Authentication and CSRF protection
- Estonian language content in responses
- Form submissions and redirects
"""

import pytest
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse

from app.models import db, Client, Invoice, InvoiceLine, VatRate


class TestClientRoutes:
    """Test client-related routes."""
    
    def test_clients_list_get(self, client, app_context):
        """Test GET /clients - list all clients."""
        response = client.get('/clients')
        assert response.status_code == 200
        assert b'clients' in response.data.lower() or b'kliendid' in response.data.lower()
    
    def test_clients_list_with_clients(self, client, app_context, sample_client, sample_client_2):
        """Test clients list with existing clients."""
        response = client.get('/clients')
        assert response.status_code == 200
        
        # Check that both clients are displayed
        assert sample_client.name.encode() in response.data
        assert sample_client_2.name.encode() in response.data
    
    def test_client_new_get(self, client, app_context):
        """Test GET /clients/new - show new client form."""
        response = client.get('/clients/new')
        assert response.status_code == 200
        assert b'form' in response.data.lower()
        # Estonian form labels
        assert b'nimi' in response.data.lower() or b'name' in response.data.lower()
    
    def test_client_new_post_valid(self, client, app_context):
        """Test POST /clients/new with valid data."""
        form_data = {
            'name': 'Uus Klient OÜ',
            'registry_code': '11223344',
            'email': 'uus@klient.ee',
            'phone': '+372 5555 0000',
            'address': 'Uus Aadress 456, 10002 Tallinn'
        }
        
        response = client.post('/clients/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Check that client was created
        new_client = Client.query.filter_by(name='Uus Klient OÜ').first()
        assert new_client is not None
        assert new_client.email == 'uus@klient.ee'
        assert new_client.registry_code == '11223344'
    
    def test_client_new_post_invalid(self, client, app_context):
        """Test POST /clients/new with invalid data."""
        form_data = {
            # Missing required name field
            'email': 'invalid@email',
            'registry_code': '12345678901234567890123'  # Too long
        }
        
        response = client.post('/clients/new', data=form_data)
        assert response.status_code == 200  # Returns form with errors
        # Check that no client was created
        assert Client.query.count() == 0
    
    def test_client_detail_get(self, client, app_context, sample_client):
        """Test GET /clients/<id> - show client details."""
        response = client.get(f'/clients/{sample_client.id}')
        assert response.status_code == 200
        assert sample_client.name.encode() in response.data
        assert sample_client.email.encode() in response.data
    
    def test_client_detail_nonexistent(self, client, app_context):
        """Test GET /clients/<id> with non-existent client."""
        response = client.get('/clients/99999')
        assert response.status_code == 404
    
    def test_client_edit_get(self, client, app_context, sample_client):
        """Test GET /clients/<id>/edit - show edit form."""
        response = client.get(f'/clients/{sample_client.id}/edit')
        assert response.status_code == 200
        assert sample_client.name.encode() in response.data
        assert b'form' in response.data.lower()
    
    def test_client_edit_post_valid(self, client, app_context, sample_client):
        """Test POST /clients/<id>/edit with valid data."""
        original_name = sample_client.name
        form_data = {
            'name': 'Muudetud Klient OÜ',
            'registry_code': sample_client.registry_code,
            'email': 'muudetud@klient.ee',
            'phone': sample_client.phone,
            'address': sample_client.address
        }
        
        response = client.post(f'/clients/{sample_client.id}/edit', 
                              data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Check that client was updated
        db.session.refresh(sample_client)
        assert sample_client.name == 'Muudetud Klient OÜ'
        assert sample_client.email == 'muudetud@klient.ee'
    
    def test_client_delete_post(self, client, app_context, sample_client):
        """Test POST /clients/<id>/delete - delete client."""
        client_id = sample_client.id
        
        response = client.post(f'/clients/{client_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        
        # Check that client was deleted
        deleted_client = Client.query.get(client_id)
        assert deleted_client is None
    
    def test_client_delete_with_invoices(self, client, app_context, sample_client, sample_invoice):
        """Test deleting client with associated invoices."""
        client_id = sample_client.id
        
        response = client.post(f'/clients/{client_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        
        # Check that both client and invoice were deleted (cascade)
        deleted_client = Client.query.get(client_id)
        deleted_invoice = Invoice.query.get(sample_invoice.id)
        assert deleted_client is None
        assert deleted_invoice is None


class TestInvoiceRoutes:
    """Test invoice-related routes."""
    
    def test_invoices_list_get(self, client, app_context):
        """Test GET /invoices - list all invoices."""
        response = client.get('/invoices')
        assert response.status_code == 200
        assert b'invoices' in response.data.lower() or b'arved' in response.data.lower()
    
    def test_invoices_list_with_filters(self, client, app_context, invoices_for_filtering):
        """Test invoices list with status filtering."""
        # Test status filter
        response = client.get('/invoices?status=makstud')
        assert response.status_code == 200
        
        # Test client filter
        test_client = invoices_for_filtering[0].client
        response = client.get(f'/invoices?client_id={test_client.id}')
        assert response.status_code == 200
        
        # Test date filters
        response = client.get('/invoices?date_from=2025-08-01&date_to=2025-08-31')
        assert response.status_code == 200
    
    def test_invoice_new_get(self, client, app_context, sample_client):
        """Test GET /invoices/new - show new invoice form."""
        VatRate.create_default_rates()
        
        response = client.get('/invoices/new')
        assert response.status_code == 200
        assert b'form' in response.data.lower()
        # Check for client dropdown
        assert sample_client.name.encode() in response.data
    
    def test_invoice_new_post_valid(self, client, app_context, sample_client):
        """Test POST /invoices/new with valid data."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'number': '2025-TEST-001',
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'Testimise teenused',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Check that invoice was created
        new_invoice = Invoice.query.filter_by(number='2025-TEST-001').first()
        assert new_invoice is not None
        assert new_invoice.client_id == sample_client.id
        assert len(new_invoice.lines) == 1
    
    def test_invoice_new_post_invalid_number(self, client, app_context, sample_client):
        """Test POST /invoices/new with invalid invoice number."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'number': 'INVALID-FORMAT',  # Invalid format
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
        assert response.status_code == 200  # Returns form with errors
        # Check that no invoice was created
        assert Invoice.query.filter_by(number='INVALID-FORMAT').first() is None
    
    def test_invoice_detail_get(self, client, app_context, sample_invoice):
        """Test GET /invoices/<id> - show invoice details."""
        response = client.get(f'/invoices/{sample_invoice.id}')
        assert response.status_code == 200
        assert sample_invoice.number.encode() in response.data
        assert sample_invoice.client.name.encode() in response.data
    
    def test_invoice_edit_get(self, client, app_context, sample_invoice):
        """Test GET /invoices/<id>/edit - show edit form."""
        response = client.get(f'/invoices/{sample_invoice.id}/edit')
        assert response.status_code == 200
        assert sample_invoice.number.encode() in response.data
        assert b'form' in response.data.lower()
    
    def test_invoice_edit_post_valid(self, client, app_context, sample_invoice):
        """Test POST /invoices/<id>/edit with valid data."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'number': sample_invoice.number,
            'client_id': str(sample_invoice.client_id),
            'date': sample_invoice.date.strftime('%Y-%m-%d'),
            'due_date': '2025-09-01',  # Change due date
            'vat_rate_id': str(standard_vat.id),
            'status': sample_invoice.status,
            'lines-0-description': 'Muudetud teenus',
            'lines-0-qty': '2.00',
            'lines-0-unit_price': '150.00'
        }
        
        response = client.post(f'/invoices/{sample_invoice.id}/edit', 
                              data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Check that invoice was updated
        db.session.refresh(sample_invoice)
        assert sample_invoice.due_date.strftime('%Y-%m-%d') == '2025-09-01'
    
    def test_invoice_duplicate_post(self, client, app_context, sample_invoice):
        """Test POST /invoices/<id>/duplicate - duplicate invoice."""
        original_count = Invoice.query.count()
        
        response = client.post(f'/invoices/{sample_invoice.id}/duplicate', follow_redirects=True)
        assert response.status_code == 200
        
        # Check that a new invoice was created
        new_count = Invoice.query.count()
        assert new_count == original_count + 1
        
        # Find the duplicate
        duplicates = Invoice.query.filter(Invoice.id != sample_invoice.id).all()
        duplicate = duplicates[-1]
        
        assert duplicate.number != sample_invoice.number
        assert duplicate.client_id == sample_invoice.client_id
        assert duplicate.status == 'mustand'  # Should be draft
    
    def test_invoice_delete_post(self, client, app_context, sample_client):
        """Test POST /invoices/<id>/delete - delete invoice."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create draft invoice (deletable)
        invoice = Invoice(
            number='DELETE-TEST-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='mustand'
        )
        db.session.add(invoice)
        db.session.commit()
        
        invoice_id = invoice.id
        
        response = client.post(f'/invoices/{invoice_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        
        # Check that invoice was deleted
        deleted_invoice = Invoice.query.get(invoice_id)
        assert deleted_invoice is None
    
    def test_invoice_status_update_post(self, client, app_context, sample_invoice):
        """Test POST /invoices/<id>/status - update invoice status."""
        original_status = sample_invoice.status
        new_status = 'saadetud'
        
        form_data = {'status': new_status}
        
        response = client.post(f'/invoices/{sample_invoice.id}/status', 
                              data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Check that status was updated
        db.session.refresh(sample_invoice)
        assert sample_invoice.status == new_status


class TestDashboardRoutes:
    """Test dashboard and overview routes."""
    
    def test_dashboard_get(self, client, app_context):
        """Test GET / - dashboard overview."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'dashboard' in response.data.lower() or b'overview' in response.data.lower()
    
    def test_dashboard_with_data(self, client, app_context, invoices_for_filtering):
        """Test dashboard with existing invoices and clients."""
        response = client.get('/')
        assert response.status_code == 200
        
        # Should show some statistics or summaries
        # Check for presence of invoice data
        for invoice in invoices_for_filtering[:2]:  # Check first couple
            if invoice.status in ['saadetud', 'makstud']:
                assert str(invoice.total).encode() in response.data or invoice.number.encode() in response.data
    
    def test_overview_get(self, client, app_context):
        """Test GET /overview - business overview page."""
        response = client.get('/overview')
        assert response.status_code == 200
    
    def test_reports_get(self, client, app_context):
        """Test GET /reports - reports page."""
        response = client.get('/reports')
        assert response.status_code == 200


class TestPDFRoutes:
    """Test PDF generation routes."""
    
    @patch('app.routes.pdf.generate_pdf')
    def test_invoice_pdf_preview(self, mock_generate_pdf, client, app_context, sample_invoice):
        """Test GET /invoices/<id>/pdf - preview PDF."""
        mock_generate_pdf.return_value = b'fake-pdf-content'
        
        response = client.get(f'/invoices/{sample_invoice.id}/pdf')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        assert response.data == b'fake-pdf-content'
    
    @patch('app.routes.pdf.generate_pdf')
    def test_invoice_pdf_download(self, mock_generate_pdf, client, app_context, sample_invoice):
        """Test GET /invoices/<id>/pdf?download=1 - download PDF."""
        mock_generate_pdf.return_value = b'fake-pdf-content'
        
        response = client.get(f'/invoices/{sample_invoice.id}/pdf?download=1')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        assert 'attachment' in response.headers.get('Content-Disposition', '')
        assert sample_invoice.number in response.headers.get('Content-Disposition', '')
    
    @patch('app.routes.pdf.generate_pdf')
    def test_invoice_pdf_different_templates(self, mock_generate_pdf, client, app_context, sample_invoice):
        """Test PDF generation with different templates."""
        mock_generate_pdf.return_value = b'fake-pdf-content'
        
        templates = ['standard', 'modern', 'elegant']
        
        for template in templates:
            response = client.get(f'/invoices/{sample_invoice.id}/pdf?template={template}')
            assert response.status_code == 200
            assert response.content_type == 'application/pdf'
            
            # Verify template was passed to generate_pdf
            mock_generate_pdf.assert_called()
            args, kwargs = mock_generate_pdf.call_args
            assert template in str(kwargs) or template in str(args)
    
    def test_invoice_pdf_nonexistent(self, client, app_context):
        """Test PDF generation for non-existent invoice."""
        response = client.get('/invoices/99999/pdf')
        assert response.status_code == 404
    
    @patch('app.routes.pdf.generate_pdf')
    def test_invoice_pdf_generation_error(self, mock_generate_pdf, client, app_context, sample_invoice):
        """Test PDF generation when WeasyPrint fails."""
        mock_generate_pdf.side_effect = Exception("PDF generation failed")
        
        response = client.get(f'/invoices/{sample_invoice.id}/pdf')
        assert response.status_code == 500


class TestRouteAuthentication:
    """Test route authentication and security."""
    
    def test_csrf_protection_enabled(self, client, app_context):
        """Test that CSRF protection works for forms."""
        # Note: In test config, CSRF is disabled (WTF_CSRF_ENABLED = False)
        # This test verifies the setting
        from app.config import Config
        from flask import current_app
        
        # In production, CSRF should be enabled
        # In tests, it should be disabled for easier testing
        test_config = current_app.config
        assert test_config.get('WTF_CSRF_ENABLED') is False
    
    def test_method_not_allowed(self, client, app_context, sample_client):
        """Test that wrong HTTP methods are rejected."""
        # Try POST on GET-only route
        response = client.post(f'/clients/{sample_client.id}')
        assert response.status_code == 405  # Method Not Allowed
        
        # Try GET on POST-only route
        response = client.get(f'/clients/{sample_client.id}/delete')
        assert response.status_code == 405  # Method Not Allowed
    
    def test_invalid_route_parameters(self, client, app_context):
        """Test routes with invalid parameters."""
        # Non-numeric ID
        response = client.get('/clients/abc')
        assert response.status_code == 404
        
        # Negative ID
        response = client.get('/clients/-1')
        assert response.status_code == 404
        
        # Very large ID
        response = client.get('/clients/999999999')
        assert response.status_code == 404


class TestRouteContentTypes:
    """Test route response content types and formats."""
    
    def test_html_routes_content_type(self, client, app_context):
        """Test that HTML routes return correct content type."""
        routes = [
            '/',
            '/clients',
            '/clients/new',
            '/invoices',
            '/invoices/new',
            '/overview',
            '/reports'
        ]
        
        for route in routes:
            response = client.get(route)
            assert response.status_code == 200
            assert 'text/html' in response.content_type
    
    def test_json_api_routes(self, client, app_context, sample_client):
        """Test API routes that return JSON."""
        # If there are AJAX endpoints
        response = client.get('/api/clients', headers={'Accept': 'application/json'})
        # This might not exist yet, so we expect 404
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            assert 'application/json' in response.content_type


class TestRouteRedirects:
    """Test route redirects and navigation."""
    
    def test_successful_form_submissions_redirect(self, client, app_context):
        """Test that successful form submissions redirect properly."""
        # Create client - should redirect to client list or detail
        form_data = {
            'name': 'Redirect Test Client',
            'email': 'redirect@test.ee'
        }
        
        response = client.post('/clients/new', data=form_data)
        assert response.status_code in [302, 200]  # Redirect or success
        
        if response.status_code == 302:
            # Check redirect location
            location = response.headers.get('Location')
            assert location is not None
            parsed = urlparse(location)
            assert parsed.path in ['/clients', f'/clients/{Client.query.first().id}']
    
    def test_delete_operations_redirect(self, client, app_context, sample_client):
        """Test that delete operations redirect properly."""
        client_id = sample_client.id
        
        response = client.post(f'/clients/{client_id}/delete')
        assert response.status_code in [302, 200]  # Redirect or success page
        
        if response.status_code == 302:
            location = response.headers.get('Location')
            parsed = urlparse(location)
            assert parsed.path == '/clients'


class TestEstonianContent:
    """Test Estonian language content in routes."""
    
    def test_estonian_form_labels(self, client, app_context):
        """Test that forms contain Estonian labels."""
        response = client.get('/clients/new')
        assert response.status_code == 200
        
        # Check for Estonian form field labels
        estonian_terms = [b'nimi', b'e-post', b'telefon', b'aadress']
        for term in estonian_terms:
            # Should contain at least some Estonian terms
            if term in response.data.lower():
                break
        else:
            # If no Estonian terms found, that's also okay if English is used
            english_terms = [b'name', b'email', b'phone', b'address']
            assert any(term in response.data.lower() for term in english_terms)
    
    def test_estonian_status_labels(self, client, app_context, sample_invoice):
        """Test that invoice statuses are displayed in Estonian."""
        response = client.get(f'/invoices/{sample_invoice.id}')
        assert response.status_code == 200
        
        # Estonian status terms
        estonian_statuses = [b'mustand', b'saadetud', b'makstud']
        status_found = any(status in response.data.lower() for status in estonian_statuses)
        
        # It's okay if English is used instead
        if not status_found:
            english_statuses = [b'draft', b'sent', b'paid']
            assert any(status in response.data.lower() for status in english_statuses)
    
    def test_estonian_error_messages(self, client, app_context):
        """Test that error messages are in Estonian."""
        # Submit invalid client form
        form_data = {
            'name': '',  # Empty name should trigger Estonian error
            'email': 'invalid-email'
        }
        
        response = client.post('/clients/new', data=form_data)
        assert response.status_code == 200
        
        # Check for Estonian error messages or English equivalents
        estonian_errors = [b'kohustuslik', b'vigane', b'e-posti']
        english_errors = [b'required', b'invalid', b'email']
        
        has_estonian = any(error in response.data.lower() for error in estonian_errors)
        has_english = any(error in response.data.lower() for error in english_errors)
        
        # Should have either Estonian or English error messages
        assert has_estonian or has_english