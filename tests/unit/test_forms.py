"""
Unit tests for Flask-WTF forms validation.

Tests cover:
- ClientForm validation (name, email, phone, address validation)
- InvoiceForm validation (number format, client selection, dates, VAT rates)
- InvoiceLineForm validation (description, quantities, prices)
- Custom validators (unique invoice numbers, status transitions)
- Estonian language validation messages
- Form field constraints and edge cases
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from app.forms import (
    ClientForm,
    InvoiceForm,
    InvoiceLineForm,
    validate_unique_invoice_number,
    validate_invoice_number_format,
    validate_status_change
)
from app.models import db, Client, Invoice, VatRate


class TestClientForm:
    """Test ClientForm validation."""
    
    def test_client_form_valid_data(self, app_context):
        """Test client form with valid data."""
        form_data = {
            'name': 'Test Klient OÜ',
            'registry_code': '12345678',
            'email': 'test@klient.ee',
            'phone': '+372 5555 1234',
            'address': 'Testiaadress 123, 10001 Tallinn'
        }
        
        form = ClientForm(data=form_data)
        assert form.validate() is True
        assert len(form.errors) == 0
    
    def test_client_form_minimal_valid_data(self, app_context):
        """Test client form with only required fields."""
        form_data = {
            'name': 'Minimaalne Klient'
        }
        
        form = ClientForm(data=form_data)
        assert form.validate() is True
        assert form.name.data == 'Minimaalne Klient'
    
    def test_client_form_missing_name(self, app_context):
        """Test client form validation when name is missing."""
        form_data = {
            'email': 'test@klient.ee',
            'phone': '+372 5555 1234'
        }
        
        form = ClientForm(data=form_data)
        assert form.validate() is False
        assert 'name' in form.errors
        assert 'Nimi on kohustuslik' in form.errors['name']
    
    def test_client_form_empty_name(self, app_context):
        """Test client form validation when name is empty."""
        form_data = {
            'name': '',
            'email': 'test@klient.ee'
        }
        
        form = ClientForm(data=form_data)
        assert form.validate() is False
        assert 'name' in form.errors
    
    def test_client_form_invalid_email(self, app_context):
        """Test client form validation with invalid email."""
        form_data = {
            'name': 'Test Klient',
            'email': 'invalid-email'
        }
        
        form = ClientForm(data=form_data)
        assert form.validate() is False
        assert 'email' in form.errors
        assert 'Vigane e-posti aadress' in form.errors['email']
    
    @pytest.mark.parametrize("email", [
        'test@example.com',
        'user.name@domain.ee',
        'test+label@gmail.com',
        'test123@domain.co.uk'
    ])
    def test_client_form_valid_emails(self, app_context, email):
        """Test client form with various valid email formats."""
        form_data = {
            'name': 'Test Klient',
            'email': email
        }
        
        form = ClientForm(data=form_data)
        assert form.validate() is True
    
    def test_client_form_registry_code_too_long(self, app_context):
        """Test client form validation when registry code is too long."""
        form_data = {
            'name': 'Test Klient',
            'registry_code': '123456789012345678901'  # 21 characters, max is 20
        }
        
        form = ClientForm(data=form_data)
        assert form.validate() is False
        assert 'registry_code' in form.errors
    
    def test_client_form_phone_too_long(self, app_context):
        """Test client form validation when phone is too long."""
        form_data = {
            'name': 'Test Klient',
            'phone': '+372 1234567890123456789012'  # Too long
        }
        
        form = ClientForm(data=form_data)
        assert form.validate() is False
        assert 'phone' in form.errors
    
    def test_client_form_optional_fields_none(self, app_context):
        """Test client form handles None values in optional fields."""
        form_data = {
            'name': 'Test Klient',
            'registry_code': None,
            'email': None,
            'phone': None,
            'address': None
        }
        
        form = ClientForm(data=form_data)
        assert form.validate() is True


class TestInvoiceLineForm:
    """Test InvoiceLineForm validation."""
    
    def test_invoice_line_form_valid_data(self, app_context):
        """Test invoice line form with valid data."""
        form_data = {
            'description': 'Veebiarenduse teenused',
            'qty': '2.5',
            'unit_price': '80.00'
        }
        
        form = InvoiceLineForm(data=form_data)
        assert form.validate() is True
        assert form.description.data == 'Veebiarenduse teenused'
        assert form.qty.data == Decimal('2.5')
        assert form.unit_price.data == Decimal('80.00')
    
    def test_invoice_line_form_missing_description(self, app_context):
        """Test invoice line form validation when description is missing."""
        form_data = {
            'qty': '1.0',
            'unit_price': '100.00'
        }
        
        form = InvoiceLineForm(data=form_data)
        assert form.validate() is False
        assert 'description' in form.errors
        assert 'Kirjeldus on kohustuslik' in form.errors['description']
    
    def test_invoice_line_form_missing_qty(self, app_context):
        """Test invoice line form validation when quantity is missing."""
        form_data = {
            'description': 'Test teenus',
            'unit_price': '100.00'
        }
        
        form = InvoiceLineForm(data=form_data)
        assert form.validate() is False
        assert 'qty' in form.errors
        assert 'Kogus on kohustuslik' in form.errors['qty']
    
    def test_invoice_line_form_missing_unit_price(self, app_context):
        """Test invoice line form validation when unit price is missing."""
        form_data = {
            'description': 'Test teenus',
            'qty': '1.0'
        }
        
        form = InvoiceLineForm(data=form_data)
        assert form.validate() is False
        assert 'unit_price' in form.errors
        assert 'Ühiku hind on kohustuslik' in form.errors['unit_price']
    
    @pytest.mark.parametrize("qty,should_be_valid", [
        ('0.01', True),   # Minimum valid quantity
        ('1.00', True),   # Standard quantity
        ('999.99', True), # Large quantity
        ('0.001', True),  # Very small quantity
        ('0', False),     # Zero quantity
        ('-1', False),    # Negative quantity
        ('abc', False),   # Non-numeric
        ('', False)       # Empty
    ])
    def test_invoice_line_form_qty_validation(self, app_context, qty, should_be_valid):
        """Test quantity validation with various values."""
        form_data = {
            'description': 'Test teenus',
            'qty': qty,
            'unit_price': '100.00'
        }
        
        form = InvoiceLineForm(data=form_data)
        is_valid = form.validate()
        
        if should_be_valid:
            assert is_valid is True
        else:
            assert is_valid is False
            assert 'qty' in form.errors
    
    @pytest.mark.parametrize("unit_price,should_be_valid", [
        ('0.00', True),    # Free service
        ('0.01', True),    # Minimum price
        ('100.50', True),  # Standard price
        ('9999.99', True), # High price
        ('-1.00', False),  # Negative price
        ('abc', False),    # Non-numeric
        ('', False)        # Empty
    ])
    def test_invoice_line_form_unit_price_validation(self, app_context, unit_price, should_be_valid):
        """Test unit price validation with various values."""
        form_data = {
            'description': 'Test teenus',
            'qty': '1.0',
            'unit_price': unit_price
        }
        
        form = InvoiceLineForm(data=form_data)
        is_valid = form.validate()
        
        if should_be_valid:
            assert is_valid is True
        else:
            assert is_valid is False
            assert 'unit_price' in form.errors
    
    def test_invoice_line_form_estonian_description(self, app_context):
        """Test invoice line form with Estonian characters."""
        form_data = {
            'description': 'Äriprotsesside analüüs ja süsteemiarenduse nõustamine',
            'qty': '1.0',
            'unit_price': '500.00'
        }
        
        form = InvoiceLineForm(data=form_data)
        assert form.validate() is True
        assert 'analüüs' in form.description.data
        assert 'süsteemiarenduse' in form.description.data
        assert 'nõustamine' in form.description.data


class TestInvoiceForm:
    """Test InvoiceForm validation."""
    
    def test_invoice_form_valid_data(self, app_context, sample_client):
        """Test invoice form with valid data."""
        # Create VAT rate
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'number': '2025-0001',
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand'
        }
        
        form = InvoiceForm(data=form_data)
        # Populate client choices manually for test
        form.client_id.choices = [(sample_client.id, sample_client.name)]
        form.vat_rate_id.choices = [(standard_vat.id, f"{standard_vat.name}")]
        
        assert form.validate() is True
    
    def test_invoice_form_missing_number(self, app_context, sample_client):
        """Test invoice form validation when number is missing."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand'
        }
        
        form = InvoiceForm(data=form_data)
        form.client_id.choices = [(sample_client.id, sample_client.name)]
        form.vat_rate_id.choices = [(standard_vat.id, f"{standard_vat.name}")]
        
        assert form.validate() is False
        assert 'number' in form.errors
        assert 'Arve number on kohustuslik' in form.errors['number']
    
    def test_invoice_form_missing_client(self, app_context):
        """Test invoice form validation when client is missing."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'number': '2025-0001',
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand'
        }
        
        form = InvoiceForm(data=form_data)
        form.client_id.choices = []  # No clients available
        form.vat_rate_id.choices = [(standard_vat.id, f"{standard_vat.name}")]
        
        assert form.validate() is False
        assert 'client_id' in form.errors
    
    def test_invoice_form_missing_dates(self, app_context, sample_client):
        """Test invoice form validation when dates are missing."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'number': '2025-0001',
            'client_id': str(sample_client.id),
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand'
        }
        
        form = InvoiceForm(data=form_data)
        form.client_id.choices = [(sample_client.id, sample_client.name)]
        form.vat_rate_id.choices = [(standard_vat.id, f"{standard_vat.name}")]
        
        assert form.validate() is False
        assert 'date' in form.errors or 'due_date' in form.errors
    
    def test_invoice_form_defaults(self, app_context):
        """Test invoice form default values."""
        form = InvoiceForm()
        
        # Date should default to today
        assert form.date.data == date.today()
        
        # Due date should default to 14 days from now
        expected_due_date = date.today() + timedelta(days=14)
        assert form.due_date.data == expected_due_date
        
        # Status should default to draft
        assert form.status.data == 'mustand'


