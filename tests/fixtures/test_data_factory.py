"""
Test data factory for generating comprehensive test data.

This module provides factory functions to create realistic test data
for Estonian invoice management system including:
- Estonian company names and addresses
- Realistic invoice amounts and services
- Valid Estonian registry codes and VAT numbers
- Date ranges and business scenarios
- Multi-language content (Estonian/English)
"""

import random
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
import uuid

from app.models import db, Client, Invoice, InvoiceLine, VatRate, CompanySettings


class EstonianDataFactory:
    """Factory for generating Estonian-specific test data."""
    
    # Estonian company suffixes
    COMPANY_SUFFIXES = ['OÜ', 'AS', 'Ltd', 'UÜ']
    
    # Estonian cities and regions
    ESTONIAN_CITIES = [
        ('Tallinn', '10001'),
        ('Tartu', '51006'),
        ('Narva', '20308'),
        ('Pärnu', '80010'),
        ('Kohtla-Järve', '30322'),
        ('Viljandi', '71020'),
        ('Rakvere', '44307'),
        ('Haapsalu', '90502')
    ]
    
    # Estonian street names (common prefixes)
    STREET_NAMES = [
        'Narva mnt', 'Tartu mnt', 'Liivalaia', 'Viru', 'Rävala pst',
        'Vabaduse väljak', 'Harju', 'Pikk', 'Lai', 'Nunne',
        'Estonia pst', 'Paldiski mnt', 'Kadrioru park'
    ]
    
    # Estonian company name components
    BUSINESS_WORDS = [
        'Arendus', 'Teenused', 'Lahendused', 'Konsultatsioon', 'Projektigrupp',
        'Infosüsteemid', 'Andmetehnoloogia', 'Veebiarendus', 'Disain',
        'Turundus', 'Müük', 'Kaubandus', 'Tootmine', 'Ehitus', 'Remont',
        'Consulting', 'Solutions', 'Development', 'Services', 'Systems',
        'Tech', 'Digital', 'Innovation', 'Strategy', 'Management'
    ]
    
    # Estonian service descriptions
    SERVICE_DESCRIPTIONS = [
        'Veebiarenduse teenused',
        'Süsteemiarenduse nõustamine',
        'Projektijuhtimise teenused',
        'IT-konsultatsiooniteenused',
        'Andmebaaside administreerimine',
        'Serverite hooldus ja seadistamine',
        'Kasutajatoe teenused',
        'Programmeerimiskoolitused',
        'Süsteemi analüüs ja projekteerimine',
        'Turvalisuse auditeerimine',
        'Pilveplatformide migratsioon',
        'Automaatika lahendused',
        'Integratsiooniteenused',
        'Testimine ja kvaliteedikontroll',
        'Äriprotsesside analüüs',
        'Digitaalse transformatsiooni nõustamine',
        'API arendus ja integratsioon',
        'Mobiilirakenduste arendus',
        'E-kaubanduse lahendused',
        'Andmeanalüüsi teenused'
    ]
    
    # Common Estonian first names
    FIRST_NAMES = [
        'Mart', 'Kari', 'Toomas', 'Andres', 'Peeter', 'Jüri', 'Ain', 'Rein',
        'Anne', 'Karin', 'Tiina', 'Mare', 'Ene', 'Piret', 'Kersti', 'Liis'
    ]
    
    # Common Estonian surnames
    SURNAMES = [
        'Tamm', 'Saar', 'Sepp', 'Kask', 'Kukk', 'Rebane', 'Raud', 'Kivi',
        'Mägi', 'Järv', 'Pärn', 'Kuusk', 'Lepp', 'Kõiv', 'Männik', 'Org'
    ]
    
    @classmethod
    def generate_registry_code(cls) -> str:
        """Generate a valid-looking Estonian registry code."""
        return f"{random.randint(10000000, 99999999)}"
    
    @classmethod
    def generate_vat_number(cls) -> str:
        """Generate a valid-looking Estonian VAT number."""
        return f"EE{random.randint(100000000, 999999999)}"
    
    @classmethod
    def generate_phone_number(cls) -> str:
        """Generate an Estonian phone number."""
        number = random.randint(1000000, 9999999)
        return f"+372 {str(number)[:4]} {str(number)[4:]}"
    
    @classmethod
    def generate_email(cls, company_name: str = None) -> str:
        """Generate a realistic Estonian email address."""
        if company_name:
            domain = company_name.lower().replace(' ', '').replace('õü', 'ou').replace('ä', 'a').replace('ö', 'o').replace('ü', 'u')
            domain = ''.join(c for c in domain if c.isalnum())[:10]
        else:
            domain = random.choice(['company', 'business', 'firm', 'group', 'solutions'])
        
        return f"info@{domain}.ee"
    
    @classmethod
    def generate_company_name(cls) -> str:
        """Generate a realistic Estonian company name."""
        business_word = random.choice(cls.BUSINESS_WORDS)
        suffix = random.choice(cls.COMPANY_SUFFIXES)
        
        # 30% chance to add a second word
        if random.random() < 0.3:
            second_word = random.choice(cls.BUSINESS_WORDS)
            while second_word == business_word:
                second_word = random.choice(cls.BUSINESS_WORDS)
            return f"{business_word} {second_word} {suffix}"
        
        return f"{business_word} {suffix}"
    
    @classmethod
    def generate_person_name(cls) -> str:
        """Generate a realistic Estonian person name."""
        first_name = random.choice(cls.FIRST_NAMES)
        surname = random.choice(cls.SURNAMES)
        return f"{first_name} {surname}"
    
    @classmethod
    def generate_address(cls) -> str:
        """Generate a realistic Estonian address."""
        street = random.choice(cls.STREET_NAMES)
        number = random.randint(1, 99)
        city, postal = random.choice(cls.ESTONIAN_CITIES)
        
        # 20% chance to add apartment number
        if random.random() < 0.2:
            apt = random.randint(1, 20)
            return f"{street} {number}-{apt}, {postal} {city}, Estonia"
        
        return f"{street} {number}, {postal} {city}, Estonia"
    
    @classmethod
    def generate_service_description(cls) -> str:
        """Generate a realistic service description."""
        return random.choice(cls.SERVICE_DESCRIPTIONS)
    
    @classmethod
    def generate_service_price(cls) -> Decimal:
        """Generate a realistic service price in euros."""
        # Common price ranges for Estonian IT services
        price_ranges = [
            (25, 50),      # Junior hourly rate
            (50, 80),      # Mid-level hourly rate
            (80, 120),     # Senior hourly rate
            (100, 500),    # Project-based pricing
            (500, 2000),   # Large project pricing
            (2000, 10000)  # Enterprise project pricing
        ]
        
        min_price, max_price = random.choice(price_ranges)
        price = random.uniform(min_price, max_price)
        
        # Round to nice numbers
        if price < 100:
            return Decimal(str(round(price, 2)))
        elif price < 1000:
            return Decimal(str(round(price / 5) * 5))  # Round to nearest 5
        else:
            return Decimal(str(round(price / 50) * 50))  # Round to nearest 50
    
    @classmethod
    def generate_quantity(cls) -> Decimal:
        """Generate a realistic quantity."""
        # Common quantity patterns
        patterns = [
            lambda: Decimal('1.0'),                           # Single item
            lambda: Decimal(str(random.randint(2, 10))),      # Small quantities
            lambda: Decimal(str(random.randint(10, 100))),    # Medium quantities
            lambda: Decimal(f"{random.randint(1, 50)}.5"),    # Half quantities
            lambda: Decimal(f"{random.uniform(0.1, 5.0):.2f}")  # Fractional quantities
        ]
        
        pattern = random.choice(patterns)
        return pattern()


