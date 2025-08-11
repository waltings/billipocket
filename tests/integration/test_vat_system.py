"""
Integration tests for VAT rate system functionality.

Tests comprehensive VAT rate workflows including:
- VAT rate dropdown selection in invoice forms
- Multiple VAT rates (0%, 9%, 20%, 24%) functionality
- VAT calculations accuracy with 2 decimal places
- VAT rate management in settings
- Default VAT rate (24%) functioning
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta

from app.models import db, VatRate, Invoice, InvoiceLine, Client, CompanySettings


class TestVATRateSystem:
    """Test VAT rate system functionality."""
    
    def test_default_vat_rates_creation(self, app_context):
        """Test creation of default Estonian VAT rates."""
        # Ensure clean state
        VatRate.query.delete()
        db.session.commit()
        
        # Create default rates
        VatRate.create_default_rates()
        
        # Verify all expected rates were created
        rates = VatRate.get_active_rates()
        assert len(rates) == 4
        
        rate_values = [rate.rate for rate in rates]
        expected_rates = [Decimal('0.00'), Decimal('9.00'), Decimal('20.00'), Decimal('24.00')]
        
        for expected_rate in expected_rates:
            assert expected_rate in rate_values
        
        # Verify Estonian names and descriptions
        rate_0 = VatRate.query.filter_by(rate=0).first()
        assert rate_0.name == 'Maksuvaba (0%)'
        assert 'Käibemaksuvaba' in rate_0.description
        
        rate_24 = VatRate.query.filter_by(rate=24).first()
        assert rate_24.name == 'Standardmäär (24%)'
        assert 'standardne käibemaksumäär' in rate_24.description
    
    def test_get_default_rate(self, app_context):
        """Test getting Estonian standard VAT rate (24%)."""
        VatRate.create_default_rates()
        
        default_rate = VatRate.get_default_rate()
        assert default_rate is not None
        assert default_rate.rate == Decimal('24.00')
        assert default_rate.is_active is True
    
    def test_get_active_rates_sorted(self, app_context):
        """Test getting active VAT rates sorted by rate."""
        VatRate.create_default_rates()
        
        # Add an inactive rate
        inactive_rate = VatRate(
            name='Inactive Rate (99%)',
            rate=Decimal('99.00'),
            is_active=False
        )
        db.session.add(inactive_rate)
        db.session.commit()
        
        active_rates = VatRate.get_active_rates()
        
        # Should only return active rates
        assert len(active_rates) == 4
        
        # Should be sorted by rate ascending
        rate_values = [rate.rate for rate in active_rates]
        assert rate_values == sorted(rate_values)
        assert rate_values[0] == Decimal('0.00')
        assert rate_values[-1] == Decimal('24.00')


class TestVATRateDropdownSelection:
    """Test VAT rate dropdown in invoice forms."""
    
    def test_vat_rate_dropdown_populated(self, client, app_context, sample_client):
        """Test that VAT rate dropdown is populated in invoice creation form."""
        VatRate.create_default_rates()
        
        response = client.get('/invoices/new')
        assert response.status_code == 200
        
        # Check that VAT rate options are present
        assert b'0%' in response.data or b'0.00' in response.data
        assert b'9%' in response.data or b'9.00' in response.data
        assert b'20%' in response.data or b'20.00' in response.data
        assert b'24%' in response.data or b'24.00' in response.data
        
        # Check Estonian VAT rate names
        assert b'Maksuvaba' in response.data or b'maksuvaba' in response.data
        assert b'Standardm' in response.data or b'standardm' in response.data
    
    def test_invoice_creation_with_each_vat_rate(self, client, app_context, sample_client):
        """Test creating invoices with each available VAT rate."""
        VatRate.create_default_rates()
        vat_rates = VatRate.get_active_rates()
        
        for vat_rate_obj in vat_rates:
            form_data = {
                'client_id': str(sample_client.id),
                'date': '2025-08-10',
                'due_date': '2025-08-24',
                'vat_rate_id': str(vat_rate_obj.id),
                'status': 'mustand',
                'lines-0-description': f'Test service with {vat_rate_obj.name}',
                'lines-0-qty': '1.00',
                'lines-0-unit_price': '100.00'
            }
            
            response = client.post('/invoices/new', data=form_data, follow_redirects=True)
            assert response.status_code == 200
            
            # Verify invoice was created with correct VAT rate
            invoice = Invoice.query.filter_by(vat_rate_id=vat_rate_obj.id).first()
            assert invoice is not None
            assert invoice.vat_rate_id == vat_rate_obj.id
            assert invoice.get_effective_vat_rate() == vat_rate_obj.rate
            
            # Clean up for next iteration
            if invoice:
                db.session.delete(invoice)
                db.session.commit()
    
    def test_vat_rate_dropdown_in_edit_form(self, client, app_context):
        """Test VAT rate dropdown in invoice edit form."""
        VatRate.create_default_rates()
        client_obj = Client(name='Test Client for VAT Edit', email='test@vatedit.ee')
        db.session.add(client_obj)
        db.session.flush()
        
        standard_vat = VatRate.get_default_rate()
        invoice = Invoice(
            number='VAT-EDIT-TEST-001',
            client_id=client_obj.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            subtotal=Decimal('100.00'),
            total=Decimal('124.00')
        )
        db.session.add(invoice)
        db.session.commit()
        
        response = client.get(f'/invoices/{invoice.id}/edit')
        assert response.status_code == 200
        
        # Check that all VAT rate options are available
        vat_rates = VatRate.get_active_rates()
        for vat_rate_obj in vat_rates:
            assert str(vat_rate_obj.rate).encode() in response.data
        
        # Check that current VAT rate is selected
        assert f'selected' in response.data.decode() or f'value="{standard_vat.id}"' in response.data.decode()


class TestVATCalculationAccuracy:
    """Test VAT calculation accuracy with 2 decimal places."""
    
    @pytest.mark.parametrize("subtotal,vat_rate,expected_vat,expected_total", [
        (Decimal('100.00'), Decimal('0.00'), Decimal('0.00'), Decimal('100.00')),
        (Decimal('100.00'), Decimal('9.00'), Decimal('9.00'), Decimal('109.00')),
        (Decimal('100.00'), Decimal('20.00'), Decimal('20.00'), Decimal('120.00')),
        (Decimal('100.00'), Decimal('24.00'), Decimal('24.00'), Decimal('124.00')),
        (Decimal('344.26'), Decimal('24.00'), Decimal('82.62'), Decimal('426.88')),
        (Decimal('123.45'), Decimal('20.00'), Decimal('24.69'), Decimal('148.14')),
        (Decimal('999.99'), Decimal('9.00'), Decimal('90.00'), Decimal('1089.99')),
    ])
    def test_vat_calculation_precision(self, app_context, sample_client, 
                                     subtotal, vat_rate, expected_vat, expected_total):
        """Test VAT calculations with various amounts and rates."""
        # Find or create VAT rate
        vat_rate_obj = VatRate.query.filter_by(rate=vat_rate).first()
        if not vat_rate_obj:
            vat_rate_obj = VatRate(
                name=f'Test Rate ({vat_rate}%)',
                rate=vat_rate,
                description='Test rate'
            )
            db.session.add(vat_rate_obj)
            db.session.commit()
        
        invoice = Invoice(
            number=f'CALC-TEST-{subtotal}-{vat_rate}',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=vat_rate_obj.id,
            subtotal=subtotal
        )
        
        # Test VAT amount calculation
        calculated_vat = invoice.vat_amount
        assert calculated_vat.quantize(Decimal('0.01')) == expected_vat
        
        # Test total calculation
        calculated_total = subtotal + calculated_vat
        assert calculated_total.quantize(Decimal('0.01')) == expected_total
    
    def test_complex_invoice_calculations(self, app_context, sample_client):
        """Test calculations with multiple line items and different scenarios."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='COMPLEX-CALC-2025-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id
        )
        db.session.add(invoice)
        db.session.flush()
        
        # Add multiple lines with different amounts
        lines_data = [
            ('Web development', Decimal('3.50'), Decimal('85.71'), Decimal('299.99')),
            ('Consulting', Decimal('1.00'), Decimal('344.26'), Decimal('344.26')),
            ('Project management', Decimal('2.25'), Decimal('133.33'), Decimal('299.99')),
        ]
        
        for description, qty, unit_price, line_total in lines_data:
            line = InvoiceLine(
                invoice_id=invoice.id,
                description=description,
                qty=qty,
                unit_price=unit_price,
                line_total=line_total
            )
            db.session.add(line)
        
        db.session.commit()
        
        # Calculate totals
        invoice.calculate_totals()
        
        # Verify calculations
        expected_subtotal = sum(line_total for _, _, _, line_total in lines_data)
        assert invoice.subtotal == expected_subtotal
        
        # VAT should be 24% of subtotal, rounded to 2 decimal places
        expected_vat = (expected_subtotal * Decimal('0.24')).quantize(Decimal('0.01'))
        actual_vat = invoice.vat_amount.quantize(Decimal('0.01'))
        assert actual_vat == expected_vat
        
        # Total should be subtotal + VAT
        expected_total = expected_subtotal + expected_vat
        assert invoice.total == expected_total
    
    def test_rounding_edge_cases(self, app_context, sample_client):
        """Test VAT calculations with amounts that require rounding."""
        VatRate.create_default_rates()
        
        # Test cases that produce fractional cents
        test_cases = [
            (Decimal('33.33'), Decimal('24.00')),  # Results in 7.9992 VAT
            (Decimal('66.67'), Decimal('9.00')),   # Results in 6.0003 VAT
            (Decimal('123.45'), Decimal('20.00')), # Results in 24.69 VAT
        ]
        
        for subtotal, vat_rate in test_cases:
            vat_rate_obj = VatRate.query.filter_by(rate=vat_rate).first()
            
            invoice = Invoice(
                number=f'ROUND-TEST-{subtotal}-{vat_rate}',
                client_id=sample_client.id,
                date=date.today(),
                due_date=date.today() + timedelta(days=14),
                vat_rate_id=vat_rate_obj.id,
                subtotal=subtotal
            )
            
            # VAT amount should have exactly 2 decimal places
            vat_amount = invoice.vat_amount
            assert vat_amount.as_tuple().exponent >= -2
            
            # Total should also have exactly 2 decimal places
            total = subtotal + vat_amount
            assert total.as_tuple().exponent >= -2


