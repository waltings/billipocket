from flask import Blueprint, render_template, flash, redirect, url_for, request
from app.models import db, Invoice, Client, VatRate
from app.logging_config import get_logger
from sqlalchemy import func, case
from datetime import date, datetime, timedelta
from decimal import Decimal

logger = get_logger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def overview():
    """Overview/dashboard page with metrics from real data."""
    today = date.today()
    current_month_start = date(today.year, today.month, 1)
    
    # Update overdue invoices first
    updated_count = Invoice.update_overdue_invoices()
    if updated_count > 0:
        db.session.commit()
    
    # Calculate metrics
    # 1. Revenue for current month (paid invoices only)
    revenue_month = db.session.query(func.sum(Invoice.total)).filter(
        Invoice.date >= current_month_start,
        Invoice.status.in_(['makstud'])
    ).scalar() or Decimal('0')
    
    # 2. Total cash received (all paid invoices)
    cash_in = db.session.query(func.sum(Invoice.total)).filter(
        Invoice.status == 'makstud'
    ).scalar() or Decimal('0')
    
    # 3. Number of unpaid invoices (sent + overdue)
    unpaid_count = Invoice.query.filter(
        Invoice.status.in_(['saadetud', 'tähtaeg ületatud'])
    ).count()
    
    # 4. Average days to payment (calculated from paid invoices)
    paid_invoices = Invoice.query.filter(Invoice.status == 'makstud').all()
    if paid_invoices:
        total_days = 0
        for invoice in paid_invoices:
            # Assume updated_at is when it was marked as paid
            # For now, use a default of 14 days or calculate from due_date
            days_diff = (invoice.due_date - invoice.date).days
            total_days += max(1, days_diff)  # At least 1 day
        avg_days = total_days // len(paid_invoices)
    else:
        avg_days = 0
    
    # Additional metrics for dashboard
    # Total clients
    total_clients = Client.query.count()
    
    # Total invoices
    total_invoices = Invoice.query.count()
    
    # Outstanding amount (unpaid invoices)
    outstanding = db.session.query(func.sum(Invoice.total)).filter(
        Invoice.status.in_(['saadetud', 'tähtaeg ületatud'])
    ).scalar() or Decimal('0')
    
    # Recent invoices for dashboard display
    recent_invoices = Invoice.query.join(Client).order_by(
        Invoice.date.desc()
    ).limit(5).all()
    
    recent_invoices_data = []
    for invoice in recent_invoices:
        recent_invoices_data.append({
            'no': invoice.number,
            'date': invoice.date.strftime('%Y-%m-%d'),
            'client': invoice.client.name,
            'total': float(invoice.total),
            'status': invoice.status,
            'status_display': {
                'mustand': 'Mustand',
                'saadetud': 'Saadetud',
                'makstud': 'Makstud',
                'tähtaeg ületatud': 'Tähtaeg ületatud'
            }.get(invoice.status, invoice.status)
        })
    
    metrics = {
        "revenue_month": float(revenue_month),
        "cash_in": float(cash_in),
        "unpaid": unpaid_count,
        "avg_days": avg_days,
        "total_clients": total_clients,
        "total_invoices": total_invoices,
        "outstanding": float(outstanding)
    }
    
    return render_template('overview.html', 
                         metrics=metrics, 
                         recent_invoices=recent_invoices_data)


@dashboard_bp.route('/reports')
def reports():
    """Reports page."""
    return render_template('reports.html')


