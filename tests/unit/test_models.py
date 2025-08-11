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

from app.models import Client, Invoice, InvoiceLine


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