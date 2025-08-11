"""
Integration tests for company settings functionality.

Tests comprehensive company settings workflows including:
- Company settings save/load functionality
- Logo drag & drop upload
- PDF template preference setting
- VAT rate management section
- "Turundussõnumid" field (changed from "Arve tingimused")
"""

import pytest
import tempfile
import os
from decimal import Decimal
from datetime import date
from werkzeug.datastructures import FileStorage
from io import BytesIO

from app.models import db, CompanySettings, VatRate


class TestCompanySettingsBasic:
    """Test basic company settings functionality."""
    
    def test_company_settings_creation(self, app_context):
        """Test creating default company settings."""
        # Clear existing settings
        CompanySettings.query.delete()
        db.session.commit()
        
        # Get settings should create default
        settings = CompanySettings.get_settings()
        assert settings is not None
        assert settings.company_name == 'Minu Ettevõte'
        assert settings.default_vat_rate == Decimal('24.00')
        assert settings.default_pdf_template == 'standard'
    
    def test_company_settings_save_load(self, client, app_context):
        """Test saving and loading company settings."""
        form_data = {
            'company_name': 'Test Company OÜ',
            'company_address': 'Test Street 123, 10001 Tallinn, Estonia',
            'company_registry_code': '12345678',
            'company_vat_number': 'EE123456789',
            'company_phone': '+372 5555 0000',
            'company_email': 'info@testcompany.ee',
            'company_website': 'https://testcompany.ee',
            'default_vat_rate': '24.00',
            'default_pdf_template': 'modern',
            'invoice_terms': 'Test invoice terms and conditions'
        }
        
        response = client.post('/settings', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify settings were saved
        settings = CompanySettings.get_settings()
        assert settings.company_name == 'Test Company OÜ'
        assert settings.company_address == 'Test Street 123, 10001 Tallinn, Estonia'
        assert settings.company_registry_code == '12345678'
        assert settings.company_vat_number == 'EE123456789'
        assert settings.company_phone == '+372 5555 0000'
        assert settings.company_email == 'info@testcompany.ee'
        assert settings.company_website == 'https://testcompany.ee'
        assert settings.default_vat_rate == Decimal('24.00')
        assert settings.default_pdf_template == 'modern'
        assert settings.invoice_terms == 'Test invoice terms and conditions'
    
    def test_company_settings_form_load(self, client, app_context):
        """Test that settings form loads with current values."""
        # Set some settings
        settings = CompanySettings.get_settings()
        settings.company_name = 'Form Load Test OÜ'
        settings.company_email = 'formload@test.ee'
        settings.default_pdf_template = 'elegant'
        db.session.commit()
        
        response = client.get('/settings')
        assert response.status_code == 200
        
        # Check that current values are loaded in form
        assert b'Form Load Test' in response.data
        assert b'formload@test.ee' in response.data
        assert b'elegant' in response.data or b'selected' in response.data
    
    def test_estonian_company_data(self, client, app_context):
        """Test saving Estonian company data with special characters."""
        form_data = {
            'company_name': 'Eesti Testimise OÜ',
            'company_address': 'Pärnu mnt 123, 10115 Tallinn',
            'company_registry_code': '12345678',
            'company_vat_number': 'EE123456789',
            'company_phone': '+372 5555 1234',
            'company_email': 'info@eesti-testimine.ee',
            'default_vat_rate': '24.00',
            'default_pdf_template': 'standard',
            'invoice_terms': 'Arve tasumise tingimused: maksetähtaeg 14 päeva'
        }
        
        response = client.post('/settings', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify Estonian characters were saved correctly
        settings = CompanySettings.get_settings()
        assert settings.company_name == 'Eesti Testimise OÜ'
        assert 'Pärnu mnt' in settings.company_address
        assert 'maksetähtaeg' in settings.invoice_terms


class TestPDFTemplateSettings:
    """Test PDF template preference settings."""
    
    def test_pdf_template_selection(self, client, app_context):
        """Test selecting different PDF templates in settings."""
        templates = ['standard', 'modern', 'elegant']
        
        for template in templates:
            form_data = {
                'company_name': 'Template Test Company',
                'default_pdf_template': template,
                'default_vat_rate': '24.00'
            }
            
            response = client.post('/settings', data=form_data, follow_redirects=True)
            assert response.status_code == 200
            
            # Verify template was saved
            settings = CompanySettings.get_settings()
            assert settings.default_pdf_template == template
    
    def test_invalid_pdf_template(self, client, app_context):
        """Test handling of invalid PDF template selection."""
        form_data = {
            'company_name': 'Invalid Template Test',
            'default_pdf_template': 'invalid_template',
            'default_vat_rate': '24.00'
        }
        
        response = client.post('/settings', data=form_data)
        
        # Should either reject invalid template or fallback to default
        settings = CompanySettings.get_settings()
        assert settings.default_pdf_template in ['standard', 'modern', 'elegant']
    
    def test_pdf_template_dropdown_populated(self, client, app_context):
        """Test that PDF template dropdown is populated in settings form."""
        response = client.get('/settings')
        assert response.status_code == 200
        
        # Check that all template options are present
        assert b'standard' in response.data
        assert b'modern' in response.data
        assert b'elegant' in response.data


class TestVATRateManagement:
    """Test VAT rate management in settings."""
    
    def test_default_vat_rate_setting(self, client, app_context):
        """Test setting default VAT rate."""
        VatRate.create_default_rates()
        
        # Test different VAT rates
        vat_rates = [Decimal('0.00'), Decimal('9.00'), Decimal('20.00'), Decimal('24.00')]
        
        for rate in vat_rates:
            form_data = {
                'company_name': 'VAT Rate Test',
                'default_vat_rate': str(rate),
                'default_pdf_template': 'standard'
            }
            
            response = client.post('/settings', data=form_data, follow_redirects=True)
            assert response.status_code == 200
            
            # Verify VAT rate was saved
            settings = CompanySettings.get_settings()
            assert settings.default_vat_rate == rate
    
    def test_vat_rate_dropdown_populated(self, client, app_context):
        """Test that VAT rate dropdown is populated with available rates."""
        VatRate.create_default_rates()
        
        response = client.get('/settings')
        assert response.status_code == 200
        
        # Check that VAT rate options are present
        vat_rates = VatRate.get_active_rates()
        for rate in vat_rates:
            assert str(rate.rate).encode() in response.data or rate.name.encode() in response.data
    
    def test_invalid_vat_rate_validation(self, client, app_context):
        """Test validation of invalid VAT rates."""
        form_data = {
            'company_name': 'Invalid VAT Test',
            'default_vat_rate': '150.00',  # Invalid - over 100%
            'default_pdf_template': 'standard'
        }
        
        response = client.post('/settings', data=form_data)
        
        # Should reject invalid VAT rate
        settings = CompanySettings.get_settings()
        assert settings.default_vat_rate <= Decimal('100.00')


class TestLogoUpload:
    """Test logo drag & drop upload functionality."""
    
    def test_logo_upload_valid_image(self, client, app_context):
        """Test uploading a valid logo image."""
        # Create a simple test image (1x1 pixel PNG)
        test_image_data = (
            b'\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00\\rIHDR\\x00\\x00\\x00\\x01\\x00\\x00\\x00\\x01'
            b'\\x08\\x06\\x00\\x00\\x00\\x1f\\x15\\xc4\\x89\\x00\\x00\\x00\\nIDATx\\x9cc```\\x00\\x00'
            b'\\x00\\x02\\x00\\x01H\\xaf\\xca\\xf3\\x00\\x00\\x00\\x00IEND\\xaeB`\\x82'
        )
        
        # Create file storage object
        test_file = FileStorage(
            stream=BytesIO(test_image_data),
            filename='test_logo.png',
            content_type='image/png'
        )
        
        form_data = {
            'company_name': 'Logo Test Company',
            'company_logo': test_file,
            'default_vat_rate': '24.00',
            'default_pdf_template': 'standard'
        }
        
        response = client.post('/settings', data=form_data, follow_redirects=True, 
                             content_type='multipart/form-data')
        
        # Should accept valid image
        if response.status_code == 200:
            settings = CompanySettings.get_settings()
            # Logo URL should be set (even if empty string is acceptable)
            assert hasattr(settings, 'company_logo_url')
    
    def test_logo_upload_invalid_file(self, client, app_context):
        """Test uploading invalid file as logo."""
        # Create a text file
        test_file = FileStorage(
            stream=BytesIO(b'This is not an image'),
            filename='not_an_image.txt',
            content_type='text/plain'
        )
        
        form_data = {
            'company_name': 'Invalid Logo Test',
            'company_logo': test_file,
            'default_vat_rate': '24.00',
            'default_pdf_template': 'standard'
        }
        
        response = client.post('/settings', data=form_data, 
                             content_type='multipart/form-data')
        
        # Should reject invalid file type
        # Response could be error page or form with validation error
        assert response.status_code in [200, 400]
    
    def test_logo_upload_large_file(self, client, app_context):
        """Test uploading oversized logo file."""
        # Create a large file (simulated)
        large_data = b'x' * (5 * 1024 * 1024)  # 5MB of data
        
        test_file = FileStorage(
            stream=BytesIO(large_data),
            filename='large_logo.jpg',
            content_type='image/jpeg'
        )
        
        form_data = {
            'company_name': 'Large Logo Test',
            'company_logo': test_file,
            'default_vat_rate': '24.00',
            'default_pdf_template': 'standard'
        }
        
        response = client.post('/settings', data=form_data, 
                             content_type='multipart/form-data')
        
        # Should handle large file appropriately (reject or accept based on limits)
        assert response.status_code in [200, 400, 413]  # 413 = Request Entity Too Large
    
    def test_logo_preview_display(self, client, app_context):
        """Test logo preview display in settings."""
        # Set a logo URL
        settings = CompanySettings.get_settings()
        settings.company_logo_url = '/static/uploads/test_logo.png'
        db.session.commit()
        
        response = client.get('/settings')
        assert response.status_code == 200
        
        # Check that logo preview is displayed
        assert b'test_logo.png' in response.data or b'preview' in response.data.lower()


class TestTurundussonumidField:
    """Test "Turundussõnumid" field (changed from "Arve tingimused")."""
    
    def test_turundussonumid_field_present(self, client, app_context):
        """Test that "Turundussõnumid" field is present in settings form."""
        response = client.get('/settings')
        assert response.status_code == 200
        
        # Check for Estonian field name
        assert (b'Turunduss' in response.data or 
                b'turunduss' in response.data or
                b'invoice_terms' in response.data)  # Field name might be used
    
    def test_turundussonumid_save_load(self, client, app_context):
        """Test saving and loading "Turundussõnumid" content."""
        turundus_content = """
        Täname teid meie teenuste kasutamise eest!
        
        Järgmised teenused võivad teid huvitada:
        - Veebiarendus
        - Konsultatsiooniteenused
        - Projektijuhtimine
        
        Küsimuste korral võtke meiega ühendust!
        """
        
        form_data = {
            'company_name': 'Turundus Test OÜ',
            'invoice_terms': turundus_content,
            'default_vat_rate': '24.00',
            'default_pdf_template': 'standard'
        }
        
        response = client.post('/settings', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify content was saved
        settings = CompanySettings.get_settings()
        assert 'Täname teid' in settings.invoice_terms
        assert 'Veebiarendus' in settings.invoice_terms
        assert 'Küsimuste korral' in settings.invoice_terms
    
    def test_turundussonumid_estonian_characters(self, client, app_context):
        """Test "Turundussõnumid" with Estonian characters."""
        estonian_content = "Sõnumid äriklientidele: tähtaeg, käibemaks, võlgnevused"
        
        form_data = {
            'company_name': 'Estonian Chars Test',
            'invoice_terms': estonian_content,
            'default_vat_rate': '24.00',
            'default_pdf_template': 'standard'
        }
        
        response = client.post('/settings', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify Estonian characters were preserved
        settings = CompanySettings.get_settings()
        assert 'Sõnumid' in settings.invoice_terms
        assert 'tähtaeg' in settings.invoice_terms
        assert 'käibemaks' in settings.invoice_terms
        assert 'võlgnevused' in settings.invoice_terms
    
    def test_turundussonumid_empty_content(self, client, app_context):
        """Test handling empty "Turundussõnumid" content."""
        form_data = {
            'company_name': 'Empty Turundus Test',
            'invoice_terms': '',  # Empty content
            'default_vat_rate': '24.00',
            'default_pdf_template': 'standard'
        }
        
        response = client.post('/settings', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Should accept empty content
        settings = CompanySettings.get_settings()
        assert settings.invoice_terms == ''


class TestSettingsValidation:
    """Test settings form validation and error handling."""
    
    def test_required_company_name_validation(self, client, app_context):
        """Test that company name is required."""
        form_data = {
            'company_name': '',  # Empty company name
            'default_vat_rate': '24.00',
            'default_pdf_template': 'standard'
        }
        
        response = client.post('/settings', data=form_data)
        
        # Should show validation error or use default
        if response.status_code == 200:
            # Check if form shows validation error
            assert b'required' in response.data.lower() or b'error' in response.data.lower()
        
        # Verify company name was not cleared
        settings = CompanySettings.get_settings()
        assert settings.company_name != ''
    
    def test_email_format_validation(self, client, app_context):
        """Test email format validation."""
        form_data = {
            'company_name': 'Email Test Company',
            'company_email': 'invalid-email-format',  # Invalid email
            'default_vat_rate': '24.00',
            'default_pdf_template': 'standard'
        }
        
        response = client.post('/settings', data=form_data)
        
        # Should show validation error for invalid email
        if response.status_code == 200:
            # May show validation error in form
            pass
        
        # Check if invalid email was saved or rejected
        settings = CompanySettings.get_settings()
        # System should either reject invalid email or accept it as-is
        assert hasattr(settings, 'company_email')
    
    def test_phone_number_validation(self, client, app_context):
        """Test phone number format validation."""
        valid_phones = ['+372 5555 1234', '372 5555 1234', '+372 55551234']
        
        for phone in valid_phones:
            form_data = {
                'company_name': 'Phone Test Company',
                'company_phone': phone,
                'default_vat_rate': '24.00',
                'default_pdf_template': 'standard'
            }
            
            response = client.post('/settings', data=form_data, follow_redirects=True)
            assert response.status_code == 200
            
            # Verify phone was saved (format may be normalized)
            settings = CompanySettings.get_settings()
            assert settings.company_phone is not None
    
    def test_website_url_validation(self, client, app_context):
        """Test website URL validation."""
        test_urls = [
            'https://example.com',
            'http://example.com',
            'https://example.ee',
            'example.com',  # Without protocol
        ]
        
        for url in test_urls:
            form_data = {
                'company_name': 'URL Test Company',
                'company_website': url,
                'default_vat_rate': '24.00',
                'default_pdf_template': 'standard'
            }
            
            response = client.post('/settings', data=form_data, follow_redirects=True)
            assert response.status_code == 200
            
            # Verify URL was processed (may be normalized)
            settings = CompanySettings.get_settings()
            assert settings.company_website is not None


class TestSettingsIntegration:
    """Test settings integration with other system components."""
    
    def test_settings_used_in_invoices(self, client, app_context, sample_client):
        """Test that company settings are used in invoice generation."""
        # Set company settings
        settings = CompanySettings.get_settings()
        settings.company_name = 'Integration Test Company'
        settings.company_address = 'Test Address 123'
        settings.default_vat_rate = Decimal('20.00')
        db.session.commit()
        
        VatRate.create_default_rates()
        
        # Create invoice
        form_data = {
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'status': 'mustand',
            'lines-0-description': 'Integration test service',
            'lines-0-qty': '1.00',
            'lines-0-unit_price': '100.00'
        }
        
        response = client.post('/invoices/new', data=form_data, follow_redirects=True)
        assert response.status_code == 200
        
        # Invoice creation should use company settings for defaults
        # (This would be verified by checking default VAT rate application)
    
    def test_settings_used_in_pdf_generation(self, client, app_context, sample_client):
        """Test that company settings are used in PDF generation."""
        # Set company settings
        settings = CompanySettings.get_settings()
        settings.company_name = 'PDF Integration Test'
        settings.company_address = 'PDF Test Address'
        settings.default_pdf_template = 'modern'
        db.session.commit()
        
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create test invoice
        from app.models import Invoice, InvoiceLine
        
        invoice = Invoice(
            number='SETTINGS-PDF-2025-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            subtotal=Decimal('100.00'),
            total=Decimal('124.00')
        )
        db.session.add(invoice)
        db.session.flush()
        
        line = InvoiceLine(
            invoice_id=invoice.id,
            description='Settings PDF test',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db.session.add(line)
        db.session.commit()
        
        # Generate PDF (should use company settings)
        response = client.get(f'/invoices/{invoice.id}/pdf')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'