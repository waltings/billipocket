"""
Advanced pytest fixtures for comprehensive testing.

These fixtures build upon the basic fixtures in conftest.py to provide
more complex test scenarios and data patterns commonly needed in
invoice management system testing.
"""

import pytest
import random
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from app.models import db, Client, Invoice, InvoiceLine, VatRate, CompanySettings
from .test_data_factory import TestDataFactory, EstonianDataFactory


@pytest.fixture
def data_factory(db_session):
    """Test data factory instance configured with test database session."""
    return TestDataFactory(db_session)


@pytest.fixture
def estonian_factory():
    """Estonian-specific data factory for generating realistic Estonian data."""
    return EstonianDataFactory()


@pytest.fixture
def vat_rates_setup(db_session):
    """Setup Estonian VAT rates for testing."""
    # Clean existing rates
    VatRate.query.delete()
    db_session.commit()
    
    # Create default Estonian rates
    VatRate.create_default_rates()
    db_session.commit()
    
    return VatRate.get_active_rates()


@pytest.fixture
def company_settings_estonian(db_session):
    """Estonian company settings for testing."""
    # Clean existing settings
    CompanySettings.query.delete()
    db_session.commit()
    
    settings = CompanySettings(
        company_name='Testimise Ettevõte OÜ',
        company_address='Narva mnt 7, 10117 Tallinn, Estonia',
        company_registry_code='12345678',
        company_vat_number='EE123456789',
        company_phone='+372 5555 1234',
        company_email='info@testimine.ee',
        company_website='https://testimine.ee',
        default_vat_rate=Decimal('24.00'),
        default_pdf_template='standard',
        invoice_terms='Maksetähtaeg 14 päeva. Viivise määr 0,5% päevas.'
    )
    
    db_session.add(settings)
    db_session.commit()
    
    return settings


@pytest.fixture
def multiple_clients_estonian(db_session, data_factory):
    """Multiple Estonian clients with diverse business types."""
    clients = []
    
    # IT Consulting company
    clients.append(data_factory.create_client(
        name='IT Konsultatsioonid OÜ',
        registry_code='11111111',
        email='info@itkonsult.ee',
        phone='+372 5551 1111',
        address='Rävala pst 5, 10143 Tallinn, Estonia'
    ))
    
    # Manufacturing company
    clients.append(data_factory.create_client(
        name='Tootmise Lahendused AS',
        registry_code='22222222',
        email='kontakt@tootmine.ee',
        phone='+372 5552 2222',
        address='Tartu mnt 67, 51006 Tartu, Estonia'
    ))
    
    # Design agency
    clients.append(data_factory.create_client(
        name='Disaini Stuudio OÜ',
        registry_code='33333333',
        email='hello@disain.ee',
        phone='+372 5553 3333',
        address='Viru 14, 20308 Narva, Estonia'
    ))
    
    # Small service business
    clients.append(data_factory.create_client(
        name='Väike Teenus UÜ',
        registry_code='44444444',
        email='info@vaiketeenus.ee',
        phone='+372 5554 4444',
        address='Pärnu mnt 89, 80010 Pärnu, Estonia'
    ))
    
    db_session.commit()
    return clients


@pytest.fixture
def invoices_different_statuses(db_session, data_factory, multiple_clients_estonian, vat_rates_setup):
    """Invoices in different statuses for testing status workflows."""
    invoices = []
    clients = multiple_clients_estonian
    standard_vat = VatRate.get_default_rate()
    
    # Draft invoices (can be edited/deleted)
    for i in range(3):
        invoice = data_factory.create_complete_invoice(
            client=clients[i % len(clients)],
            status='mustand',
            vat_rate=standard_vat,
            line_count=3
        )
        invoices.append(invoice)
    
    # Sent invoices (can be paid or become overdue)
    for i in range(4):
        invoice = data_factory.create_complete_invoice(
            client=clients[i % len(clients)],
            status='saadetud',
            vat_rate=standard_vat,
            date=date.today() - timedelta(days=random.randint(1, 10)),
            line_count=2
        )
        invoices.append(invoice)
    
    # Paid invoices (cannot be edited)
    for i in range(2):
        invoice = data_factory.create_complete_invoice(
            client=clients[i % len(clients)],
            status='makstud',
            vat_rate=standard_vat,
            date=date.today() - timedelta(days=random.randint(15, 30)),
            line_count=1
        )
        invoices.append(invoice)
    
    # Overdue invoices
    for i in range(2):
        overdue_date = date.today() - timedelta(days=random.randint(5, 20))
        invoice = data_factory.create_complete_invoice(
            client=clients[i % len(clients)],
            status='tähtaeg ületatud',
            vat_rate=standard_vat,
            date=overdue_date - timedelta(days=15),
            due_date=overdue_date,
            line_count=3
        )
        invoices.append(invoice)
    
    return {
        'all': invoices,
        'draft': [inv for inv in invoices if inv.status == 'mustand'],
        'sent': [inv for inv in invoices if inv.status == 'saadetud'],
        'paid': [inv for inv in invoices if inv.status == 'makstud'],
        'overdue': [inv for inv in invoices if inv.status == 'tähtaeg ületatud']
    }


