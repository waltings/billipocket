"""
Pytest configuration and fixtures for the BilliPocket invoice manager tests.

This module provides:
- Flask test app setup with in-memory SQLite database
- Sample Estonian test data (clients, invoices, invoice lines)
- Test fixtures for models and services
- CSRF exemption for testing
- Database setup and cleanup
"""

import pytest
import tempfile
import os
from datetime import date, timedelta
from decimal import Decimal

from app import create_app
from app.models import db, Client, Invoice, InvoiceLine
from app.config import Config


class TestConfig(Config):
    """Test-specific configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing
    SECRET_KEY = 'test-secret-key-for-testing-only'


@pytest.fixture(scope='session')
def app():
    """Create Flask application for testing."""
    app = create_app()
    app.config.from_object(TestConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def app_context(app):
    """Application context for testing."""
    with app.app_context():
        yield app


@pytest.fixture(scope='function')
def db_session(app_context):
    """Database session for testing."""
    db.create_all()
    yield db.session
    db.session.rollback()
    db.drop_all()


@pytest.fixture
def sample_client_data():
    """Sample client data using Estonian companies."""
    return {
        'name': 'Testimise OÜ',
        'registry_code': '12345678',
        'email': 'info@testimine.ee',
        'phone': '+372 5555 1234',
        'address': 'Narva mnt 7, 10117 Tallinn, Estonia'
    }


@pytest.fixture
def sample_client_2_data():
    """Second sample client for testing relationships."""
    return {
        'name': 'Arendus AS',
        'registry_code': '87654321',
        'email': 'kontakt@arendus.ee',
        'phone': '+372 5555 5678',
        'address': 'Tartu mnt 2, 51006 Tartu, Estonia'
    }


@pytest.fixture
def sample_client(db_session, sample_client_data):
    """Create a sample client in the database."""
    client = Client(**sample_client_data)
    db_session.add(client)
    db_session.commit()
    return client


@pytest.fixture
def sample_client_2(db_session, sample_client_2_data):
    """Create a second sample client in the database."""
    client = Client(**sample_client_2_data)
    db_session.add(client)
    db_session.commit()
    return client


@pytest.fixture
def sample_invoice_data():
    """Sample invoice data with Estonian descriptions."""
    return {
        'number': '2025-0001',
        'date': date(2025, 8, 10),
        'due_date': date(2025, 8, 24),
        'vat_rate': Decimal('22.00'),  # Estonian VAT rate
        'status': 'mustand'
    }


@pytest.fixture
def sample_invoice(db_session, sample_client, sample_invoice_data):
    """Create a sample invoice in the database."""
    invoice_data = sample_invoice_data.copy()
    invoice_data['client_id'] = sample_client.id
    invoice = Invoice(**invoice_data)
    db_session.add(invoice)
    db_session.commit()
    return invoice


@pytest.fixture
def sample_invoice_line_data():
    """Sample invoice line data in Estonian."""
    return {
        'description': 'Veebiarenduse teenused',
        'qty': Decimal('1.00'),
        'unit_price': Decimal('344.26'),
        'line_total': Decimal('344.26')
    }


@pytest.fixture
def sample_invoice_line(db_session, sample_invoice, sample_invoice_line_data):
    """Create a sample invoice line in the database."""
    line_data = sample_invoice_line_data.copy()
    line_data['invoice_id'] = sample_invoice.id
    line = InvoiceLine(**line_data)
    db_session.add(line)
    db_session.commit()
    return line


@pytest.fixture
def multiple_invoice_lines_data():
    """Multiple invoice lines data for testing calculations."""
    return [
        {
            'description': 'Veebiarenduse teenused',
            'qty': Decimal('1.00'),
            'unit_price': Decimal('300.00'),
            'line_total': Decimal('300.00')
        },
        {
            'description': 'Konsultatsiooniteenused',
            'qty': Decimal('5.00'),
            'unit_price': Decimal('80.00'),
            'line_total': Decimal('400.00')
        },
        {
            'description': 'Projektijuhtimine',
            'qty': Decimal('2.50'),
            'unit_price': Decimal('120.00'),
            'line_total': Decimal('300.00')
        }
    ]


@pytest.fixture
def invoice_with_multiple_lines(db_session, sample_client, multiple_invoice_lines_data):
    """Create an invoice with multiple lines for testing calculations."""
    invoice = Invoice(
        number='2025-0002',
        client_id=sample_client.id,
        date=date(2025, 8, 10),
        due_date=date(2025, 8, 24),
        vat_rate=Decimal('22.00'),
        status='saadetud'
    )
    db_session.add(invoice)
    db_session.flush()
    
    for line_data in multiple_invoice_lines_data:
        line_data_copy = line_data.copy()
        line_data_copy['invoice_id'] = invoice.id
        line = InvoiceLine(**line_data_copy)
        db_session.add(line)
    
    db_session.commit()
    
    # Calculate totals
    invoice.calculate_totals()
    db_session.commit()
    
    return invoice


@pytest.fixture
def form_data_client():
    """Form data for client creation in Estonian."""
    return {
        'name': 'Test Klient OÜ',
        'registry_code': '11223344',
        'email': 'test@klient.ee',
        'phone': '+372 5555 0000',
        'address': 'Testiaadress 123, 10001 Tallinn'
    }


@pytest.fixture
def form_data_invoice():
    """Form data for invoice creation in Estonian."""
    return {
        'client_id': '1',
        'date': '2025-08-10',
        'due_date': '2025-08-24',
        'vat_rate': '22.00',
        'status': 'mustand',
        'lines-0-description': 'Testimise teenused',
        'lines-0-qty': '1.00',
        'lines-0-unit_price': '100.00'
    }


@pytest.fixture
def overdue_invoice(db_session, sample_client):
    """Create an overdue invoice for testing status updates."""
    invoice = Invoice(
        number='2025-0003',
        client_id=sample_client.id,
        date=date.today() - timedelta(days=30),
        due_date=date.today() - timedelta(days=10),  # 10 days overdue
        vat_rate=Decimal('22.00'),
        status='saadetud',
        subtotal=Decimal('100.00'),
        total=Decimal('122.00')
    )
    db_session.add(invoice)
    db_session.commit()
    return invoice


@pytest.fixture
def clients_for_search(db_session):
    """Create multiple clients for search testing."""
    clients = [
        Client(name='Alpha OÜ', email='alpha@test.ee', phone='+372 1111 1111'),
        Client(name='Beta AS', email='beta@test.ee', phone='+372 2222 2222'),
        Client(name='Gamma Ltd', email='gamma@test.ee', phone='+372 3333 3333'),
        Client(name='Delta OÜ', email='delta@test.ee', phone='+372 4444 4444'),
    ]
    
    for client in clients:
        db_session.add(client)
    
    db_session.commit()
    return clients


@pytest.fixture
def invoices_for_filtering(db_session, clients_for_search):
    """Create multiple invoices with different statuses for filtering tests."""
    invoices = [
        Invoice(
            number='2025-0010',
            client_id=clients_for_search[0].id,
            date=date(2025, 8, 1),
            due_date=date(2025, 8, 15),
            status='mustand',
            subtotal=Decimal('100.00'),
            total=Decimal('122.00')
        ),
        Invoice(
            number='2025-0011',
            client_id=clients_for_search[1].id,
            date=date(2025, 8, 5),
            due_date=date(2025, 8, 19),
            status='saadetud',
            subtotal=Decimal('200.00'),
            total=Decimal('244.00')
        ),
        Invoice(
            number='2025-0012',
            client_id=clients_for_search[2].id,
            date=date(2025, 8, 10),
            due_date=date(2025, 8, 24),
            status='makstud',
            subtotal=Decimal('300.00'),
            total=Decimal('366.00')
        ),
        Invoice(
            number='2025-0013',
            client_id=clients_for_search[0].id,
            date=date(2025, 7, 15),
            due_date=date(2025, 7, 29),
            status='tähtaeg ületatud',
            subtotal=Decimal('150.00'),
            total=Decimal('183.00')
        )
    ]
    
    for invoice in invoices:
        db_session.add(invoice)
    
    db_session.commit()
    return invoices


@pytest.fixture
def invoice_number_test_data():
    """Test data for invoice numbering system."""
    return {
        'current_year': 2025,
        'existing_numbers': ['2025-0001', '2025-0002', '2025-0005'],
        'expected_next': '2025-0006',
        'previous_year_numbers': ['2024-0001', '2024-0099']
    }


@pytest.fixture
def vat_calculation_test_cases():
    """Test cases for VAT calculations with Estonian VAT rate."""
    return [
        {
            'subtotal': Decimal('100.00'),
            'vat_rate': Decimal('22.00'),
            'expected_vat': Decimal('22.00'),
            'expected_total': Decimal('122.00')
        },
        {
            'subtotal': Decimal('344.26'),
            'vat_rate': Decimal('22.00'),
            'expected_vat': Decimal('75.74'),  # Rounded
            'expected_total': Decimal('420.00')
        },
        {
            'subtotal': Decimal('50.50'),
            'vat_rate': Decimal('22.00'),
            'expected_vat': Decimal('11.11'),
            'expected_total': Decimal('61.61')
        }
    ]