class TestVATRateManagement:
    """Test VAT rate management functionality."""
    
    def test_company_settings_default_vat_rate(self, app_context):
        """Test company settings default VAT rate functionality."""
        VatRate.create_default_rates()
        
        settings = CompanySettings.get_settings()
        assert settings.default_vat_rate == Decimal('24.00')  # Estonian standard
        
        # Test updating default VAT rate
        settings.default_vat_rate = Decimal('20.00')
        db.session.commit()
        
        updated_settings = CompanySettings.get_settings()
        assert updated_settings.default_vat_rate == Decimal('20.00')
    
    def test_vat_rate_constraints(self, app_context):
        """Test VAT rate database constraints."""
        # Test valid VAT rate
        valid_rate = VatRate(
            name='Valid Rate (15%)',
            rate=Decimal('15.00'),
            description='Valid test rate'
        )
        db.session.add(valid_rate)
        db.session.commit()  # Should succeed
        
        # Test invalid VAT rate (over 100%)
        with pytest.raises(Exception):  # Should raise integrity error
            invalid_rate = VatRate(
                name='Invalid Rate (150%)',
                rate=Decimal('150.00'),
                description='Invalid test rate'
            )
            db.session.add(invalid_rate)
            db.session.commit()
        
        db.session.rollback()
        
        # Test negative VAT rate
        with pytest.raises(Exception):  # Should raise integrity error
            negative_rate = VatRate(
                name='Negative Rate (-5%)',
                rate=Decimal('-5.00'),
                description='Negative test rate'
            )
            db.session.add(negative_rate)
            db.session.commit()
    
    def test_duplicate_vat_rate_prevention(self, app_context):
        """Test that duplicate VAT rates are prevented."""
        rate1 = VatRate(
            name='First 15% Rate',
            rate=Decimal('15.00'),
            description='First rate'
        )
        db.session.add(rate1)
        db.session.commit()
        
        # Try to create another rate with same percentage
        with pytest.raises(Exception):  # Should raise integrity error
            rate2 = VatRate(
                name='Second 15% Rate',
                rate=Decimal('15.00'),  # Same rate
                description='Duplicate rate'
            )
            db.session.add(rate2)
            db.session.commit()
    
    def test_vat_rate_activation_deactivation(self, app_context):
        """Test VAT rate activation and deactivation."""
        test_rate = VatRate(
            name='Test Activation Rate (12%)',
            rate=Decimal('12.00'),
            description='Test activation',
            is_active=True
        )
        db.session.add(test_rate)
        db.session.commit()
        
        # Verify it's in active rates
        active_rates = VatRate.get_active_rates()
        assert test_rate in active_rates
        
        # Deactivate it
        test_rate.is_active = False
        db.session.commit()
        
        # Verify it's not in active rates
        active_rates = VatRate.get_active_rates()
        assert test_rate not in active_rates
        
        # Reactivate it
        test_rate.is_active = True
        db.session.commit()
        
        # Verify it's back in active rates
        active_rates = VatRate.get_active_rates()
        assert test_rate in active_rates


