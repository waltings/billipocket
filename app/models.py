from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from decimal import Decimal

db = SQLAlchemy()


class VatRate(db.Model):
    """VAT rate model for storing different VAT percentages."""
    __tablename__ = 'vat_rates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # e.g., "Standardmäär (24%)"
    rate = db.Column(db.Numeric(5, 2), nullable=False, unique=True)  # e.g., 24.00
    description = db.Column(db.String(255), nullable=True)  # Estonian description
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    invoices = db.relationship('Invoice', backref='vat_rate_obj', lazy=True)
    
    __table_args__ = (
        db.CheckConstraint('rate >= 0 AND rate <= 100', name='check_vat_rate_valid'),
    )
    
    def __repr__(self):
        return f'<VatRate {self.name}: {self.rate}%>'
    
    @classmethod
    def get_active_rates(cls):
        """Get all active VAT rates ordered by rate."""
        return cls.query.filter_by(is_active=True).order_by(cls.rate.asc()).all()
    
    @classmethod
    def get_default_rate(cls):
        """Get the Estonian standard VAT rate (24%)."""
        return cls.query.filter_by(rate=24.00, is_active=True).first()
    
    @classmethod
    def create_default_rates(cls):
        """Create default Estonian VAT rates."""
        default_rates = [
            {'name': 'Maksuvaba (0%)', 'rate': 0.00, 'description': 'Käibemaksuvaba tooted ja teenused'},
            {'name': 'Vähendatud määr (9%)', 'rate': 9.00, 'description': 'Vähendatud käibemaksumäär'},
            {'name': 'Vähendatud määr (20%)', 'rate': 20.00, 'description': 'Vähendatud käibemaksumäär'},
            {'name': 'Standardmäär (24%)', 'rate': 24.00, 'description': 'Eesti standardne käibemaksumäär'}
        ]
        
        for rate_data in default_rates:
            existing_rate = cls.query.filter_by(rate=rate_data['rate']).first()
            if not existing_rate:
                new_rate = cls(
                    name=rate_data['name'],
                    rate=rate_data['rate'],
                    description=rate_data['description']
                )
                db.session.add(new_rate)
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise


class Client(db.Model):
    """Client model for storing customer information."""
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    registry_code = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    invoices = db.relationship('Invoice', backref='client', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Client #{self.id}: "{self.name}" ({self.email or "no email"})>'
    
    @property
    def invoice_count(self):
        """Get total number of invoices for this client."""
        return len(self.invoices)
    
    @property
    def last_invoice_date(self):
        """Get the date of the most recent invoice."""
        if self.invoices:
            return max(invoice.date for invoice in self.invoices)
        return None
    
    @property
    def total_revenue(self):
        """Calculate total revenue from this client."""
        return sum(invoice.total for invoice in self.invoices if invoice.status != 'mustand')


class Invoice(db.Model):
    """Invoice model for storing invoice information."""
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), nullable=False, unique=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    vat_rate_id = db.Column(db.Integer, db.ForeignKey('vat_rates.id'), nullable=True)  # Reference to VatRate
    vat_rate = db.Column(db.Numeric(5, 2), nullable=False, default=24)  # Keep for backward compatibility
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='mustand')  # mustand, saadetud, makstud, tähtaeg ületatud
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    lines = db.relationship('InvoiceLine', backref='invoice', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.CheckConstraint('subtotal >= 0', name='check_subtotal_positive'),
        db.CheckConstraint('total >= 0', name='check_total_positive'),
        db.CheckConstraint('vat_rate >= 0', name='check_vat_rate_positive'),
        db.CheckConstraint("status IN ('mustand', 'saadetud', 'makstud', 'tähtaeg ületatud')", name='check_status_valid'),
    )
    
    def __repr__(self):
        return f'<Invoice {self.number}: {self.client.name if self.client else "No Client"} - €{self.total} ({self.status})>'
    
    @property
    def vat_amount(self):
        """Calculate VAT amount."""
        effective_rate = self.get_effective_vat_rate()
        return self.subtotal * (effective_rate / 100)
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
        return self.due_date < date.today() and self.status in ['saadetud']
    
    @property
    def is_paid(self):
        """Check if invoice is paid."""
        return self.status == 'makstud'
    
    @property
    def can_be_edited(self):
        """Check if invoice can be edited (not paid)."""
        return self.status != 'makstud'
    
    @property
    def can_status_change_to_unpaid(self):
        """Check if status can be changed from paid to unpaid (not allowed)."""
        return self.status != 'makstud'
    
    def get_effective_vat_rate(self):
        """Get the effective VAT rate (from VatRate object or fallback to vat_rate column)."""
        if self.vat_rate_obj:
            return self.vat_rate_obj.rate
        return self.vat_rate
    
    def calculate_totals(self):
        """Calculate invoice totals from lines."""
        self.subtotal = sum(line.line_total for line in self.lines)
        self.total = self.subtotal + self.vat_amount
    
    def update_status_if_overdue(self):
        """Update status to overdue if due date has passed."""
        if self.is_overdue:
            self.status = 'tähtaeg ületatud'
    
    def can_change_status_to(self, new_status):
        """Check if status can be changed to the new status."""
        current_status = self.status
        
        # Paid invoices cannot be changed back to unpaid status
        if current_status == 'makstud' and new_status in ['mustand', 'saadetud', 'tähtaeg ületatud']:
            return False, 'Makstud arveid ei saa tagasi maksmata staatusesse muuta.'
        
        # Valid status transitions
        valid_statuses = ['mustand', 'saadetud', 'makstud', 'tähtaeg ületatud']
        if new_status not in valid_statuses:
            return False, f'Vigane staatus: {new_status}'
        
        # Automatic overdue status should not be manually set to other statuses if still overdue
        if current_status == 'tähtaeg ületatud' and new_status == 'saadetud' and self.is_overdue:
            return False, 'Tähtaja ületanud arvet ei saa saadetud staatusesse muuta, kui tähtaeg on endiselt ületatud.'
        
        return True, None
    
    def set_status(self, new_status):
        """Set invoice status with validation."""
        can_change, error_message = self.can_change_status_to(new_status)
        if not can_change:
            raise ValueError(error_message)
        
        self.status = new_status
        self.updated_at = datetime.utcnow()
    
    @classmethod
    def update_overdue_invoices(cls):
        """Class method to update all overdue invoices."""
        today = date.today()
        overdue_invoices = cls.query.filter(
            cls.due_date < today,
            cls.status == 'saadetud'
        ).all()
        
        count = 0
        for invoice in overdue_invoices:
            invoice.status = 'tähtaeg ületatud'
            invoice.updated_at = datetime.utcnow()
            count += 1
        
        return count


class InvoiceLine(db.Model):
    """Invoice line model for storing individual line items."""
    __tablename__ = 'invoice_lines'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    qty = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)
    
    __table_args__ = (
        db.CheckConstraint('qty > 0', name='check_qty_positive'),
        db.CheckConstraint('unit_price >= 0', name='check_unit_price_non_negative'),
        db.CheckConstraint('line_total >= 0', name='check_line_total_non_negative'),
    )
    
    def __repr__(self):
        return f'<InvoiceLine "{self.description[:50]}..." qty={self.qty} price={self.unit_price} total={self.line_total}>'


class CompanySettings(db.Model):
    """Company settings model for storing business information."""
    __tablename__ = 'company_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(255), nullable=False, default='')
    company_address = db.Column(db.Text, default='')
    company_registry_code = db.Column(db.String(50), default='')
    company_vat_number = db.Column(db.String(50), default='')
    company_phone = db.Column(db.String(50), default='')
    company_email = db.Column(db.String(120), default='')
    company_website = db.Column(db.String(255), default='')
    company_logo_url = db.Column(db.String(500), default='')
    default_vat_rate = db.Column(db.Numeric(5, 2), nullable=False, default=24.00)
    default_pdf_template = db.Column(db.String(20), nullable=False, default='standard')
    invoice_terms = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_settings(cls):
        """Get current company settings (create default if none exist)."""
        settings = cls.query.first()
        if not settings:
            settings = cls(company_name='Minu Ettevõte')
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def __repr__(self):
        return f'<CompanySettings "{self.company_name}">'