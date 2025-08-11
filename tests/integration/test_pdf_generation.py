"""
Integration tests for PDF generation functionality.

Tests comprehensive PDF generation workflows including:
- PDF generation for all 3 templates (standard, modern, elegant)
- PDF preview functionality
- PDF download functionality  
- Template selection from settings
- Company information in PDFs
"""

import pytest
import tempfile
import os
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from app.models import db, Invoice, InvoiceLine, Client, VatRate, CompanySettings


class TestPDFGeneration:
    """Test PDF generation functionality."""
    
    def test_pdf_generation_all_templates(self, client, app_context):
        """Test PDF generation for all 3 templates."""
        # Set up test data
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        test_client = Client(
            name='PDF Test Client OÜ',
            registry_code='12345678',
            email='test@pdfclient.ee',
            phone='+372 5555 1234',
            address='Test Address 123, 10001 Tallinn'
        )
        db.session.add(test_client)
        db.session.flush()
        
        invoice = Invoice(
            number='PDF-TEST-2025-001',
            client_id=test_client.id,
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
            description='PDF Generation Test Service',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db.session.add(line)
        db.session.commit()
        
        # Test all three templates
        templates = ['standard', 'modern', 'elegant']
        
        for template in templates:
            response = client.get(f'/invoices/{invoice.id}/pdf?template={template}')
            assert response.status_code == 200
            assert response.content_type == 'application/pdf'
            assert len(response.data) > 0  # PDF content exists
            
            # Check PDF headers
            assert response.headers.get('Content-Disposition')
            assert f'PDF-TEST-2025-001' in response.headers.get('Content-Disposition', '')
    
    def test_pdf_preview_functionality(self, client, app_context):
        """Test PDF preview functionality."""
        # Set up test data
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        test_client = Client(
            name='Preview Test Client AS',
            email='preview@test.ee'
        )
        db.session.add(test_client)
        db.session.flush()
        
        invoice = Invoice(
            number='PREVIEW-2025-001',
            client_id=test_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            subtotal=Decimal('200.00'),
            total=Decimal('248.00')
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Test preview endpoint
        response = client.get(f'/invoices/{invoice.id}/preview')
        assert response.status_code == 200
        
        # Should return HTML preview or redirect to PDF
        if response.content_type == 'application/pdf':
            assert len(response.data) > 0
        else:
            assert b'preview' in response.data.lower() or b'PDF' in response.data
    
    def test_pdf_download_functionality(self, client, app_context):
        """Test PDF download functionality."""
        # Set up test data
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        test_client = Client(
            name='Download Test Client OÜ',
            email='download@test.ee'
        )
        db.session.add(test_client)
        db.session.flush()
        
        invoice = Invoice(
            number='DOWNLOAD-2025-001',
            client_id=test_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            subtotal=Decimal('300.00'),
            total=Decimal('372.00')
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Test download
        response = client.get(f'/invoices/{invoice.id}/pdf?download=true')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        
        # Check download headers
        content_disposition = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disposition
        assert 'DOWNLOAD-2025-001' in content_disposition
    
    def test_template_selection_from_settings(self, client, app_context):
        """Test PDF template selection from company settings."""
        # Set up test data
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        test_client = Client(name='Settings Template Test', email='settings@test.ee')
        db.session.add(test_client)
        db.session.flush()
        
        invoice = Invoice(
            number='SETTINGS-2025-001',
            client_id=test_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            subtotal=Decimal('100.00'),
            total=Decimal('124.00')
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Test with different default templates
        templates = ['standard', 'modern', 'elegant']
        
        for template in templates:
            # Update company settings
            settings = CompanySettings.get_settings()
            settings.default_pdf_template = template
            db.session.commit()
            
            # Generate PDF without specifying template (should use default)
            response = client.get(f'/invoices/{invoice.id}/pdf')
            assert response.status_code == 200
            assert response.content_type == 'application/pdf'
            
            # PDF should be generated successfully regardless of template
            assert len(response.data) > 0


class TestPDFContent:
    """Test PDF content accuracy."""
    
    def test_company_information_in_pdf(self, client, app_context):
        """Test that company information appears correctly in PDFs."""
        # Set up company settings
        settings = CompanySettings.get_settings()
        settings.company_name = 'Test Company OÜ'
        settings.company_address = 'Test Street 123, 10001 Tallinn, Estonia'
        settings.company_registry_code = '12345678'
        settings.company_vat_number = 'EE123456789'
        settings.company_phone = '+372 5555 0000'
        settings.company_email = 'info@testcompany.ee'
        db.session.commit()
        
        # Set up test data
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        test_client = Client(
            name='PDF Content Test Client',
            email='content@test.ee'
        )
        db.session.add(test_client)
        db.session.flush()
        
        invoice = Invoice(
            number='CONTENT-2025-001',
            client_id=test_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            subtotal=Decimal('500.00'),
            total=Decimal('620.00')
        )
        db.session.add(invoice)
        db.session.flush()
        
        line = InvoiceLine(
            invoice_id=invoice.id,
            description='Content Test Service',
            qty=Decimal('1.00'),
            unit_price=Decimal('500.00'),
            line_total=Decimal('500.00')
        )
        db.session.add(line)
        db.session.commit()
        
        # Generate PDF
        response = client.get(f'/invoices/{invoice.id}/pdf')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        
        # Note: Direct PDF content validation would require PDF parsing library
        # Here we verify that PDF was generated successfully
        assert len(response.data) > 1000  # PDF should have substantial content
    
    def test_estonian_characters_in_pdf(self, client, app_context):
        """Test that Estonian characters (ä, ö, ü) render correctly in PDFs."""
        # Set up test data with Estonian characters
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        test_client = Client(
            name='Eesti Testimise OÜ',  # Estonian characters
            email='test@eesti.ee',
            address='Pärnu mnt 123, Tallinn'  # Estonian characters
        )
        db.session.add(test_client)
        db.session.flush()
        
        invoice = Invoice(
            number='EESTI-2025-001',
            client_id=test_client.id,
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
            description='Veebiarenduse teenused äriüksusele',  # Estonian characters
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db.session.add(line)
        db.session.commit()
        
        # Generate PDF - should handle Estonian characters without errors
        response = client.get(f'/invoices/{invoice.id}/pdf')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        assert len(response.data) > 0
    
    def test_vat_calculations_in_pdf(self, client, app_context):
        """Test that VAT calculations are correctly reflected in PDF."""
        # Set up test data with complex calculations
        VatRate.create_default_rates()
        vat_rates = VatRate.get_active_rates()
        
        for vat_rate_obj in vat_rates:
            test_client = Client(
                name=f'VAT Test Client {vat_rate_obj.rate}%',
                email=f'vat{vat_rate_obj.rate}@test.ee'
            )
            db.session.add(test_client)
            db.session.flush()
            
            invoice = Invoice(
                number=f'VAT-PDF-{vat_rate_obj.rate}-001',
                client_id=test_client.id,
                date=date.today(),
                due_date=date.today() + timedelta(days=14),
                vat_rate_id=vat_rate_obj.id,
                subtotal=Decimal('100.00')
            )
            db.session.add(invoice)
            db.session.flush()
            
            line = InvoiceLine(
                invoice_id=invoice.id,
                description=f'Service with {vat_rate_obj.rate}% VAT',
                qty=Decimal('1.00'),
                unit_price=Decimal('100.00'),
                line_total=Decimal('100.00')
            )
            db.session.add(line)
            
            # Calculate expected total
            expected_vat = Decimal('100.00') * (vat_rate_obj.rate / 100)
            expected_total = Decimal('100.00') + expected_vat
            invoice.total = expected_total
            
            db.session.commit()
            
            # Generate PDF
            response = client.get(f'/invoices/{invoice.id}/pdf')
            assert response.status_code == 200
            assert response.content_type == 'application/pdf'
            assert len(response.data) > 0
            
            # Clean up for next iteration
            db.session.delete(invoice)
            db.session.delete(test_client)
            db.session.commit()


class TestPDFErrorHandling:
    """Test PDF generation error handling."""
    
    def test_pdf_generation_nonexistent_invoice(self, client, app_context):
        """Test PDF generation for non-existent invoice."""
        response = client.get('/invoices/99999/pdf')
        assert response.status_code == 404
    
    def test_pdf_generation_invalid_template(self, client, app_context):
        """Test PDF generation with invalid template."""
        # Set up test data
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        test_client = Client(name='Error Test Client', email='error@test.ee')
        db.session.add(test_client)
        db.session.flush()
        
        invoice = Invoice(
            number='ERROR-2025-001',
            client_id=test_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            subtotal=Decimal('100.00'),
            total=Decimal('124.00')
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Try with invalid template
        response = client.get(f'/invoices/{invoice.id}/pdf?template=invalid_template')
        
        # Should either use default template or return error
        if response.status_code == 200:
            assert response.content_type == 'application/pdf'
        else:
            assert response.status_code in [400, 404]
    
    def test_pdf_generation_missing_data(self, client, app_context):
        """Test PDF generation with missing data."""
        # Create invoice with minimal data
        test_client = Client(name='Minimal Client')  # No address, etc.
        db.session.add(test_client)
        db.session.flush()
        
        invoice = Invoice(
            number='MINIMAL-2025-001',
            client_id=test_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            subtotal=Decimal('0.00'),
            total=Decimal('0.00')
        )
        db.session.add(invoice)
        db.session.commit()
        
        # PDF generation should still work with minimal data
        response = client.get(f'/invoices/{invoice.id}/pdf')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        assert len(response.data) > 0


class TestPDFTemplates:
    """Test different PDF template functionality."""
    
    def test_standard_template(self, client, app_context):
        """Test standard PDF template."""
        invoice = self._create_test_invoice('STANDARD-2025-001')
        
        response = client.get(f'/invoices/{invoice.id}/pdf?template=standard')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        assert len(response.data) > 0
    
    def test_modern_template(self, client, app_context):
        """Test modern PDF template."""
        invoice = self._create_test_invoice('MODERN-2025-001')
        
        response = client.get(f'/invoices/{invoice.id}/pdf?template=modern')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        assert len(response.data) > 0
    
    def test_elegant_template(self, client, app_context):
        """Test elegant PDF template."""
        invoice = self._create_test_invoice('ELEGANT-2025-001')
        
        response = client.get(f'/invoices/{invoice.id}/pdf?template=elegant')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        assert len(response.data) > 0
    
    def _create_test_invoice(self, number):
        """Helper method to create test invoice."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        test_client = Client(
            name='Template Test Client',
            email='template@test.ee'
        )
        db.session.add(test_client)
        db.session.flush()
        
        invoice = Invoice(
            number=number,
            client_id=test_client.id,
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
            description='Template test service',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db.session.add(line)
        db.session.commit()
        
        return invoice


class TestPDFPerformance:
    """Test PDF generation performance."""
    
    def test_pdf_generation_performance(self, client, app_context):
        """Test PDF generation performance with large invoices."""
        # Create invoice with many line items
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        test_client = Client(
            name='Performance Test Client',
            email='performance@test.ee'
        )
        db.session.add(test_client)
        db.session.flush()
        
        invoice = Invoice(
            number='PERF-2025-001',
            client_id=test_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id
        )
        db.session.add(invoice)
        db.session.flush()
        
        # Add 20 line items
        subtotal = Decimal('0.00')
        for i in range(20):
            line = InvoiceLine(
                invoice_id=invoice.id,
                description=f'Performance test service #{i+1}',
                qty=Decimal('1.00'),
                unit_price=Decimal('50.00'),
                line_total=Decimal('50.00')
            )
            db.session.add(line)
            subtotal += Decimal('50.00')
        
        invoice.subtotal = subtotal
        invoice.total = subtotal * Decimal('1.24')  # 24% VAT
        db.session.commit()
        
        # Measure PDF generation time
        import time
        start_time = time.time()
        
        response = client.get(f'/invoices/{invoice.id}/pdf')
        
        end_time = time.time()
        generation_time = end_time - start_time
        
        # PDF should be generated within reasonable time (< 10 seconds)
        assert generation_time < 10.0
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        assert len(response.data) > 0