class TestCustomValidators:
    """Test custom form validators."""
    
    def test_validate_invoice_number_format_valid(self, app_context):
        """Test invoice number format validator with valid formats."""
        valid_numbers = [
            '2025-0001',
            '2024-9999',
            '2023-0123'
        ]
        
        for number in valid_numbers:
            form = MagicMock()
            field = MagicMock()
            field.data = number
            
            # Should not raise ValidationError
            try:
                validate_invoice_number_format(form, field)
            except Exception as e:
                pytest.fail(f"Valid number {number} raised exception: {e}")
    
    def test_validate_invoice_number_format_invalid(self, app_context):
        """Test invoice number format validator with invalid formats."""
        from wtforms.validators import ValidationError
        
        invalid_numbers = [
            '25-0001',      # Year too short
            '2025-01',      # Number too short
            '2025-00001',   # Number too long
            'ABCD-0001',    # Non-numeric year
            '2025-ABCD',    # Non-numeric number
            '2025_0001',    # Wrong separator
            '20250001',     # No separator
            '2025-0001-001', # Too many parts
            ''              # Empty string
        ]
        
        for number in invalid_numbers:
            form = MagicMock()
            field = MagicMock()
            field.data = number
            
            with pytest.raises(ValidationError) as exc_info:
                validate_invoice_number_format(form, field)
            
            assert 'AAAA-NNNN' in str(exc_info.value)
    
    def test_validate_unique_invoice_number_available(self, app_context):
        """Test unique invoice number validator when number is available."""
        form = MagicMock()
        field = MagicMock()
        field.data = '2025-9999'  # Assuming this number doesn't exist
        
        # Should not raise ValidationError
        try:
            validate_unique_invoice_number(form, field)
        except Exception as e:
            pytest.fail(f"Available number raised exception: {e}")
    
    def test_validate_unique_invoice_number_taken(self, app_context, sample_invoice):
        """Test unique invoice number validator when number is taken."""
        from wtforms.validators import ValidationError
        
        form = MagicMock()
        field = MagicMock()
        field.data = sample_invoice.number  # Use existing number
        
        with pytest.raises(ValidationError) as exc_info:
            validate_unique_invoice_number(form, field)
        
        assert 'juba kasutusel' in str(exc_info.value)
        assert sample_invoice.number in str(exc_info.value)
    
    def test_validate_unique_invoice_number_same_invoice(self, app_context, sample_invoice):
        """Test unique invoice number validator for same invoice (editing)."""
        form = MagicMock()
        form._invoice_id = sample_invoice.id  # Editing the same invoice
        field = MagicMock()
        field.data = sample_invoice.number
        
        # Should not raise ValidationError when editing same invoice
        try:
            validate_unique_invoice_number(form, field)
        except Exception as e:
            pytest.fail(f"Same invoice editing raised exception: {e}")
    
    @patch('app.models.Invoice.query')
    def test_validate_status_change_new_invoice(self, mock_query, app_context):
        """Test status change validator for new invoice."""
        # New invoice (no _invoice_id)
        form = MagicMock()
        # Don't set _invoice_id to simulate new invoice
        if hasattr(form, '_invoice_id'):
            delattr(form, '_invoice_id')
        
        field = MagicMock()
        field.data = 'saadetud'
        
        # Should not raise ValidationError for new invoice
        try:
            validate_status_change(form, field)
        except Exception as e:
            pytest.fail(f"New invoice status validation raised exception: {e}")
    
    def test_validate_status_change_valid_transition(self, app_context, sample_invoice):
        """Test status change validator for valid transition."""
        # Mock invoice can_change_status_to method
        sample_invoice.can_change_status_to = MagicMock(return_value=(True, None))
        
        form = MagicMock()
        form._invoice_id = sample_invoice.id
        field = MagicMock()
        field.data = 'saadetud'
        
        with patch('app.models.Invoice.query.get', return_value=sample_invoice):
            try:
                validate_status_change(form, field)
            except Exception as e:
                pytest.fail(f"Valid status change raised exception: {e}")
    
    def test_validate_status_change_invalid_transition(self, app_context, sample_invoice):
        """Test status change validator for invalid transition."""
        from wtforms.validators import ValidationError
        
        error_message = "Makstud arveid ei saa tagasi muuta"
        sample_invoice.can_change_status_to = MagicMock(return_value=(False, error_message))
        
        form = MagicMock()
        form._invoice_id = sample_invoice.id
        field = MagicMock()
        field.data = 'mustand'
        
        with patch('app.models.Invoice.query.get', return_value=sample_invoice):
            with pytest.raises(ValidationError) as exc_info:
                validate_status_change(form, field)
            
            assert error_message in str(exc_info.value)


