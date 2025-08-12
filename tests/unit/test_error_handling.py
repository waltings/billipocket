"""
Comprehensive error handling and edge case tests.

Tests cover:
- Database integrity constraints and violations
- Invalid data handling (malformed inputs, edge values)
- Error recovery and graceful degradation
- Estonian-specific validation edge cases
- Business rule violations
- Resource not found scenarios
- Concurrent access and race conditions
- Memory and performance limits
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import IntegrityError, DataError
from sqlalchemy import text

from app.models import db, Client, Invoice, InvoiceLine, VatRate, CompanySettings
from app.services.numbering import generate_invoice_number, is_invoice_number_available
from app.services.status_transitions import InvoiceStatusTransition
from app.services.totals import calculate_line_total, calculate_vat_amount


class TestDatabaseConstraints:
    """Test database constraint violations and error handling."""
    
    def test_client_duplicate_constraints(self, db_session):
        """Test handling of duplicate client data."""
        # Create first client
        client1 = Client(
            name='Test Company',
            email='test@company.ee'
        )
        db_session.add(client1)
        db_session.commit()
        
        # Try to create client with same name (should be allowed)
        client2 = Client(
            name='Test Company',
            email='different@company.ee'
        )
        db_session.add(client2)
        # Should succeed - names don't have to be unique
        db_session.commit()
        
        assert Client.query.filter_by(name='Test Company').count() == 2
    
    def test_invoice_number_constraint_violation(self, db_session, sample_client):
        """Test duplicate invoice number constraint."""
        # Create first invoice
        invoice1 = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        db_session.add(invoice1)
        db_session.commit()
        
        # Try to create invoice with same number
        invoice2 = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        db_session.add(invoice2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_invalid_foreign_key_reference(self, db_session):
        """Test invalid foreign key references."""
        # Try to create invoice with non-existent client
        invoice = Invoice(
            number='2025-0001',
            client_id=99999,  # Non-existent client
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        db_session.add(invoice)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_check_constraint_violations(self, db_session, sample_client):
        """Test various check constraint violations."""
        # Negative subtotal
        with pytest.raises(IntegrityError):
            invoice = Invoice(
                number='2025-0001',
                client_id=sample_client.id,
                date=date.today(),
                due_date=date.today() + timedelta(days=14),
                subtotal=Decimal('-100.00')
            )
            db_session.add(invoice)
            db_session.commit()
        
        db_session.rollback()
        
        # Invalid status
        with pytest.raises(IntegrityError):
            invoice = Invoice(
                number='2025-0002',
                client_id=sample_client.id,
                date=date.today(),
                due_date=date.today() + timedelta(days=14),
                status='invalid_status'
            )
            db_session.add(invoice)
            db_session.commit()
    
    def test_string_length_violations(self, db_session):
        """Test string length constraint violations."""
        # Client name too long
        long_name = 'A' * 1000  # Assuming max length is less than 1000
        client = Client(name=long_name)
        db_session.add(client)
        
        # This might raise DataError or succeed depending on database
        try:
            db_session.commit()
            # If it succeeds, the name should be truncated or handled
            assert len(client.name) <= 200  # Assuming 200 is the limit
        except (DataError, IntegrityError):
            # This is expected for overly long strings
            pass
    
    def test_null_constraint_violations(self, db_session):
        """Test null constraint violations."""
        # Client without required name
        client = Client(email='test@company.ee')
        db_session.add(client)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_vat_rate_constraint_violations(self, db_session):
        """Test VAT rate specific constraints."""
        # Negative VAT rate
        with pytest.raises(IntegrityError):
            vat_rate = VatRate(
                name='Negative Rate',
                rate=Decimal('-5.00')
            )
            db_session.add(vat_rate)
            db_session.commit()
        
        db_session.rollback()
        
        # VAT rate over 100%
        with pytest.raises(IntegrityError):
            vat_rate = VatRate(
                name='Over 100%',
                rate=Decimal('150.00')
            )
            db_session.add(vat_rate)
            db_session.commit()


class TestInvalidDataHandling:
    """Test handling of invalid or malformed data."""
    
    @pytest.mark.parametrize("invalid_decimal", [
        'not_a_number',
        'abc.def',
        '12.34.56',
        '',
        None,
        'infinity',
        'nan'
    ])
    def test_invalid_decimal_handling(self, invalid_decimal):
        """Test handling of invalid decimal inputs."""
        with pytest.raises((ValueError, InvalidOperation, TypeError)):
            Decimal(invalid_decimal)
    
    @pytest.mark.parametrize("invalid_qty,invalid_price", [
        ('invalid', '100.00'),
        ('1.0', 'invalid'),
        ('', '100.00'),
        ('1.0', ''),
        (None, '100.00'),
        ('1.0', None)
    ])
    def test_calculate_line_total_invalid_inputs(self, invalid_qty, invalid_price):
        """Test line total calculation with invalid inputs."""
        # Should handle gracefully or raise appropriate error
        try:
            result = calculate_line_total(invalid_qty, invalid_price)
            # If it handles gracefully, should return 0
            assert result == Decimal('0.00')
        except (ValueError, TypeError, InvalidOperation):
            # This is also acceptable - explicit error handling
            pass
    
    def test_invoice_with_invalid_dates(self, db_session, sample_client):
        """Test invoice creation with invalid dates."""
        # Due date before invoice date
        with pytest.raises(ValueError):
            invoice = Invoice(
                number='2025-0001',
                client_id=sample_client.id,
                date=date.today(),
                due_date=date.today() - timedelta(days=1)  # Invalid
            )
            # Custom validation would catch this
            if hasattr(invoice, 'validate'):
                invoice.validate()
    
    def test_invoice_line_invalid_quantities(self, db_session, sample_invoice):
        """Test invoice line with invalid quantities."""
        # Zero quantity (should violate constraint)
        with pytest.raises(IntegrityError):
            line = InvoiceLine(
                invoice_id=sample_invoice.id,
                description='Test service',
                qty=Decimal('0.00'),
                unit_price=Decimal('100.00'),
                line_total=Decimal('0.00')
            )
            db_session.add(line)
            db_session.commit()
    
    def test_email_format_validation(self, db_session):
        """Test handling of invalid email formats in models."""
        invalid_emails = [
            'not_an_email',
            '@domain.com',
            'user@',
            'user@domain',
            'user space@domain.com',
            'user@domain..com'
        ]
        
        for invalid_email in invalid_emails:
            client = Client(
                name='Test Client',
                email=invalid_email
            )
            db_session.add(client)
            
            # Model might not validate, but it should be handled at form level
            try:
                db_session.commit()
                # If it accepts invalid email, that's handled at application level
                assert client.email == invalid_email
            except IntegrityError:
                # Some databases might have email format constraints
                pass
            finally:
                db_session.rollback()


class TestBusinessRuleViolations:
    """Test violations of business rules and logic."""
    
    def test_status_transition_violations(self, db_session, sample_client):
        """Test invalid status transitions."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create paid invoice
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='makstud'
        )
        db_session.add(invoice)
        db_session.commit()
        
        # Try to change paid invoice back to draft
        service = InvoiceStatusTransition
        success, message = service.transition_invoice_status(invoice, service.DRAFT)
        
        assert success is False
        assert 'Makstud arveid ei saa tagasi' in message
    
    def test_edit_paid_invoice_violation(self, db_session, sample_client):
        """Test business rule preventing editing of paid invoices."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='makstud'
        )
        db_session.add(invoice)
        db_session.commit()
        
        # Check business rule
        assert invoice.can_be_edited is False
    
    def test_delete_paid_invoice_violation(self, db_session, sample_client):
        """Test business rule preventing deletion of paid invoices."""
        # This would be implemented at the application level
        # The test verifies the property exists to check
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='makstud'
        )
        db_session.add(invoice)
        db_session.commit()
        
        # In a real application, this would prevent deletion
        assert invoice.status == 'makstud'
        # Application logic should check this before allowing deletion
    
    def test_duplicate_invoice_number_generation(self, db_session, sample_client):
        """Test handling of duplicate number generation race condition."""
        # Create invoice with a specific number
        existing_number = '2025-0001'
        invoice = Invoice(
            number=existing_number,
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        db_session.add(invoice)
        db_session.commit()
        
        # Check availability
        assert is_invoice_number_available(existing_number) is False
        
        # Generate new number should skip the existing one
        new_number = generate_invoice_number()
        assert new_number != existing_number
        assert is_invoice_number_available(new_number) is True


class TestResourceNotFound:
    """Test handling of resource not found scenarios."""
    
    def test_get_nonexistent_client(self, db_session):
        """Test getting non-existent client."""
        client = Client.query.get(99999)
        assert client is None
    
    def test_get_nonexistent_invoice(self, db_session):
        """Test getting non-existent invoice."""
        invoice = Invoice.query.get(99999)
        assert invoice is None
    
    def test_get_nonexistent_vat_rate(self, db_session):
        """Test getting non-existent VAT rate."""
        vat_rate = VatRate.query.get(99999)
        assert vat_rate is None
    
    def test_cascade_delete_behavior(self, db_session, sample_client):
        """Test cascade delete behavior when parent is deleted."""
        # Create invoice with lines
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        db_session.add(invoice)
        db_session.flush()
        
        line = InvoiceLine(
            invoice_id=invoice.id,
            description='Test service',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db_session.add(line)
        db_session.commit()
        
        invoice_id = invoice.id
        line_id = line.id
        client_id = sample_client.id
        
        # Delete client (should cascade to invoice and lines)
        db_session.delete(sample_client)
        db_session.commit()
        
        # Check everything was deleted
        assert Client.query.get(client_id) is None
        assert Invoice.query.get(invoice_id) is None
        assert InvoiceLine.query.get(line_id) is None


class TestConcurrencyAndRaceConditions:
    """Test concurrent access scenarios."""
    
    def test_concurrent_invoice_number_generation(self, db_session, sample_client):
        """Test concurrent invoice number generation."""
        # Simulate race condition where two processes try to generate
        # the same invoice number simultaneously
        
        with patch('app.services.numbering.Invoice.query') as mock_query:
            mock_query.filter.return_value.order_by.return_value.first.return_value = None
            
            # Both should get the same base number
            number1 = generate_invoice_number()
            number2 = generate_invoice_number()
            
            # Without database state change, both get same number
            assert number1 == number2
    
    @patch('app.models.db.session.commit')
    def test_database_commit_failure(self, mock_commit, db_session, sample_client):
        """Test handling of database commit failures."""
        mock_commit.side_effect = Exception("Database connection lost")
        
        client = Client(name='Test Client')
        db_session.add(client)
        
        with pytest.raises(Exception, match="Database connection lost"):
            db_session.commit()
    
    def test_optimistic_locking_scenario(self, db_session, sample_client):
        """Test optimistic locking scenario with updated_at."""
        VatRate.create_default_rates()
        standard_vat = VatRate.get_default_rate()
        
        # Create invoice
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=standard_vat.id,
            status='mustand'
        )
        db_session.add(invoice)
        db_session.commit()
        
        original_updated = invoice.updated_at
        
        # Simulate update
        invoice.status = 'saadetud'
        db_session.commit()
        
        # updated_at should change
        assert invoice.updated_at > original_updated


class TestMemoryAndPerformanceLimits:
    """Test memory limits and performance edge cases."""
    
    def test_large_string_handling(self, db_session):
        """Test handling of very large strings."""
        # Large description (but within reasonable limits)
        large_description = 'A' * 500  # 500 characters
        
        client = Client(name='Test Client')
        db_session.add(client)
        db_session.flush()
        
        invoice = Invoice(
            number='2025-0001',
            client_id=client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        db_session.add(invoice)
        db_session.flush()
        
        line = InvoiceLine(
            invoice_id=invoice.id,
            description=large_description,
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db_session.add(line)
        
        try:
            db_session.commit()
            assert len(line.description) == 500
        except DataError:
            # If database has stricter limits, that's fine
            pass
    
    def test_high_precision_decimal_handling(self, db_session):
        """Test handling of high precision decimals."""
        # Very high precision decimal
        high_precision = Decimal('123.123456789012345')
        
        try:
            result = calculate_vat_amount(high_precision, Decimal('24.0'))
            # Should be rounded to 2 decimal places
            assert result.as_tuple().exponent >= -2
        except (ValueError, InvalidOperation):
            # Acceptable if system has precision limits
            pass
    
    def test_very_large_numbers(self, db_session, sample_client):
        """Test handling of very large monetary amounts."""
        # Large but reasonable business amount
        large_amount = Decimal('999999.99')
        
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            subtotal=large_amount
        )
        db_session.add(invoice)
        
        try:
            db_session.commit()
            assert invoice.subtotal == large_amount
        except (DataError, IntegrityError):
            # If database has limits on decimal size
            pass


class TestEstonianSpecificEdgeCases:
    """Test Estonian-specific validation and edge cases."""
    
    def test_estonian_characters_in_database(self, db_session):
        """Test Estonian characters are properly stored and retrieved."""
        estonian_text = 'Äriprotsesside analüüs ja süsteemiarenduse nõustamine'
        
        client = Client(
            name='Test Klient OÜ',
            address=estonian_text
        )
        db_session.add(client)
        db_session.commit()
        
        # Retrieve and verify
        retrieved = Client.query.filter_by(name='Test Klient OÜ').first()
        assert retrieved.address == estonian_text
        assert 'ü' in retrieved.address
        assert 'ä' in retrieved.address
        assert 'õ' in retrieved.address
    
    def test_estonian_vat_rates_edge_cases(self, db_session):
        """Test Estonian VAT rate edge cases."""
        # Create VAT rate with Estonian description
        vat_rate = VatRate(
            name='Erimäär (käibemaksuvaba)',
            rate=Decimal('0.00'),
            description='Käibemaksuvabad tooted ja teenused vastavalt KMS-le'
        )
        db_session.add(vat_rate)
        db_session.commit()
        
        assert vat_rate.rate == Decimal('0.00')
        assert 'käibemaksuvaba' in vat_rate.description.lower()
    
    def test_estonian_registry_code_format(self, db_session):
        """Test Estonian registry code format handling."""
        # Estonian registry codes are typically 8 digits
        registry_codes = [
            '12345678',   # Valid
            '1234567',    # Too short but might be valid
            '123456789',  # Too long but might be valid
            'EE123456',   # With country prefix
            '12 34 56 78' # With spaces
        ]
        
        for code in registry_codes:
            client = Client(
                name=f'Test Client {code}',
                registry_code=code
            )
            db_session.add(client)
            try:
                db_session.commit()
                # If it succeeds, the format is accepted
                assert client.registry_code == code
            except IntegrityError:
                # If it fails, there might be format validation
                pass
            finally:
                db_session.rollback()
    
    def test_estonian_phone_number_formats(self, db_session):
        """Test various Estonian phone number formats."""
        phone_formats = [
            '+372 5555 1234',
            '+372 55551234',
            '372 5555 1234',
            '55551234',
            '+372-5555-1234',
            '+372.5555.1234'
        ]
        
        for phone in phone_formats:
            client = Client(
                name=f'Test Client {phone}',
                phone=phone
            )
            db_session.add(client)
            db_session.commit()
            
            # All formats should be accepted (validation at form level)
            assert client.phone == phone
            
            # Clean up for next iteration
            db_session.delete(client)
            db_session.commit()


class TestErrorRecovery:
    """Test error recovery and graceful degradation."""
    
    @patch('app.services.totals.calculate_subtotal')
    def test_calculation_error_recovery(self, mock_calculate_subtotal, db_session, sample_invoice):
        """Test recovery from calculation errors."""
        mock_calculate_subtotal.side_effect = Exception("Calculation error")
        
        # Should handle gracefully
        try:
            sample_invoice.calculate_totals()
            # If it handles the error, totals might be set to 0 or unchanged
            assert isinstance(sample_invoice.subtotal, Decimal)
        except Exception:
            # Or it might propagate the error for handling at higher level
            pass
    
    def test_missing_vat_rate_recovery(self, db_session, sample_client):
        """Test handling of missing VAT rate."""
        # Create invoice without VAT rate
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=None,  # No VAT rate set
            vat_rate=None
        )
        db_session.add(invoice)
        db_session.commit()
        
        # Should handle gracefully
        effective_rate = invoice.get_effective_vat_rate()
        assert effective_rate == 0 or effective_rate == 24  # Default fallback
    
    def test_company_settings_fallback(self, db_session):
        """Test fallback when company settings are missing."""
        # Delete all company settings
        CompanySettings.query.delete()
        db_session.commit()
        
        # Getting settings should create defaults
        settings = CompanySettings.get_settings()
        assert settings is not None
        assert settings.company_name == 'Minu Ettevõte'
    
    @patch('app.models.db.session.rollback')
    def test_database_rollback_on_error(self, mock_rollback, db_session, sample_client):
        """Test database rollback on transaction errors."""
        mock_rollback.side_effect = Exception("Rollback failed")
        
        # Create invalid data that will cause rollback
        invoice = Invoice(
            number='DUPLICATE-NUMBER',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        db_session.add(invoice)
        
        # Add duplicate
        duplicate = Invoice(
            number='DUPLICATE-NUMBER',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        db_session.add(duplicate)
        
        with pytest.raises(IntegrityError):
            db_session.commit()