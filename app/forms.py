from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, DateField, SelectField, FieldList, FormField, HiddenField
from wtforms.validators import DataRequired, Email, Optional, NumberRange, Length
from datetime import date, timedelta


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
    client_id = SelectField('Klient', validators=[DataRequired(message='Klient on kohustuslik')], coerce=int)
    date = DateField('Arve kuupäev', validators=[DataRequired(message='Arve kuupäev on kohustuslik')], default=date.today)
    due_date = DateField('Maksetähtaeg', validators=[DataRequired(message='Maksetähtaeg on kohustuslik')], 
                        default=lambda: date.today() + timedelta(days=14))
    vat_rate = DecimalField('KM määr (%)', validators=[DataRequired(message='KM määr on kohustuslik'), 
                                                      NumberRange(min=0, max=100, message='KM määr peab olema 0-100% vahel')], 
                           default=24)
    status = SelectField('Staatus', choices=[
        ('mustand', 'Mustand'),
        ('saadetud', 'Saadetud'),
        ('makstud', 'Makstud'),
        ('tähtaeg ületatud', 'Tähtaeg ületatud')
    ], default='mustand')
    lines = FieldList(FormField(InvoiceLineForm), min_entries=1)
    
    def __init__(self, *args, **kwargs):
        super(InvoiceForm, self).__init__(*args, **kwargs)
        # Client choices will be populated in the route
        self.client_id.choices = []


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