class TestFormIntegration:
    """Test form integration scenarios."""
    
    def test_invoice_form_with_lines(self, app_context, sample_client):
        """Test invoice form with multiple line items."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'number': '2025-0001',
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'Service 1',
            'lines-0-qty': '1.0',
            'lines-0-unit_price': '100.00',
            'lines-1-description': 'Service 2',
            'lines-1-qty': '2.0',
            'lines-1-unit_price': '75.00'
        }
        
        form = InvoiceForm(data=form_data)
        form.client_id.choices = [(sample_client.id, sample_client.name)]
        form.vat_rate_id.choices = [(standard_vat.id, f"{standard_vat.name}")]
        
        assert form.validate() is True
        assert len(form.lines.data) == 2
        
        line1 = form.lines.data[0]
        assert line1['description'] == 'Service 1'
        assert line1['qty'] == Decimal('1.0')
        assert line1['unit_price'] == Decimal('100.00')
    
    def test_invoice_form_estonian_content(self, app_context, sample_client):
        """Test invoice form with Estonian content."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        form_data = {
            'number': '2025-0001',
            'client_id': str(sample_client.id),
            'date': '2025-08-10',
            'due_date': '2025-08-24',
            'vat_rate_id': str(standard_vat.id),
            'status': 'mustand',
            'lines-0-description': 'Veebiarenduse teenused ja süsteemide hooldus',
            'lines-0-qty': '1.0',
            'lines-0-unit_price': '500.00'
        }
        
        form = InvoiceForm(data=form_data)
        form.client_id.choices = [(sample_client.id, sample_client.name)]
        form.vat_rate_id.choices = [(standard_vat.id, f"{standard_vat.name}")]
        
        assert form.validate() is True
        line = form.lines.data[0]
        assert 'süsteemide' in line['description']
        assert 'teenused' in line['description']
    
    def test_form_field_rendering_attributes(self, app_context):
        """Test form field rendering attributes."""
        form = InvoiceForm()
        
        # Test that number field has placeholder
        assert hasattr(form.number, 'render_kw')
        if form.number.render_kw:
            assert 'placeholder' in form.number.render_kw
            assert 'Näiteks: 2025-0001' in form.number.render_kw['placeholder']
    
    def test_form_status_choices(self, app_context):
        """Test invoice form status choices are in Estonian."""
        form = InvoiceForm()
        
        status_values = [choice[0] for choice in form.status.choices]
        status_labels = [choice[1] for choice in form.status.choices]
        
        assert 'mustand' in status_values
        assert 'saadetud' in status_values
        assert 'makstud' in status_values
        assert 'tähtaeg ületatud' in status_values
        
        assert 'Mustand' in status_labels
        assert 'Saadetud' in status_labels
        assert 'Makstud' in status_labels