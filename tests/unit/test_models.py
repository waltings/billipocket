"""
Unit tests for SQLAlchemy models.

Tests cover:
- Client model creation, validation, and properties
- Invoice model with auto-numbering and Estonian VAT calculations
- InvoiceLine model and calculations
- Model relationships (Client→Invoices, Invoice→Lines)
- Status transitions and validations
- Estonian VAT calculations (22%)
- Database constraints and edge cases
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.models import Client, Invoice, InvoiceLine, VatRate, CompanySettings


class TestClientModel:
    """Test cases for the Client model."""
    
    def test_client_creation(self, db_session):
        """Test basic client creation."""
        client = Client(
            name='Test Client OÜ',
            registry_code='12345678',
            email='test@client.ee',
            phone='+372 5555 1234',
            address='Test Address 123, Tallinn'
        )
        
        db_session.add(client)
        db_session.commit()
        
        assert client.id is not None
        assert client.name == 'Test Client OÜ'
        assert client.registry_code == '12345678'
        assert client.email == 'test@client.ee'
        assert client.phone == '+372 5555 1234'
        assert client.address == 'Test Address 123, Tallinn'
        assert client.created_at is not None
    
    def test_client_creation_minimal(self, db_session):
        """Test client creation with only required fields."""
        client = Client(name='Minimal Client')
        
        db_session.add(client)
        db_session.commit()
        
        assert client.id is not None
        assert client.name == 'Minimal Client'
        assert client.registry_code is None
        assert client.email is None
        assert client.phone is None
        assert client.address is None
    
    def test_client_name_required(self, db_session):
        """Test that client name is required."""
        client = Client()
        
        db_session.add(client)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_client_repr(self, sample_client):
        """Test client string representation."""
        assert repr(sample_client) == f'<Client {sample_client.name}>'
    
    def test_client_invoice_count_property(self, sample_client, db_session):
        """Test invoice_count property calculation."""
        # Initially no invoices
        assert sample_client.invoice_count == 0
        
        # Add invoices
        invoice1 = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        invoice2 = Invoice(
            number='2025-0002',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        
        db_session.add(invoice1)
        db_session.add(invoice2)
        db_session.commit()
        
        assert sample_client.invoice_count == 2
    
    def test_client_last_invoice_date_property(self, sample_client, db_session):
        """Test last_invoice_date property calculation."""
        # Initially no invoices
        assert sample_client.last_invoice_date is None
        
        # Add invoices with different dates
        earlier_date = date(2025, 8, 1)
        later_date = date(2025, 8, 10)
        
        invoice1 = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=earlier_date,
            due_date=earlier_date + timedelta(days=14)
        )
        invoice2 = Invoice(
            number='2025-0002',
            client_id=sample_client.id,
            date=later_date,
            due_date=later_date + timedelta(days=14)
        )
        
        db_session.add(invoice1)
        db_session.add(invoice2)
        db_session.commit()
        
        assert sample_client.last_invoice_date == later_date
    
    def test_client_total_revenue_property(self, sample_client, db_session):
        """Test total_revenue property calculation."""
        # Initially no invoices
        assert sample_client.total_revenue == 0
        
        # Add invoices with different statuses
        invoice1 = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            total=Decimal('100.00'),
            status='makstud'
        )
        invoice2 = Invoice(
            number='2025-0002',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            total=Decimal('200.00'),
            status='saadetud'
        )
        invoice3 = Invoice(
            number='2025-0003',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            total=Decimal('50.00'),
            status='mustand'  # Should not count toward revenue
        )
        
        db_session.add_all([invoice1, invoice2, invoice3])
        db_session.commit()
        
        # Only paid and sent invoices count toward revenue
        assert sample_client.total_revenue == Decimal('300.00')
    
    def test_client_cascade_delete(self, sample_client, db_session):
        """Test that deleting client deletes associated invoices."""
        # Add invoice to client
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        db_session.add(invoice)
        db_session.commit()
        
        invoice_id = invoice.id
        client_id = sample_client.id
        
        # Delete client
        db_session.delete(sample_client)
        db_session.commit()
        
        # Check that invoice was also deleted
        deleted_client = db_session.get(Client, client_id)
        deleted_invoice = db_session.get(Invoice, invoice_id)
        
        assert deleted_client is None
        assert deleted_invoice is None


class TestInvoiceModel:
    """Test cases for the Invoice model."""
    
    def test_invoice_creation(self, db_session, sample_client):
        """Test basic invoice creation."""
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date(2025, 8, 10),
            due_date=date(2025, 8, 24),
            subtotal=Decimal('100.00'),
            vat_rate=Decimal('22.00'),
            total=Decimal('122.00'),
            status='mustand'
        )
        
        db_session.add(invoice)
        db_session.commit()
        
        assert invoice.id is not None
        assert invoice.number == '2025-0001'
        assert invoice.client_id == sample_client.id
        assert invoice.date == date(2025, 8, 10)
        assert invoice.due_date == date(2025, 8, 24)
        assert invoice.subtotal == Decimal('100.00')
        assert invoice.vat_rate == Decimal('22.00')
        assert invoice.total == Decimal('122.00')
        assert invoice.status == 'mustand'
        assert invoice.created_at is not None
    
    def test_invoice_defaults(self, db_session, sample_client):
        """Test invoice creation with default values."""
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            due_date=date.today() + timedelta(days=14)
        )
        
        db_session.add(invoice)
        db_session.commit()
        
        assert invoice.date == date.today()
        assert invoice.subtotal == Decimal('0')
        assert invoice.vat_rate == Decimal('22')  # Estonian VAT rate
        assert invoice.total == Decimal('0')
        assert invoice.status == 'mustand'
    
    def test_invoice_unique_number_constraint(self, db_session, sample_client):
        """Test that invoice numbers must be unique."""
        invoice1 = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            due_date=date.today() + timedelta(days=14)
        )
        invoice2 = Invoice(
            number='2025-0001',  # Same number
            client_id=sample_client.id,
            due_date=date.today() + timedelta(days=14)
        )
        
        db_session.add(invoice1)
        db_session.commit()
        
        db_session.add(invoice2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_invoice_required_fields(self, db_session):
        """Test that required fields are enforced."""
        # Missing number
        invoice1 = Invoice(client_id=1, due_date=date.today())
        db_session.add(invoice1)
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
        
        # Missing client_id
        invoice2 = Invoice(number='2025-0001', due_date=date.today())
        db_session.add(invoice2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_invoice_vat_amount_property(self, sample_invoice):
        """Test VAT amount calculation property."""
        sample_invoice.subtotal = Decimal('100.00')
        sample_invoice.vat_rate = Decimal('22.00')
        
        assert sample_invoice.vat_amount == Decimal('22.00')
        
        # Test with different rates
        sample_invoice.vat_rate = Decimal('20.00')
        assert sample_invoice.vat_amount == Decimal('20.00')
    
    def test_invoice_is_overdue_property(self, db_session, sample_client):
        """Test is_overdue property calculation."""
        # Current invoice - not overdue
        current_invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            status='saadetud'
        )
        assert not current_invoice.is_overdue
        
        # Overdue invoice
        overdue_invoice = Invoice(
            number='2025-0002',
            client_id=sample_client.id,
            date=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=5),
            status='saadetud'
        )
        assert overdue_invoice.is_overdue
        
        # Paid invoice - not overdue even if past due date
        paid_invoice = Invoice(
            number='2025-0003',
            client_id=sample_client.id,
            date=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=5),
            status='makstud'
        )
        assert not paid_invoice.is_overdue
    
    def test_invoice_calculate_totals_method(self, db_session, sample_client):
        """Test calculate_totals method with invoice lines."""
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate=Decimal('22.00')
        )
        db_session.add(invoice)
        db_session.flush()
        
        # Add invoice lines
        line1 = InvoiceLine(
            invoice_id=invoice.id,
            description='Service 1',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        line2 = InvoiceLine(
            invoice_id=invoice.id,
            description='Service 2',
            qty=Decimal('2.00'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('100.00')
        )
        
        db_session.add_all([line1, line2])
        db_session.commit()
        
        # Calculate totals
        invoice.calculate_totals()
        
        assert invoice.subtotal == Decimal('200.00')
        assert invoice.total == Decimal('244.00')  # 200 + 22% VAT = 244
    
    def test_invoice_update_status_if_overdue(self, db_session, sample_client):
        """Test automatic status update for overdue invoices."""
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=5),
            status='saadetud'
        )
        
        db_session.add(invoice)
        db_session.commit()
        
        # Update status
        invoice.update_status_if_overdue()
        
        assert invoice.status == 'tähtaeg ületatud'
    
    def test_invoice_status_constraints(self, db_session, sample_client):
        """Test that only valid statuses are allowed."""
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            due_date=date.today() + timedelta(days=14),
            status='invalid_status'
        )
        
        db_session.add(invoice)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_invoice_positive_amount_constraints(self, db_session, sample_client):
        """Test that amounts must be non-negative."""
        # Negative subtotal
        invoice1 = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            due_date=date.today() + timedelta(days=14),
            subtotal=Decimal('-10.00')
        )
        
        db_session.add(invoice1)
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
        
        # Negative total
        invoice2 = Invoice(
            number='2025-0002',
            client_id=sample_client.id,
            due_date=date.today() + timedelta(days=14),
            total=Decimal('-10.00')
        )
        
        db_session.add(invoice2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_invoice_repr(self, sample_invoice):
        """Test invoice string representation."""
        assert repr(sample_invoice) == f'<Invoice {sample_invoice.number}>'


class TestInvoiceLineModel:
    """Test cases for the InvoiceLine model."""
    
    def test_invoice_line_creation(self, db_session, sample_invoice):
        """Test basic invoice line creation."""
        line = InvoiceLine(
            invoice_id=sample_invoice.id,
            description='Test Service',
            qty=Decimal('2.50'),
            unit_price=Decimal('80.00'),
            line_total=Decimal('200.00')
        )
        
        db_session.add(line)
        db_session.commit()
        
        assert line.id is not None
        assert line.invoice_id == sample_invoice.id
        assert line.description == 'Test Service'
        assert line.qty == Decimal('2.50')
        assert line.unit_price == Decimal('80.00')
        assert line.line_total == Decimal('200.00')
    
    def test_invoice_line_defaults(self, db_session, sample_invoice):
        """Test invoice line creation with default values."""
        line = InvoiceLine(
            invoice_id=sample_invoice.id,
            description='Test Service',
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        
        db_session.add(line)
        db_session.commit()
        
        assert line.qty == Decimal('1')  # Default quantity
    
    def test_invoice_line_required_fields(self, db_session, sample_invoice):
        """Test that required fields are enforced."""
        # Missing description
        line1 = InvoiceLine(
            invoice_id=sample_invoice.id,
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db_session.add(line1)
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
        
        # Missing unit_price
        line2 = InvoiceLine(
            invoice_id=sample_invoice.id,
            description='Test Service',
            qty=Decimal('1.00'),
            line_total=Decimal('100.00')
        )
        db_session.add(line2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_invoice_line_calculate_total_method(self, sample_invoice_line):
        """Test calculate_total method."""
        sample_invoice_line.qty = Decimal('3.00')
        sample_invoice_line.unit_price = Decimal('25.50')
        
        sample_invoice_line.calculate_total()
        
        assert sample_invoice_line.line_total == Decimal('76.50')
    
    def test_invoice_line_constraints(self, db_session, sample_invoice):
        """Test database constraints on invoice lines."""
        # Negative quantity
        line1 = InvoiceLine(
            invoice_id=sample_invoice.id,
            description='Test Service',
            qty=Decimal('-1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db_session.add(line1)
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
        
        # Negative unit price
        line2 = InvoiceLine(
            invoice_id=sample_invoice.id,
            description='Test Service',
            qty=Decimal('1.00'),
            unit_price=Decimal('-100.00'),
            line_total=Decimal('100.00')
        )
        db_session.add(line2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
        
        # Negative line total
        line3 = InvoiceLine(
            invoice_id=sample_invoice.id,
            description='Test Service',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('-100.00')
        )
        db_session.add(line3)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_invoice_line_repr(self, sample_invoice_line):
        """Test invoice line string representation."""
        expected = f'<InvoiceLine {sample_invoice_line.description[:30]}...>'
        assert repr(sample_invoice_line) == expected
    
    def test_invoice_line_cascade_delete(self, db_session, sample_invoice):
        """Test that deleting invoice deletes associated lines."""
        # Add line to invoice
        line = InvoiceLine(
            invoice_id=sample_invoice.id,
            description='Test Service',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        db_session.add(line)
        db_session.commit()
        
        line_id = line.id
        invoice_id = sample_invoice.id
        
        # Delete invoice
        db_session.delete(sample_invoice)
        db_session.commit()
        
        # Check that line was also deleted
        deleted_invoice = db_session.get(Invoice, invoice_id)
        deleted_line = db_session.get(InvoiceLine, line_id)
        
        assert deleted_invoice is None
        assert deleted_line is None


class TestModelRelationships:
    """Test cases for model relationships."""
    
    def test_client_invoice_relationship(self, db_session, sample_client):
        """Test Client to Invoice relationship."""
        # Create invoices for the client
        invoice1 = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        invoice2 = Invoice(
            number='2025-0002',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        
        db_session.add_all([invoice1, invoice2])
        db_session.commit()
        
        # Test forward relationship
        assert len(sample_client.invoices) == 2
        assert invoice1 in sample_client.invoices
        assert invoice2 in sample_client.invoices
        
        # Test reverse relationship
        assert invoice1.client == sample_client
        assert invoice2.client == sample_client
    
    def test_invoice_line_relationship(self, db_session, sample_invoice):
        """Test Invoice to InvoiceLine relationship."""
        # Create lines for the invoice
        line1 = InvoiceLine(
            invoice_id=sample_invoice.id,
            description='Service 1',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        line2 = InvoiceLine(
            invoice_id=sample_invoice.id,
            description='Service 2',
            qty=Decimal('2.00'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('100.00')
        )
        
        db_session.add_all([line1, line2])
        db_session.commit()
        
        # Test forward relationship
        assert len(sample_invoice.lines) == 2
        assert line1 in sample_invoice.lines
        assert line2 in sample_invoice.lines
        
        # Test reverse relationship
        assert line1.invoice == sample_invoice
        assert line2.invoice == sample_invoice


class TestEstonianVATCalculations:
    """Test Estonian VAT calculations (22%)."""
    
    def test_standard_vat_calculation(self, vat_calculation_test_cases):
        """Test standard VAT calculations with Estonian rate."""
        for case in vat_calculation_test_cases:
            # Create a mock invoice to test VAT property
            invoice = Invoice()
            invoice.subtotal = case['subtotal']
            invoice.vat_rate = case['vat_rate']
            
            assert invoice.vat_amount == case['expected_vat']
            
            # Test total calculation
            total = invoice.subtotal + invoice.vat_amount
            assert total == case['expected_total']
    
    def test_zero_vat_calculation(self):
        """Test VAT calculation with 0% rate."""
        invoice = Invoice()
        invoice.subtotal = Decimal('100.00')
        invoice.vat_rate = Decimal('0.00')
        
        assert invoice.vat_amount == Decimal('0.00')
    
    def test_invoice_totals_with_estonian_vat(self, db_session, sample_client):
        """Test complete invoice calculation with Estonian VAT."""
        invoice = Invoice(
            number='2025-0001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate=Decimal('22.00')  # Estonian VAT
        )
        db_session.add(invoice)
        db_session.flush()
        
        # Add lines
        lines_data = [
            ('Web development', Decimal('1.00'), Decimal('300.00')),
            ('Consulting', Decimal('4.00'), Decimal('75.00')),
            ('Project management', Decimal('2.50'), Decimal('100.00'))
        ]
        
        for desc, qty, unit_price in lines_data:
            line_total = qty * unit_price
            line = InvoiceLine(
                invoice_id=invoice.id,
                description=desc,
                qty=qty,
                unit_price=unit_price,
                line_total=line_total
            )
            db_session.add(line)
        
        db_session.commit()
        
        # Calculate totals
        invoice.calculate_totals()
        
        # Verify calculations
        expected_subtotal = Decimal('300.00') + Decimal('300.00') + Decimal('250.00')  # 850.00
        expected_vat = expected_subtotal * Decimal('0.22')  # 187.00
        expected_total = expected_subtotal + expected_vat  # 1037.00
        
        assert invoice.subtotal == expected_subtotal
        assert invoice.vat_amount == expected_vat
        assert invoice.total == expected_total


class TestVatRateModel:
    """Test cases for the VatRate model."""
    
    def test_vat_rate_creation(self, db_session):
        """Test basic VAT rate creation."""
        vat_rate = VatRate(
            name='Test Rate (25%)',
            rate=Decimal('25.00'),
            description='Test VAT rate'
        )
        
        db_session.add(vat_rate)
        db_session.commit()
        
        assert vat_rate.id is not None
        assert vat_rate.name == 'Test Rate (25%)'
        assert vat_rate.rate == Decimal('25.00')
        assert vat_rate.description == 'Test VAT rate'
        assert vat_rate.is_active is True
        assert vat_rate.created_at is not None
    
    def test_vat_rate_required_fields(self, db_session):
        """Test VAT rate creation with missing required fields."""
        # Missing name
        vat_rate1 = VatRate(rate=Decimal('20.00'))
        db_session.add(vat_rate1)
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
        
        # Missing rate
        vat_rate2 = VatRate(name='Test Rate')
        db_session.add(vat_rate2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_vat_rate_unique_constraints(self, db_session):
        """Test VAT rate unique constraints."""
        # Create first VAT rate
        vat_rate1 = VatRate(
            name='Standard Rate (24%)',
            rate=Decimal('24.00')
        )
        db_session.add(vat_rate1)
        db_session.commit()
        
        # Try to create duplicate name
        vat_rate2 = VatRate(
            name='Standard Rate (24%)',
            rate=Decimal('25.00')
        )
        db_session.add(vat_rate2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
        
        # Try to create duplicate rate
        vat_rate3 = VatRate(
            name='Another Standard Rate',
            rate=Decimal('24.00')
        )
        db_session.add(vat_rate3)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_vat_rate_constraints(self, db_session):
        """Test VAT rate validation constraints."""
        # Negative rate
        vat_rate1 = VatRate(
            name='Negative Rate',
            rate=Decimal('-5.00')
        )
        db_session.add(vat_rate1)
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
        
        # Rate over 100%
        vat_rate2 = VatRate(
            name='Over 100%',
            rate=Decimal('150.00')
        )
        db_session.add(vat_rate2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_vat_rate_repr(self, db_session):
        """Test VAT rate string representation."""
        vat_rate = VatRate(
            name='Standard Rate (24%)',
            rate=Decimal('24.00')
        )
        db_session.add(vat_rate)
        db_session.commit()
        
        expected = '<VatRate Standard Rate (24%): 24.00%>'
        assert repr(vat_rate) == expected
    
    def test_get_active_rates(self, db_session):
        """Test getting active VAT rates ordered by rate."""
        # Create multiple VAT rates
        rates = [
            VatRate(name='Zero (0%)', rate=Decimal('0.00')),
            VatRate(name='Reduced (9%)', rate=Decimal('9.00')),
            VatRate(name='Standard (24%)', rate=Decimal('24.00')),
            VatRate(name='High (25%)', rate=Decimal('25.00')),
            VatRate(name='Inactive (30%)', rate=Decimal('30.00'), is_active=False)
        ]
        
        for rate in rates:
            db_session.add(rate)
        db_session.commit()
        
        active_rates = VatRate.get_active_rates()
        
        # Should return 4 active rates
        assert len(active_rates) == 4
        
        # Should be ordered by rate ascending
        rates_values = [rate.rate for rate in active_rates]
        assert rates_values == [Decimal('0.00'), Decimal('9.00'), Decimal('24.00'), Decimal('25.00')]
        
        # Should not include inactive rate
        inactive_found = any(rate.rate == Decimal('30.00') for rate in active_rates)
        assert not inactive_found
    
    def test_get_default_rate(self, db_session):
        """Test getting Estonian default VAT rate (24%)."""
        # Without any rates
        default_rate = VatRate.get_default_rate()
        assert default_rate is None
        
        # Create default rate
        standard_rate = VatRate(
            name='Standardmäär (24%)',
            rate=Decimal('24.00')
        )
        db_session.add(standard_rate)
        db_session.commit()
        
        default_rate = VatRate.get_default_rate()
        assert default_rate is not None
        assert default_rate.rate == Decimal('24.00')
    
    def test_create_default_rates(self, db_session):
        """Test creating Estonian default VAT rates."""
        # Ensure clean state
        VatRate.query.delete()
        db_session.commit()
        
        # Create default rates
        VatRate.create_default_rates()
        
        # Check that all expected rates were created
        rates = VatRate.query.order_by(VatRate.rate.asc()).all()
        assert len(rates) == 4
        
        expected_rates = [Decimal('0.00'), Decimal('9.00'), Decimal('20.00'), Decimal('24.00')]
        actual_rates = [rate.rate for rate in rates]
        assert actual_rates == expected_rates
        
        # Check Estonian names
        zero_rate = VatRate.query.filter_by(rate=0).first()
        assert zero_rate.name == 'Maksuvaba (0%)'
        assert 'Käibemaksuvaba' in zero_rate.description
        
        standard_rate = VatRate.query.filter_by(rate=24).first()
        assert standard_rate.name == 'Standardmäär (24%)'
        assert 'standardne käibemaksumäär' in standard_rate.description
    
    def test_create_default_rates_idempotent(self, db_session):
        """Test that creating default rates multiple times is safe."""
        initial_count = VatRate.query.count()
        
        # Create defaults multiple times
        VatRate.create_default_rates()
        VatRate.create_default_rates()
        VatRate.create_default_rates()
        
        # Should still have the same number of rates
        final_count = VatRate.query.count()
        expected_count = initial_count + 4  # 4 default rates
        assert final_count == expected_count
    
    def test_vat_rate_invoice_relationship(self, db_session, sample_client):
        """Test relationship between VAT rates and invoices."""
        # Create VAT rate
        vat_rate = VatRate(
            name='Test Rate (20%)',
            rate=Decimal('20.00')
        )
        db_session.add(vat_rate)
        db_session.flush()
        
        # Create invoice with VAT rate
        invoice = Invoice(
            number='VAT-TEST-001',
            client_id=sample_client.id,
            date=date.today(),
            due_date=date.today() + timedelta(days=14),
            vat_rate_id=vat_rate.id
        )
        db_session.add(invoice)
        db_session.commit()
        
        # Test relationships
        assert invoice.vat_rate_obj == vat_rate
        assert invoice in vat_rate.invoices
        
        # Test effective VAT rate
        assert invoice.get_effective_vat_rate() == Decimal('20.00')


class TestCompanySettingsModel:
    """Test cases for the CompanySettings model."""
    
    def test_company_settings_creation(self, db_session):
        """Test basic company settings creation."""
        settings = CompanySettings(
            company_name='Test Company OÜ',
            company_address='Test Address 123, Tallinn',
            company_registry_code='12345678',
            company_vat_number='EE123456789',
            company_phone='+372 1234 5678',
            company_email='info@testcompany.ee',
            company_website='https://testcompany.ee',
            default_vat_rate=Decimal('24.00'),
            default_pdf_template='modern'
        )
        
        db_session.add(settings)
        db_session.commit()
        
        assert settings.id is not None
        assert settings.company_name == 'Test Company OÜ'
        assert settings.company_address == 'Test Address 123, Tallinn'
        assert settings.company_registry_code == '12345678'
        assert settings.company_vat_number == 'EE123456789'
        assert settings.company_phone == '+372 1234 5678'
        assert settings.company_email == 'info@testcompany.ee'
        assert settings.company_website == 'https://testcompany.ee'
        assert settings.default_vat_rate == Decimal('24.00')
        assert settings.default_pdf_template == 'modern'
        assert settings.created_at is not None
        assert settings.updated_at is not None
    
    def test_company_settings_defaults(self, db_session):
        """Test company settings default values."""
        settings = CompanySettings(company_name='Minimal Company')
        
        db_session.add(settings)
        db_session.commit()
        
        assert settings.company_address == ''
        assert settings.company_registry_code == ''
        assert settings.company_vat_number == ''
        assert settings.company_phone == ''
        assert settings.company_email == ''
        assert settings.company_website == ''
        assert settings.company_logo_url == ''
        assert settings.default_vat_rate == Decimal('24.00')  # Estonian default
        assert settings.default_pdf_template == 'standard'
        assert settings.invoice_terms == ''
    
    def test_company_settings_required_name(self, db_session):
        """Test that company name is required."""
        settings = CompanySettings()  # No name
        
        db_session.add(settings)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_get_settings_existing(self, db_session):
        """Test getting existing company settings."""
        # Create settings
        existing_settings = CompanySettings(
            company_name='Existing Company',
            company_email='existing@company.ee'
        )
        db_session.add(existing_settings)
        db_session.commit()
        
        # Get settings
        settings = CompanySettings.get_settings()
        
        assert settings.id == existing_settings.id
        assert settings.company_name == 'Existing Company'
        assert settings.company_email == 'existing@company.ee'
    
    def test_get_settings_create_default(self, db_session):
        """Test getting settings creates default if none exist."""
        # Ensure no settings exist
        CompanySettings.query.delete()
        db_session.commit()
        
        # Get settings should create default
        settings = CompanySettings.get_settings()
        
        assert settings is not None
        assert settings.id is not None
        assert settings.company_name == 'Minu Ettevõte'
        
        # Verify it was saved to database
        db_settings = CompanySettings.query.first()
        assert db_settings is not None
        assert db_settings.id == settings.id
    
    def test_company_settings_repr(self, db_session):
        """Test company settings string representation."""
        settings = CompanySettings(company_name='Test Representation OÜ')
        db_session.add(settings)
        db_session.commit()
        
        expected = '<CompanySettings "Test Representation OÜ">'
        assert repr(settings) == expected
    
    def test_company_settings_estonian_defaults(self, db_session):
        """Test Estonian-specific default values."""
        settings = CompanySettings.get_settings()
        
        # Should default to Estonian VAT rate
        assert settings.default_vat_rate == Decimal('24.00')
        
        # Should have Estonian default company name
        if not CompanySettings.query.filter(CompanySettings.company_name != 'Minu Ettevõte').first():
            assert settings.company_name == 'Minu Ettevõte'
    
    def test_company_settings_pdf_templates(self, db_session):
        """Test PDF template setting validation."""
        valid_templates = ['standard', 'modern', 'elegant']
        
        for template in valid_templates:
            settings = CompanySettings(
                company_name=f'Company with {template} template',
                default_pdf_template=template
            )
            db_session.add(settings)
            db_session.commit()
            
            assert settings.default_pdf_template == template
            
            # Clean up for next iteration
            db_session.delete(settings)
            db_session.commit()
    
    def test_company_settings_vat_number_format(self, db_session):
        """Test Estonian VAT number format."""
        # Estonian VAT numbers start with EE
        settings = CompanySettings(
            company_name='Estonian Company',
            company_vat_number='EE123456789'
        )
        db_session.add(settings)
        db_session.commit()
        
        assert settings.company_vat_number.startswith('EE')
        assert len(settings.company_vat_number) == 11  # EE + 9 digits
    
    def test_company_settings_phone_format(self, db_session):
        """Test Estonian phone number format."""
        estonian_phones = [
            '+372 1234 5678',
            '+372 5555 1234',
            '372 6666 7890'
        ]
        
        for phone in estonian_phones:
            settings = CompanySettings(
                company_name=f'Company with phone {phone}',
                company_phone=phone
            )
            db_session.add(settings)
            db_session.commit()
            
            assert '372' in settings.company_phone  # Estonian country code
            
            # Clean up for next iteration
            db_session.delete(settings)
            db_session.commit()
    
    def test_company_settings_updated_at(self, db_session):
        """Test that updated_at is automatically updated."""
        settings = CompanySettings(company_name='Update Test Company')
        db_session.add(settings)
        db_session.commit()
        
        original_updated = settings.updated_at
        
        # Update settings
        settings.company_phone = '+372 9999 0000'
        db_session.commit()
        
        # updated_at should be newer
        assert settings.updated_at > original_updated