class TestVATRateIntegration:
    """Test VAT rate integration with other system components."""
    
    def test_invoice_vat_rate_relationship(self, app_context, sample_client):
        """Test foreign key relationship between invoices and VAT rates."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='VAT-REL-2025-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            subtotal=Decimal('100.00'),
            total=Decimal('124.00')
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Test relationship
        assert invoice.vat_rate_obj == standard_vat
        assert invoice in standard_vat.invoices
        
        # Test effective VAT rate method
        assert invoice.get_effective_vat_rate() == standard_vat.rate
    
    def test_backward_compatibility_fallback(self, app_context, sample_client):
        """Test backward compatibility with old vat_rate column."""
        # Create invoice without VAT rate relationship (old style)
        invoice = Invoice(
            number='COMPAT-2025-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=None,  # No relationship
            vat_rate=Decimal('22.00'),  # Old column
            subtotal=Decimal('100.00'),
            total=Decimal('122.00')
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Should fall back to vat_rate column
        assert invoice.get_effective_vat_rate() == Decimal('22.00')
        assert invoice.vat_amount == Decimal('22.00')
    
    def test_vat_rate_deletion_with_invoices(self, app_context, sample_client):
        """Test behavior when trying to delete VAT rate with associated invoices."""
        VatRate.create_default_rates()
        test_vat = VatRate(
            name='Test Deletion Rate (18%)',
            rate=Decimal('18.00'),
            description='Rate for deletion test'
        )
        db.session.add(test_vat)
        db.session.flush()
        
        # Create invoice using this VAT rate
        invoice = Invoice(
            number='VAT-DEL-2025-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=test_vat.id,
            subtotal=Decimal('100.00'),
            total=Decimal('118.00')
        )
        db.session.add(invoice)
        db.session.commit()
        
        # Try to delete VAT rate (should be restricted by foreign key)
        with pytest.raises(Exception):  # Should raise integrity error
            db.session.delete(test_vat)
            db.session.commit()
        
        db.session.rollback()
        
        # VAT rate should still exist
        existing_rate = VatRate.query.get(test_vat.id)
        assert existing_rate is not None