@pytest.fixture
def invoices_with_different_vat_rates(db_session, data_factory, sample_client, vat_rates_setup):
    """Invoices using different VAT rates for calculation testing."""
    invoices = []
    vat_rates = VatRate.get_active_rates()
    
    for vat_rate in vat_rates:
        invoice = data_factory.create_invoice(
            client=sample_client,
            vat_rate=vat_rate,
            status='saadetud'
        )
        
        # Add consistent line for calculation testing
        data_factory.create_invoice_line(
            invoice=invoice,
            description=f'Test service with {vat_rate.rate}% VAT',
            qty=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        
        invoice.calculate_totals()
        invoices.append(invoice)
    
    db_session.commit()
    return invoices


@pytest.fixture
def large_invoice_dataset(db_session, data_factory, vat_rates_setup):
    """Large dataset for performance and pagination testing."""
    import random
    
    # Create 20 clients
    clients = [data_factory.create_client() for _ in range(20)]
    
    # Create 200 invoices
    invoices = []
    statuses = ['mustand', 'saadetud', 'makstud', 'tähtaeg ületatud']
    
    for i in range(200):
        client = random.choice(clients)
        status = random.choice(statuses)
        
        # Create date in the past year
        days_ago = random.randint(0, 365)
        invoice_date = date.today() - timedelta(days=days_ago)
        
        invoice = data_factory.create_complete_invoice(
            client=client,
            status=status,
            date=invoice_date,
            line_count=random.randint(1, 5)
        )
        invoices.append(invoice)
    
    return {
        'clients': clients,
        'invoices': invoices,
        'total_count': len(invoices)
    }


@pytest.fixture
def complex_invoice_calculations(db_session, data_factory, sample_client, vat_rates_setup):
    """Complex invoice with various line types for calculation edge cases."""
    standard_vat = VatRate.get_default_rate()
    
    invoice = data_factory.create_invoice(
        client=sample_client,
        vat_rate=standard_vat,
        status='mustand'
    )
    
    # Various line types that test calculation edge cases
    lines_data = [
        # Normal service
        {'description': 'Veebiarenduse teenused', 'qty': Decimal('40.0'), 'unit_price': Decimal('75.50')},
        # Fractional quantity
        {'description': 'Konsultatsioon', 'qty': Decimal('2.75'), 'unit_price': Decimal('120.00')},
        # Large quantity, small price
        {'description': 'Andmesisestus', 'qty': Decimal('1000.0'), 'unit_price': Decimal('0.15')},
        # Small quantity, large price
        {'description': 'Serveri seadistus', 'qty': Decimal('0.5'), 'unit_price': Decimal('2400.00')},
        # High precision numbers
        {'description': 'Automaatika', 'qty': Decimal('33.333'), 'unit_price': Decimal('15.15')},
        # Zero price item (free service)
        {'description': 'Garantii', 'qty': Decimal('1.0'), 'unit_price': Decimal('0.00')}
    ]
    
    for line_data in lines_data:
        line_data['invoice_id'] = invoice.id
        line_data['line_total'] = line_data['qty'] * line_data['unit_price']
        line = InvoiceLine(**line_data)
        db_session.add(line)
    
    db_session.commit()
    invoice.calculate_totals()
    db_session.commit()
    
    return invoice


@pytest.fixture
def invoice_numbering_scenarios(db_session, data_factory, sample_client):
    """Invoices with different numbering patterns for numbering service tests."""
    current_year = date.today().year
    previous_year = current_year - 1
    
    # Create invoices with gaps in numbering
    numbers = [
        f'{current_year}-0001',
        f'{current_year}-0003',
        f'{current_year}-0005',
        f'{current_year}-0010',
        f'{previous_year}-0001',
        f'{previous_year}-0099'
    ]
    
    invoices = []
    for number in numbers:
        year = int(number.split('-')[0])
        invoice_date = date(year, random.randint(1, 12), random.randint(1, 28))
        
        invoice = data_factory.create_invoice(
            client=sample_client,
            number=number,
            date=invoice_date
        )
        invoices.append(invoice)
    
    return {
        'invoices': invoices,
        'current_year_numbers': [n for n in numbers if n.startswith(str(current_year))],
        'previous_year_numbers': [n for n in numbers if n.startswith(str(previous_year))],
        'expected_next_number': f'{current_year}-0011'
    }


@pytest.fixture
def business_scenarios(db_session, data_factory):
    """Complete business scenarios for integration testing."""
    scenarios = {}
    
    # Small business scenario
    scenarios['small_business'] = data_factory.create_business_scenario('small_business')
    
    # Consulting firm scenario
    scenarios['consulting_firm'] = data_factory.create_business_scenario('consulting_firm')
    
    # Software company scenario
    scenarios['software_company'] = data_factory.create_business_scenario('software_company')
    
    return scenarios


@pytest.fixture
def error_scenarios(db_session, data_factory, sample_client):
    """Data scenarios that should trigger various error conditions."""
    scenarios = {}
    
    # Invoice with no lines (should have zero totals)
    scenarios['empty_invoice'] = data_factory.create_invoice(
        client=sample_client,
        status='mustand'
    )
    
    # Invalid status transition invoice
    scenarios['paid_invoice'] = data_factory.create_complete_invoice(
        client=sample_client,
        status='makstud',
        line_count=1
    )
    
    # Overdue invoice for status testing
    overdue_date = date.today() - timedelta(days=10)
    scenarios['overdue_invoice'] = data_factory.create_complete_invoice(
        client=sample_client,
        status='saadetud',
        date=overdue_date - timedelta(days=10),
        due_date=overdue_date,
        line_count=1
    )
    
    return scenarios


@pytest.fixture
def multilingual_data(db_session, data_factory):
    """Test data with both Estonian and English content."""
    # Client with English name
    english_client = data_factory.create_client(
        name='International Solutions Ltd',
        email='info@international.com',
        address='123 Business Street, 10001 Tallinn, Estonia'
    )
    
    # Client with Estonian name
    estonian_client = data_factory.create_client(
        name='Eesti Lahendused OÜ',
        email='info@eestilahendused.ee',
        address='Narva mnt 25, 10117 Tallinn, Estonia'
    )
    
    return {
        'english_client': english_client,
        'estonian_client': estonian_client
    }


@pytest.fixture
def performance_test_data(db_session, data_factory):
    """Large dataset for performance testing."""
    import random
    
    # Create many clients
    clients = [data_factory.create_client() for _ in range(100)]
    
    # Create many invoices with lines
    invoices = []
    for _ in range(1000):
        client = random.choice(clients)
        invoice = data_factory.create_complete_invoice(
            client=client,
            line_count=random.randint(1, 10)
        )
        invoices.append(invoice)
    
    return {
        'clients': clients,
        'invoices': invoices,
        'total_clients': len(clients),
        'total_invoices': len(invoices)
    }


# Helper functions for common test patterns
@pytest.fixture
def assert_invoice_totals():
    """Helper function to assert invoice totals are correctly calculated."""
    def _assert_totals(invoice: Invoice, expected_subtotal: Decimal = None, expected_total: Decimal = None):
        if expected_subtotal is not None:
            assert invoice.subtotal == expected_subtotal, f"Expected subtotal {expected_subtotal}, got {invoice.subtotal}"
        
        if expected_total is not None:
            assert invoice.total == expected_total, f"Expected total {expected_total}, got {invoice.total}"
        
        # Assert VAT calculation is correct
        expected_vat = invoice.subtotal * (invoice.get_effective_vat_rate() / 100)
        expected_vat = expected_vat.quantize(Decimal('0.01'))
        actual_vat = invoice.vat_amount.quantize(Decimal('0.01'))
        
        assert actual_vat == expected_vat, f"VAT calculation incorrect. Expected {expected_vat}, got {actual_vat}"
        
        # Assert total = subtotal + VAT
        calculated_total = invoice.subtotal + invoice.vat_amount
        assert invoice.total == calculated_total, f"Total should equal subtotal + VAT. Got {invoice.total}, expected {calculated_total}"
    
    return _assert_totals


@pytest.fixture
def assert_estonian_format():
    """Helper function to assert Estonian formatting and content."""
    def _assert_format(text: str, should_contain_estonian: bool = True):
        if should_contain_estonian:
            estonian_chars = ['ä', 'ö', 'ü', 'õ']
            has_estonian = any(char in text.lower() for char in estonian_chars)
            
            estonian_words = ['teenus', 'arve', 'maksetähtaeg', 'käibemaks', 'kokku']
            has_estonian_words = any(word in text.lower() for word in estonian_words)
            
            # Should have either Estonian characters or words
            assert has_estonian or has_estonian_words, f"Expected Estonian content in: {text}"
    
    return _assert_format