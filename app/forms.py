from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, DateField, SelectField, FieldList, FormField, HiddenField
from wtforms.validators import DataRequired, Email, Optional, NumberRange, Length, ValidationError
from datetime import date, timedelta


def validate_unique_invoice_number(form, field):
    """Custom validator to ensure invoice number is unique."""
    from app.models import Invoice
    
    # Get the invoice being edited (if any)
    invoice_id = getattr(form, '_invoice_id', None)
    
    # Check if another invoice already has this number
    existing_invoice = Invoice.query.filter_by(number=field.data).first()
    
    if existing_invoice:
        # If editing an invoice, allow the same number if it belongs to the same invoice
        if invoice_id and existing_invoice.id == invoice_id:
            return  # This is fine - same invoice keeping its number
        else:
            # Another invoice already has this number
            raise ValidationError(f'Arve number "{field.data}" on juba kasutusel.')


def validate_invoice_number_format(form, field):
    """Custom validator to ensure invoice number follows the correct format."""
    import re
    
    if not field.data:
        return
    
    # Expected format: YYYY-NNNN (e.g., 2025-0001)
    if not re.match(r'^\d{4}-\d{4}$', field.data):
        raise ValidationError('Arve number peab olema kujul AAAA-NNNN (näiteks: 2025-0001).')


def validate_status_change(form, field):
    """Custom validator to prevent invalid status changes."""
    from app.models import Invoice
    
    # Get the invoice being edited (if any)
    invoice_id = getattr(form, '_invoice_id', None)
    if not invoice_id:
        return  # New invoice, no restrictions
    
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return  # Invoice not found, let it pass
    
    new_status = field.data
    can_change, error_message = invoice.can_change_status_to(new_status)
    
    if not can_change:
        raise ValidationError(error_message)