class TestDataFactory:
    """Main factory for creating test data objects."""
    
    def __init__(self, db_session=None):
        """Initialize factory with optional database session."""
        self.db_session = db_session or db.session
        self.estonian_factory = EstonianDataFactory()
    
    def create_client(self, **kwargs) -> Client:
        """Create a client with realistic Estonian data."""
        defaults = {
            'name': self.estonian_factory.generate_company_name(),
            'registry_code': self.estonian_factory.generate_registry_code(),
            'email': None,  # Will be generated based on company name
            'phone': self.estonian_factory.generate_phone_number(),
            'address': self.estonian_factory.generate_address()
        }
        
        # Update with provided kwargs
        defaults.update(kwargs)
        
        # Generate email based on company name if not provided
        if not defaults['email']:
            defaults['email'] = self.estonian_factory.generate_email(defaults['name'])
        
        client = Client(**defaults)
        
        if self.db_session:
            self.db_session.add(client)
            self.db_session.flush()
        
        return client
    
    def create_vat_rate(self, **kwargs) -> VatRate:
        """Create a VAT rate."""
        defaults = {
            'name': f"Test Rate ({kwargs.get('rate', 24)}%)",
            'rate': Decimal('24.00'),
            'description': 'Test VAT rate',
            'is_active': True
        }
        
        defaults.update(kwargs)
        vat_rate = VatRate(**defaults)
        
        if self.db_session:
            self.db_session.add(vat_rate)
            self.db_session.flush()
        
        return vat_rate
    
    def create_invoice(self, client: Client = None, vat_rate: VatRate = None, **kwargs) -> Invoice:
        """Create an invoice with realistic data."""
        if not client:
            client = self.create_client()
        
        if not vat_rate:
            # Try to get existing default rate or create one
            vat_rate = VatRate.get_default_rate()
            if not vat_rate:
                VatRate.create_default_rates()
                vat_rate = VatRate.get_default_rate()
        
        # Generate realistic invoice dates
        invoice_date = kwargs.get('date', date.today() - timedelta(days=random.randint(0, 30)))
        due_date = kwargs.get('due_date', invoice_date + timedelta(days=14))
        
        defaults = {
            'number': self._generate_invoice_number(),
            'client_id': client.id,
            'date': invoice_date,
            'due_date': due_date,
            'vat_rate_id': vat_rate.id if vat_rate else None,
            'vat_rate': vat_rate.rate if vat_rate else Decimal('24.00'),
            'status': random.choice(['mustand', 'saadetud', 'makstud']),
            'subtotal': Decimal('0.00'),
            'total': Decimal('0.00')
        }
        
        defaults.update(kwargs)
        invoice = Invoice(**defaults)
        
        if self.db_session:
            self.db_session.add(invoice)
            self.db_session.flush()
        
        return invoice
    
    def create_invoice_line(self, invoice: Invoice = None, **kwargs) -> InvoiceLine:
        """Create an invoice line with realistic data."""
        if not invoice:
            invoice = self.create_invoice()
        
        quantity = self.estonian_factory.generate_quantity()
        unit_price = self.estonian_factory.generate_service_price()
        line_total = quantity * unit_price
        
        defaults = {
            'invoice_id': invoice.id,
            'description': self.estonian_factory.generate_service_description(),
            'qty': quantity,
            'unit_price': unit_price,
            'line_total': line_total
        }
        
        defaults.update(kwargs)
        invoice_line = InvoiceLine(**defaults)
        
        if self.db_session:
            self.db_session.add(invoice_line)
            self.db_session.flush()
        
        return invoice_line
    
    def create_company_settings(self, **kwargs) -> CompanySettings:
        """Create company settings with Estonian defaults."""
        company_name = self.estonian_factory.generate_company_name()
        
        defaults = {
            'company_name': company_name,
            'company_address': self.estonian_factory.generate_address(),
            'company_registry_code': self.estonian_factory.generate_registry_code(),
            'company_vat_number': self.estonian_factory.generate_vat_number(),
            'company_phone': self.estonian_factory.generate_phone_number(),
            'company_email': self.estonian_factory.generate_email(company_name),
            'company_website': f"https://{company_name.lower().replace(' ', '').replace('õü', 'ou')}.ee",
            'default_vat_rate': Decimal('24.00'),
            'default_pdf_template': random.choice(['standard', 'modern', 'elegant']),
            'invoice_terms': 'Maksetähtaeg 14 päeva. Viivise määr 0,5% päevas.'
        }
        
        defaults.update(kwargs)
        settings = CompanySettings(**defaults)
        
        if self.db_session:
            self.db_session.add(settings)
            self.db_session.flush()
        
        return settings
    
    def create_complete_invoice(self, 
                               client: Client = None, 
                               line_count: int = None,
                               include_vat: bool = True,
                               **kwargs) -> Invoice:
        """Create a complete invoice with client and lines."""
        if not client:
            client = self.create_client()
        
        if line_count is None:
            line_count = random.randint(1, 5)
        
        # Create invoice
        invoice = self.create_invoice(client=client, **kwargs)
        
        # Add lines
        for _ in range(line_count):
            self.create_invoice_line(invoice=invoice)
        
        # Calculate totals if database session is available
        if self.db_session:
            self.db_session.commit()
            invoice.calculate_totals()
            self.db_session.commit()
        
        return invoice
    
    def create_business_scenario(self, scenario_type: str) -> Dict[str, Any]:
        """Create complete business scenario with multiple related objects."""
        scenarios = {
            'small_business': self._create_small_business_scenario,
            'consulting_firm': self._create_consulting_firm_scenario,
            'software_company': self._create_software_company_scenario,
            'overdue_invoices': self._create_overdue_scenario
        }
        
        if scenario_type not in scenarios:
            raise ValueError(f"Unknown scenario type: {scenario_type}")
        
        return scenarios[scenario_type]()
    
    def _generate_invoice_number(self) -> str:
        """Generate a unique invoice number."""
        year = date.today().year
        number = random.randint(1, 9999)
        return f"{year}-{number:04d}"
    
    def _create_small_business_scenario(self) -> Dict[str, Any]:
        """Create a small business scenario."""
        # Company settings
        settings = self.create_company_settings(
            company_name='Väike Ettevõte OÜ',
            company_address='Pikk 15, 10123 Tallinn, Estonia',
            default_pdf_template='standard'
        )
        
        # 3-5 clients
        clients = [self.create_client() for _ in range(random.randint(3, 5))]
        
        # 10-20 invoices
        invoices = []
        for _ in range(random.randint(10, 20)):
            client = random.choice(clients)
            invoice = self.create_complete_invoice(
                client=client,
                line_count=random.randint(1, 3)
            )
            invoices.append(invoice)
        
        return {
            'scenario_type': 'small_business',
            'settings': settings,
            'clients': clients,
            'invoices': invoices
        }
    
    def _create_consulting_firm_scenario(self) -> Dict[str, Any]:
        """Create a consulting firm scenario."""
        settings = self.create_company_settings(
            company_name='Konsultatsiooni Grupp AS',
            company_address='Narva mnt 7, 10117 Tallinn, Estonia',
            default_pdf_template='modern'
        )
        
        # More clients (8-12)
        clients = [self.create_client() for _ in range(random.randint(8, 12))]
        
        # Higher value invoices
        invoices = []
        for _ in range(random.randint(15, 30)):
            client = random.choice(clients)
            # Consulting typically has fewer lines but higher values
            invoice = self.create_complete_invoice(
                client=client,
                line_count=random.randint(1, 2)
            )
            invoices.append(invoice)
        
        return {
            'scenario_type': 'consulting_firm',
            'settings': settings,
            'clients': clients,
            'invoices': invoices
        }
    
    def _create_software_company_scenario(self) -> Dict[str, Any]:
        """Create a software company scenario."""
        settings = self.create_company_settings(
            company_name='Tarkvaraarenduse Lahendused OÜ',
            company_address='Estonia pst 5, 10143 Tallinn, Estonia',
            default_pdf_template='elegant'
        )
        
        # Mix of individual and corporate clients
        clients = [self.create_client() for _ in range(random.randint(6, 10))]
        
        # Projects with multiple phases/lines
        invoices = []
        for _ in range(random.randint(20, 40)):
            client = random.choice(clients)
            invoice = self.create_complete_invoice(
                client=client,
                line_count=random.randint(2, 6)  # More complex projects
            )
            invoices.append(invoice)
        
        return {
            'scenario_type': 'software_company',
            'settings': settings,
            'clients': clients,
            'invoices': invoices
        }
    
    def _create_overdue_scenario(self) -> Dict[str, Any]:
        """Create scenario with overdue invoices for testing."""
        clients = [self.create_client() for _ in range(3)]
        
        invoices = []
        
        # Create overdue invoices
        for _ in range(5):
            client = random.choice(clients)
            overdue_date = date.today() - timedelta(days=random.randint(5, 30))
            invoice = self.create_complete_invoice(
                client=client,
                date=overdue_date - timedelta(days=10),
                due_date=overdue_date,
                status='saadetud'  # Sent but not paid
            )
            invoices.append(invoice)
        
        # Create some current invoices
        for _ in range(3):
            client = random.choice(clients)
            invoice = self.create_complete_invoice(
                client=client,
                status='saadetud'
            )
            invoices.append(invoice)
        
        return {
            'scenario_type': 'overdue_invoices',
            'clients': clients,
            'invoices': invoices,
            'overdue_count': 5
        }


# Convenience functions for common test data patterns
def create_test_client(**kwargs) -> Client:
    """Quick function to create a test client."""
    factory = TestDataFactory()
    return factory.create_client(**kwargs)

def create_test_invoice_with_lines(line_count: int = 3, **kwargs) -> Invoice:
    """Quick function to create an invoice with lines."""
    factory = TestDataFactory()
    return factory.create_complete_invoice(line_count=line_count, **kwargs)

def create_business_test_data(scenario: str = 'small_business') -> Dict[str, Any]:
    """Quick function to create a complete business scenario."""
    factory = TestDataFactory()
    return factory.create_business_scenario(scenario)

def setup_estonian_vat_rates() -> List[VatRate]:
    """Setup Estonian VAT rates for testing."""
    VatRate.create_default_rates()
    return VatRate.get_active_rates()