from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from decimal import Decimal

db = SQLAlchemy()


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
        return f'<Client {self.name}>'
    
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
    vat_rate = db.Column(db.Numeric(5, 2), nullable=False, default=24)  # Estonian VAT rate 24%
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
        return f'<Invoice {self.number}>'
    
    @property
    def vat_amount(self):
        """Calculate VAT amount."""
        return self.subtotal * (self.vat_rate / 100)
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
        return self.due_date < date.today() and self.status in ['saadetud']
    
    def calculate_totals(self):
        """Calculate invoice totals from lines."""
        self.subtotal = sum(line.line_total for line in self.lines)
        self.total = self.subtotal + self.vat_amount
    
    def update_status_if_overdue(self):
        """Update status to overdue if due date has passed."""
        if self.is_overdue:
            self.status = 'tähtaeg ületatud'


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
        return f'<InvoiceLine {self.description[:30]}...>'
    
    def calculate_total(self):
        """Calculate line total from quantity and unit price."""
        self.line_total = self.qty * self.unit_price