class ClientForm(FlaskForm):
    """Form for creating and editing clients."""
    name = StringField('Nimi', validators=[DataRequired(message='Nimi on kohustuslik')])
    registry_code = StringField('Registrikood', validators=[Optional(), Length(max=20)])
    email = StringField('E-post', validators=[Optional(), Email(message='Vigane e-posti aadress')])
    phone = StringField('Telefon', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Aadress', validators=[Optional()])


class InvoiceLineForm(FlaskForm):
    """Form for individual invoice lines."""
    id = HiddenField()
    description = StringField('Kirjeldus', validators=[DataRequired(message='Kirjeldus on kohustuslik')])
    qty = DecimalField('Kogus', validators=[DataRequired(message='Kogus on kohustuslik'), NumberRange(min=0.01, message='Kogus peab olema positiivne')])
    unit_price = DecimalField('Ühiku hind', validators=[DataRequired(message='Ühiku hind on kohustuslik'), NumberRange(min=0, message='Hind ei saa olla negatiivne')])
    line_total = DecimalField('Kokku', validators=[Optional()])


class InvoiceForm(FlaskForm):
    """Form for creating and editing invoices."""
    number = StringField('Arve number', 
                        validators=[
                            DataRequired(message='Arve number on kohustuslik'),
                            validate_invoice_number_format,
                            validate_unique_invoice_number
                        ], 
                        render_kw={"placeholder": "Näiteks: 2025-0001"})
    client_id = SelectField('Klient', validators=[DataRequired(message='Klient on kohustuslik')], coerce=int)
    date = DateField('Arve kuupäev', validators=[DataRequired(message='Arve kuupäev on kohustuslik')], default=date.today)
    due_date = DateField('Maksetähtaeg', validators=[DataRequired(message='Maksetähtaeg on kohustuslik')], 
                        default=lambda: date.today() + timedelta(days=14))
    vat_rate_id = SelectField('KM määr', validators=[DataRequired(message='KM määr on kohustuslik')], coerce=int)
    status = SelectField('Staatus', choices=[
        ('mustand', 'Mustand'),
        ('saadetud', 'Saadetud'),
        ('makstud', 'Makstud'),
        ('tähtaeg ületatud', 'Tähtaeg ületatud')
    ], default='mustand', validators=[validate_status_change])
    lines = FieldList(FormField(InvoiceLineForm), min_entries=1)
    
    def __init__(self, *args, **kwargs):
        super(InvoiceForm, self).__init__(*args, **kwargs)
        # Client choices will be populated in the route
        self.client_id.choices = []
        # VAT rate choices will be populated in the route
        self.vat_rate_id.choices = []


class InvoiceSearchForm(FlaskForm):
    """Form for searching and filtering invoices."""
    status = SelectField('Staatus', choices=[
        ('', 'Kõik'),
        ('mustand', 'Mustand'),
        ('saadetud', 'Saadetud'),
        ('makstud', 'Makstud'),
        ('tähtaeg ületatud', 'Tähtaeg ületatud')
    ], default='')
    client_id = SelectField('Klient', choices=[('', 'Kõik')], coerce=str, default='')
    date_from = DateField('Alates', validators=[Optional()])
    date_to = DateField('Kuni', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super(InvoiceSearchForm, self).__init__(*args, **kwargs)
        # Client choices will be populated in the route
        self.client_id.choices = [('', 'Kõik')]


class ClientSearchForm(FlaskForm):
    """Form for searching clients."""
    search = StringField('Otsing', validators=[Optional()], render_kw={"placeholder": "Otsi klientide seast..."})


class CompanySettingsForm(FlaskForm):
    """Form for company settings."""
    company_name = StringField('Ettevõtte nimi', validators=[DataRequired(message='Ettevõtte nimi on kohustuslik')])
    company_address = TextAreaField('Aadress', validators=[Optional()])
    company_registry_code = StringField('Registrikood', validators=[Optional(), Length(max=50)])
    company_vat_number = StringField('KMKR number', validators=[Optional(), Length(max=50)])
    company_phone = StringField('Telefon', validators=[Optional(), Length(max=50)])
    company_email = StringField('E-post', validators=[Optional(), Email(message='Vigane e-posti aadress')])
    company_website = StringField('Veebileht', validators=[Optional(), Length(max=255)])
    company_logo_url = StringField('Logo URL', validators=[Optional(), Length(max=500)])
    default_vat_rate = DecimalField('Vaikimisi KM määr (%)', 
                                   validators=[DataRequired(message='KM määr on kohustuslik'),
                                             NumberRange(min=0, max=100, message='KM määr peab olema 0-100% vahel')], 
                                   default=24)
    default_pdf_template = SelectField('Vaikimisi PDF mall', 
                                     choices=[
                                         ('standard', 'Standard - klassikaline valge taust'),
                                         ('modern', 'Moodne - värviline gradient'),
                                         ('elegant', 'Elegantne - äripäeva stiilis')
                                     ], 
                                     default='standard',
                                     validators=[DataRequired(message='PDF mall on kohustuslik')])
    invoice_terms = TextAreaField('Arve tingimused', validators=[Optional()])


class VatRateForm(FlaskForm):
    """Form for creating and editing VAT rates."""
    name = StringField('Nimetus', validators=[DataRequired(message='Nimetus on kohustuslik'), Length(max=100)])
    rate = DecimalField('Määr (%)', validators=[
        DataRequired(message='KM määr on kohustuslik'), 
        NumberRange(min=0, max=100, message='KM määr peab olema 0-100% vahel')
    ])
    description = StringField('Kirjeldus', validators=[Optional(), Length(max=255)])
    is_active = SelectField('Staatus', choices=[
        (True, 'Aktiivne'),
        (False, 'Mitteaktiivne')
    ], default=True, coerce=lambda x: x == 'True')
    
    def validate_rate(self, field):
        """Ensure the rate is unique when creating or editing."""
        from app.models import VatRate
        
        # Get the VAT rate being edited (if any)
        vat_rate_id = getattr(self, '_vat_rate_id', None)
        
        # Check if another VAT rate already has this rate
        existing_rate = VatRate.query.filter_by(rate=field.data).first()
        
        if existing_rate:
            # If editing a VAT rate, allow the same rate if it belongs to the same record
            if vat_rate_id and existing_rate.id == vat_rate_id:
                return  # This is fine - same rate keeping its value
            else:
                # Another rate already has this percentage
                raise ValidationError(f'KM määr "{field.data}%" on juba olemas.')
    
    def validate_name(self, field):
        """Ensure the name is unique when creating or editing."""
        from app.models import VatRate
        
        # Get the VAT rate being edited (if any)
        vat_rate_id = getattr(self, '_vat_rate_id', None)
        
        # Check if another VAT rate already has this name
        existing_rate = VatRate.query.filter_by(name=field.data).first()
        
        if existing_rate:
            # If editing a VAT rate, allow the same name if it belongs to the same record
            if vat_rate_id and existing_rate.id == vat_rate_id:
                return  # This is fine - same rate keeping its name
            else:
                # Another rate already has this name
                raise ValidationError(f'Nimetus "{field.data}" on juba kasutusel.')