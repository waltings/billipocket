"""
Unit tests for service layer functionality.

Tests cover:
- Invoice numbering service (generation, validation, availability)
- Status transition service (validation, business rules)
- Totals calculation service (line totals, VAT, precision)
- Estonian business logic and VAT calculations
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from app.services.numbering import (
    generate_invoice_number,
    is_invoice_number_available,
    validate_invoice_number_format
)
from app.services.status_transitions import InvoiceStatusTransition
from app.services.totals import (
    calculate_line_total,
    calculate_subtotal,
    calculate_vat_amount,
    calculate_total,
    calculate_invoice_totals
)
from app.models import Invoice, InvoiceLine


class TestNumberingService:
    """Test invoice numbering service."""
    
    def test_generate_invoice_number_current_year(self, db_session):
        """Test generating invoice number for current year."""
        current_year = date.today().year
        
        # With no existing invoices
        number = generate_invoice_number()
        expected = f"{current_year}-0001"
        assert number == expected
    
    def test_generate_invoice_number_specific_year(self, db_session):
        """Test generating invoice number for specific year."""
        test_year = 2024
        
        # With no existing invoices for that year
        number = generate_invoice_number(test_year)
        expected = f"{test_year}-0001"
        assert number == expected
    
    def test_generate_invoice_number_with_existing_invoices(self, db_session, sample_client):
        """Test number generation with existing invoices."""
        current_year = date.today().year
        
        # Create existing invoices
        existing_numbers = [f"{current_year}-0001", f"{current_year}-0003", f"{current_year}-0005"]
        
        for number in existing_numbers:
            invoice = Invoice(
                number=number,
                client_id=sample_client.id,
                date=date.today(),
                due_date=date.today() + timedelta(days=14)
            )
            db_session.add(invoice)
        
        db_session.commit()
        
        # Should generate next number after highest existing
        next_number = generate_invoice_number()
        expected = f"{current_year}-0006"
        assert next_number == expected
    
    def test_generate_invoice_number_year_rollover(self, db_session, sample_client):
        """Test number generation handles year rollover correctly."""
        current_year = date.today().year
        previous_year = current_year - 1
        
        # Create invoices from previous year
        old_invoice = Invoice(
            number=f"{previous_year}-0099",
            client_id=sample_client.id,
            date=date(previous_year, 12, 31),
            due_date=date(current_year, 1, 14)
        )
        db_session.add(old_invoice)
        db_session.commit()
        
        # Should start from 0001 for new year
        new_number = generate_invoice_number(current_year)
        expected = f"{current_year}-0001"
        assert new_number == expected
    
    def test_is_invoice_number_available_true(self, db_session):
        """Test number availability check when number is free."""
        test_number = "2025-9999"
        
        assert is_invoice_number_available(test_number) is True
    
    def test_is_invoice_number_available_false(self, db_session, sample_invoice):
        """Test number availability check when number is taken."""
        existing_number = sample_invoice.number
        
        assert is_invoice_number_available(existing_number) is False
    
    @pytest.mark.parametrize("number,expected", [
        ("2025-0001", True),
        ("2024-0999", True),
        ("2023-0001", True),
        ("25-0001", False),      # Year too short
        ("2025-01", False),      # Number too short
        ("2025-00001", False),   # Number too long
        ("ABCD-0001", False),    # Non-numeric year
        ("2025-ABCD", False),    # Non-numeric number
        ("2025_0001", False),    # Wrong separator
        ("20250001", False),     # No separator
        ("", False),             # Empty string
        (None, False),           # None value
        ("2025-0001-001", False) # Too many parts
    ])
    def test_validate_invoice_number_format(self, number, expected):
        """Test invoice number format validation."""
        result = validate_invoice_number_format(number)
        assert result == expected


class TestStatusTransitionService:
    """Test invoice status transition service."""
    
    def test_valid_status_constants(self):
        """Test that status constants are defined correctly."""
        assert InvoiceStatusTransition.DRAFT == 'mustand'
        assert InvoiceStatusTransition.SENT == 'saadetud'
        assert InvoiceStatusTransition.PAID == 'makstud'
        assert InvoiceStatusTransition.OVERDUE == 'tähtaeg ületatud'
        
        assert len(InvoiceStatusTransition.VALID_STATUSES) == 4
    
    def test_can_transition_valid_transitions(self):
        """Test valid status transitions."""
        service = InvoiceStatusTransition
        
        # Draft to sent
        can_change, error = service.can_transition_to(service.DRAFT, service.SENT)
        assert can_change is True
        assert error is None
        
        # Sent to paid
        can_change, error = service.can_transition_to(service.SENT, service.PAID)
        assert can_change is True
        assert error is None
        
        # Sent to overdue
        can_change, error = service.can_transition_to(service.SENT, service.OVERDUE)
        assert can_change is True
        assert error is None
        
        # Same status (no change)
        can_change, error = service.can_transition_to(service.SENT, service.SENT)
        assert can_change is True
        assert error is None
    
    def test_can_transition_invalid_transitions(self):
        """Test invalid status transitions."""
        service = InvoiceStatusTransition
        
        # Paid to any unpaid status should fail
        invalid_transitions = [
            (service.PAID, service.DRAFT),
            (service.PAID, service.SENT),
            (service.PAID, service.OVERDUE)
        ]
        
        for current, new in invalid_transitions:
            can_change, error = service.can_transition_to(current, new)
            assert can_change is False
            assert 'Makstud arveid ei saa tagasi' in error
    
    def test_can_transition_invalid_status(self):
        """Test transition to invalid status."""
        service = InvoiceStatusTransition
        
        can_change, error = service.can_transition_to(service.DRAFT, 'invalid_status')
        assert can_change is False
        assert 'Vigane staatus' in error
    
    def test_can_transition_overdue_to_sent_while_overdue(self, sample_client, db_session):
        """Test overdue to sent transition when still overdue."""
        service = InvoiceStatusTransition
        
        # Create overdue invoice
        overdue_invoice = Invoice(
            number='TEST-OVERDUE-001',
            client_id=sample_client.id,
            date=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=5),  # Still overdue
            status=service.OVERDUE
        )
        
        can_change, error = service.can_transition_overdue_to_sent(overdue_invoice, service.SENT)
        assert can_change is False
        assert 'tähtaja ületanud arvet ei saa saadetud staatusesse muuta' in error.lower()
    
    def test_can_transition_overdue_to_sent_not_overdue(self, sample_client, db_session):
        """Test overdue to sent transition when no longer overdue."""
        service = InvoiceStatusTransition
        
        # Create invoice that was overdue but isn't anymore
        not_overdue_invoice = Invoice(
            number='TEST-NOT-OVERDUE-001',
            client_id=sample_client.id,
            date=date.today() - timedelta(days=30),
            due_date=date.today() + timedelta(days=5),  # Future due date
            status=service.OVERDUE
        )
        
        can_change, error = service.can_transition_overdue_to_sent(not_overdue_invoice, service.SENT)
        assert can_change is True
        assert error is None
    
    def test_get_valid_transitions_draft(self):
        """Test getting valid transitions from draft status."""
        service = InvoiceStatusTransition
        
        transitions = service.get_valid_transitions(service.DRAFT)
        assert len(transitions) == 4
        assert service.DRAFT in transitions
        assert service.SENT in transitions
        assert service.PAID in transitions
        assert service.OVERDUE in transitions
    
    def test_get_valid_transitions_paid(self):
        """Test getting valid transitions from paid status."""
        service = InvoiceStatusTransition
        
        transitions = service.get_valid_transitions(service.PAID)
        assert len(transitions) == 1
        assert transitions == [service.PAID]
    
    def test_get_status_display_name(self):
        """Test getting human-readable status names."""
        service = InvoiceStatusTransition
        
        assert service.get_status_display_name(service.DRAFT) == 'Mustand'
        assert service.get_status_display_name(service.SENT) == 'Saadetud'
        assert service.get_status_display_name(service.PAID) == 'Makstud'
        assert service.get_status_display_name(service.OVERDUE) == 'Tähtaeg ületatud'
        
        # Unknown status
        assert service.get_status_display_name('unknown') == 'unknown'
    
    def test_get_status_css_class(self):
        """Test getting CSS classes for status styling."""
        service = InvoiceStatusTransition
        
        assert service.get_status_css_class(service.DRAFT) == 'badge-secondary'
        assert service.get_status_css_class(service.SENT) == 'badge-primary'
        assert service.get_status_css_class(service.PAID) == 'badge-success'
        assert service.get_status_css_class(service.OVERDUE) == 'badge-danger'
        
        # Unknown status
        assert service.get_status_css_class('unknown') == 'badge-light'
    
    @patch('app.models.Invoice.update_overdue_invoices')
    def test_update_overdue_invoices(self, mock_update):
        """Test bulk update of overdue invoices."""
        mock_update.return_value = 5
        
        service = InvoiceStatusTransition
        updated_count = service.update_overdue_invoices()
        
        assert updated_count == 5
        mock_update.assert_called_once()


class TestTotalsService:
    """Test invoice totals calculation service."""
    
    @pytest.mark.parametrize("qty,unit_price,expected", [
        (Decimal('1.00'), Decimal('100.00'), Decimal('100.00')),
        (Decimal('2.50'), Decimal('80.00'), Decimal('200.00')),
        (Decimal('3.333'), Decimal('37.037'), Decimal('123.46')),  # Rounding test
        (Decimal('0.5'), Decimal('199.99'), Decimal('100.00')),
        (1.5, 66.67, Decimal('100.01')),  # Float inputs
        ('2', '50.25', Decimal('100.50')),  # String inputs
        (None, Decimal('100.00'), Decimal('0.00')),  # None quantity
        (Decimal('1.00'), None, Decimal('0.00'))  # None price
    ])
    def test_calculate_line_total(self, qty, unit_price, expected):
        """Test line total calculations with various inputs."""
        result = calculate_line_total(qty, unit_price)
        assert result == expected
    
    def test_calculate_subtotal_with_lines(self, sample_invoice, db_session):
        """Test subtotal calculation with multiple lines."""
        lines = [
            InvoiceLine(
                invoice_id=sample_invoice.id,
                description='Service 1',
                qty=Decimal('1.00'),
                unit_price=Decimal('100.00'),
                line_total=Decimal('100.00')
            ),
            InvoiceLine(
                invoice_id=sample_invoice.id,
                description='Service 2',
                qty=Decimal('2.00'),
                unit_price=Decimal('75.50'),
                line_total=Decimal('151.00')
            ),
            InvoiceLine(
                invoice_id=sample_invoice.id,
                description='Service 3',
                qty=Decimal('0.5'),
                unit_price=Decimal('299.98'),
                line_total=Decimal('149.99')
            )
        ]
        
        for line in lines:
            db_session.add(line)
        db_session.commit()
        
        subtotal = calculate_subtotal(lines)
        expected = Decimal('100.00') + Decimal('151.00') + Decimal('149.99')
        assert subtotal == expected
    
    def test_calculate_subtotal_empty_lines(self):
        """Test subtotal calculation with no lines."""
        result = calculate_subtotal([])
        assert result == Decimal('0.00')
    
    def test_calculate_subtotal_lines_without_totals(self):
        """Test subtotal calculation with lines missing line_total."""
        mock_line = MagicMock()
        mock_line.line_total = None
        
        result = calculate_subtotal([mock_line])
        assert result == Decimal('0.00')
    
    @pytest.mark.parametrize("subtotal,vat_rate,expected", [
        (Decimal('100.00'), Decimal('24.00'), Decimal('24.00')),  # Estonian standard
        (Decimal('100.00'), Decimal('22.00'), Decimal('22.00')),  # Legacy rate
        (Decimal('100.00'), Decimal('20.00'), Decimal('20.00')),  # Reduced rate
        (Decimal('100.00'), Decimal('9.00'), Decimal('9.00')),    # Lower reduced rate
        (Decimal('100.00'), Decimal('0.00'), Decimal('0.00')),    # Tax-free
        (Decimal('344.26'), Decimal('24.00'), Decimal('82.62')),  # Common service amount
        (Decimal('123.45'), Decimal('24.00'), Decimal('29.63')),  # Rounding test
        (100.00, 24.00, Decimal('24.00')),  # Float inputs
        ('150.00', '24.00', Decimal('36.00')),  # String inputs
        (None, Decimal('24.00'), Decimal('0.00')),  # None subtotal
        (Decimal('100.00'), None, Decimal('0.00'))   # None VAT rate
    ])
    def test_calculate_vat_amount(self, subtotal, vat_rate, expected):
        """Test VAT amount calculations."""
        result = calculate_vat_amount(subtotal, vat_rate)
        assert result == expected
    
    @pytest.mark.parametrize("subtotal,vat_amount,expected", [
        (Decimal('100.00'), Decimal('24.00'), Decimal('124.00')),
        (Decimal('344.26'), Decimal('82.62'), Decimal('426.88')),
        (Decimal('0.00'), Decimal('0.00'), Decimal('0.00')),
        (100.50, 24.12, Decimal('124.62')),  # Float inputs
        ('200.00', '48.00', Decimal('248.00')),  # String inputs
        (None, Decimal('24.00'), Decimal('24.00')),  # None subtotal
        (Decimal('100.00'), None, Decimal('100.00'))  # None VAT amount
    ])
    def test_calculate_total(self, subtotal, vat_amount, expected):
        """Test total amount calculations."""
        result = calculate_total(subtotal, vat_amount)
        assert result == expected
    
    def test_calculate_invoice_totals_integration(self, sample_client, db_session):
        """Test complete invoice totals calculation."""
        # Create invoice with VAT rate
        invoice = Invoice(
            number='TOTALS-TEST-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate=Decimal('24.00')
        )
        db_session.add(invoice)
        db_session.flush()
        
        # Add lines to invoice
        lines_data = [
            ('Web development', Decimal('1.00'), Decimal('300.00')),
            ('Consulting', Decimal('4.00'), Decimal('75.00')),
            ('Project management', Decimal('2.50'), Decimal('100.00'))
        ]
        
        for description, qty, unit_price in lines_data:
            line_total = calculate_line_total(qty, unit_price)
            line = InvoiceLine(
                invoice_id=invoice.id,
                description=description,
                qty=qty,
                unit_price=unit_price,
                line_total=line_total
            )
            db_session.add(line)
        
        db_session.commit()
        
        # Calculate totals
        result = calculate_invoice_totals(invoice)
        
        expected_subtotal = Decimal('300.00') + Decimal('300.00') + Decimal('250.00')  # 850.00
        expected_vat = expected_subtotal * Decimal('0.24')  # 204.00
        expected_total = expected_subtotal + expected_vat  # 1054.00
        
        assert result['subtotal'] == expected_subtotal
        assert result['vat_amount'] == expected_vat
        assert result['total'] == expected_total
        
        # Verify invoice was updated
        assert invoice.subtotal == expected_subtotal
        assert invoice.total == expected_total
    
    def test_calculate_invoice_totals_empty_lines(self, sample_client, db_session):
        """Test invoice totals calculation with no lines."""
        invoice = Invoice(
            number='EMPTY-TOTALS-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate=Decimal('24.00')
        )
        db_session.add(invoice)
        db_session.commit()
        
        result = calculate_invoice_totals(invoice)
        
        assert result['subtotal'] == Decimal('0.00')
        assert result['vat_amount'] == Decimal('0.00')
        assert result['total'] == Decimal('0.00')
        
        assert invoice.subtotal == Decimal('0.00')
        assert invoice.total == Decimal('0.00')
    
    def test_decimal_precision_maintained(self):
        """Test that calculations maintain proper decimal precision."""
        # Test with amounts that could cause precision issues
        test_cases = [
            (Decimal('33.333'), Decimal('3.00'), Decimal('100.00')),
            (Decimal('0.1'), Decimal('10.00'), Decimal('1.00')),
            (Decimal('1.0'), Decimal('33.33'), Decimal('33.33'))
        ]
        
        for qty, unit_price, expected in test_cases:
            result = calculate_line_total(qty, unit_price)
            # Check that result has at most 2 decimal places
            assert result.as_tuple().exponent >= -2
            
        # Test VAT calculation precision
        vat_result = calculate_vat_amount(Decimal('123.456'), Decimal('24.0'))
        assert vat_result.as_tuple().exponent >= -2
        
        # Test total calculation precision
        total_result = calculate_total(Decimal('100.001'), Decimal('24.001'))
        assert total_result.as_tuple().exponent >= -2
    
    def test_rounding_behavior(self):
        """Test that rounding follows ROUND_HALF_UP behavior."""
        # Test cases where rounding matters
        test_cases = [
            (Decimal('3.333'), Decimal('37.037'), Decimal('123.46')),  # Should round up
            (Decimal('2.222'), Decimal('45.004'), Decimal('100.01')),  # Should round up
            (Decimal('1.111'), Decimal('90.009'), Decimal('100.02'))   # Should round up
        ]
        
        for qty, unit_price, expected in test_cases:
            result = calculate_line_total(qty, unit_price)
            assert result == expected


class TestServiceIntegration:
    """Test integration between services."""
    
    def test_complete_invoice_workflow(self, sample_client, db_session):
        """Test complete invoice creation workflow using all services."""
        # Generate invoice number
        invoice_number = generate_invoice_number()
        assert validate_invoice_number_format(invoice_number)
        assert is_invoice_number_available(invoice_number)
        
        # Create invoice
        invoice = Invoice(
            number=invoice_number,
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate=Decimal('24.00'),
            status=InvoiceStatusTransition.DRAFT
        )
        db_session.add(invoice)
        db_session.flush()
        
        # Add lines
        lines_data = [
            ('Service 1', Decimal('1.00'), Decimal('100.00')),
            ('Service 2', Decimal('2.00'), Decimal('50.00'))
        ]
        
        for description, qty, unit_price in lines_data:
            line_total = calculate_line_total(qty, unit_price)
            line = InvoiceLine(
                invoice_id=invoice.id,
                description=description,
                qty=qty,
                unit_price=unit_price,
                line_total=line_total
            )
            db_session.add(line)
        
        db_session.commit()
        
        # Calculate totals
        totals = calculate_invoice_totals(invoice)
        
        # Verify calculations
        assert totals['subtotal'] == Decimal('200.00')
        assert totals['vat_amount'] == Decimal('48.00')
        assert totals['total'] == Decimal('248.00')
        
        # Test status transitions
        service = InvoiceStatusTransition
        
        # Draft to sent
        success, message = service.transition_invoice_status(invoice, service.SENT)
        assert success is True
        assert invoice.status == service.SENT
        
        # Sent to paid
        success, message = service.transition_invoice_status(invoice, service.PAID)
        assert success is True
        assert invoice.status == service.PAID
        
        # Verify number is no longer available
        assert is_invoice_number_available(invoice_number) is False
    
    def test_error_handling_integration(self, sample_client, db_session):
        """Test error handling across services."""
        # Test invalid number format with status transitions
        invoice = Invoice(
            number='INVALID-FORMAT',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            status=InvoiceStatusTransition.DRAFT
        )
        
        # Number format should be invalid
        assert validate_invoice_number_format(invoice.number) is False
        
        # But status transitions should still work
        service = InvoiceStatusTransition
        success, message = service.transition_invoice_status(invoice, service.SENT)
        assert success is True
        
        # Test totals calculation with problematic data
        invoice.vat_rate = None  # This could cause issues
        
        # Should handle gracefully
        totals = calculate_invoice_totals(invoice)
        assert totals['vat_amount'] == Decimal('0.00')