@dashboard_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page."""
    from app.models import CompanySettings
    from app.forms import CompanySettingsForm
    
    # Get current settings
    company_settings = CompanySettings.get_settings()
    
    # Create form with current settings
    form = CompanySettingsForm(obj=company_settings)
    
    if form.validate_on_submit():
        # Update settings from form
        company_settings.company_name = form.company_name.data
        company_settings.company_address = form.company_address.data
        company_settings.company_registry_code = form.company_registry_code.data
        company_settings.company_vat_number = form.company_vat_number.data
        company_settings.company_phone = form.company_phone.data
        company_settings.company_email = form.company_email.data
        company_settings.company_website = form.company_website.data
        company_settings.company_logo_url = form.company_logo_url.data
        company_settings.default_vat_rate = form.default_vat_rate.data
        company_settings.default_pdf_template = form.default_pdf_template.data
        company_settings.invoice_terms = form.invoice_terms.data
        
        try:
            db.session.commit()
            flash('Ettevõtte seaded on edukalt salvestatud.', 'success')
            return redirect(url_for('dashboard.settings'))
        except Exception as e:
            db.session.rollback()
            flash('Seadete salvestamisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    # Get VAT rates for display
    vat_rates = VatRate.get_active_rates()
    
    return render_template('settings.html', form=form, settings=company_settings, vat_rates=vat_rates)


@dashboard_bp.route('/settings/vat-rates')
def vat_rates():
    """VAT rates management page."""
    vat_rates = VatRate.query.order_by(VatRate.rate.asc()).all()
    return render_template('vat_rates.html', vat_rates=vat_rates)


@dashboard_bp.route('/settings/vat-rates/new', methods=['GET', 'POST'])
def new_vat_rate():
    """Create new VAT rate."""
    from app.forms import VatRateForm
    
    form = VatRateForm()
    
    if form.validate_on_submit():
        vat_rate = VatRate(
            name=form.name.data,
            rate=form.rate.data,
            description=form.description.data,
            is_active=form.is_active.data
        )
        
        try:
            db.session.add(vat_rate)
            db.session.commit()
            flash(f'KM määr "{vat_rate.name}" on edukalt loodud.', 'success')
            return redirect(url_for('dashboard.vat_rates'))
        except Exception as e:
            db.session.rollback()
            flash('KM määra loomisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    return render_template('vat_rate_form.html', form=form, title='Uus KM määr')


@dashboard_bp.route('/settings/vat-rates/<int:vat_rate_id>/edit', methods=['GET', 'POST'])
def edit_vat_rate(vat_rate_id):
    """Edit VAT rate."""
    from app.forms import VatRateForm
    
    vat_rate = VatRate.query.get_or_404(vat_rate_id)
    form = VatRateForm(obj=vat_rate)
    
    # Set VAT rate ID for unique validation
    form._vat_rate_id = vat_rate_id
    
    if form.validate_on_submit():
        vat_rate.name = form.name.data
        vat_rate.rate = form.rate.data
        vat_rate.description = form.description.data
        vat_rate.is_active = form.is_active.data
        
        try:
            db.session.commit()
            flash(f'KM määr "{vat_rate.name}" on edukalt uuendatud.', 'success')
            return redirect(url_for('dashboard.vat_rates'))
        except Exception as e:
            db.session.rollback()
            flash('KM määra uuendamisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    return render_template('vat_rate_form.html', form=form, vat_rate=vat_rate, title='Muuda KM määra')


@dashboard_bp.route('/settings/vat-rates/<int:vat_rate_id>/delete', methods=['POST'])
def delete_vat_rate(vat_rate_id):
    """Delete VAT rate."""
    vat_rate = VatRate.query.get_or_404(vat_rate_id)
    
    # Check if VAT rate is used in any invoices
    invoice_count = Invoice.query.filter_by(vat_rate_id=vat_rate_id).count()
    if invoice_count > 0:
        flash(f'KM määra "{vat_rate.name}" ei saa kustutada, kuna see on kasutusel {invoice_count} arvel.', 'warning')
        return redirect(url_for('dashboard.vat_rates'))
    
    try:
        vat_rate_name = vat_rate.name
        db.session.delete(vat_rate)
        db.session.commit()
        flash(f'KM määr "{vat_rate_name}" on edukalt kustutatud.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('KM määra kustutamisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    return redirect(url_for('dashboard.vat_rates'))


@dashboard_bp.route('/settings/vat-rates/init-defaults', methods=['POST'])
def init_default_vat_rates():
    """Initialize default Estonian VAT rates."""
    try:
        VatRate.create_default_rates()
        flash('Vaikimisi KM määrad on edukalt loodud.', 'success')
    except Exception as e:
        flash('Vaikimisi KM määrade loomisel tekkis viga. Palun proovi uuesti.', 'danger')
    
    return redirect(url_for('dashboard.vat_rates'))