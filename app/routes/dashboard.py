from flask import Blueprint, render_template
from app.models import db, Invoice, Client
from sqlalchemy import func, case
from datetime import date, datetime, timedelta
from decimal import Decimal

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def overview():
    """Overview/dashboard page with metrics from real data."""
    today = date.today()
    current_month_start = date(today.year, today.month, 1)
    
    # Update overdue invoices first
    overdue_invoices = Invoice.query.filter(
        Invoice.due_date < today,
        Invoice.status == 'saadetud'
    ).all()
    
    for invoice in overdue_invoices:
        invoice.status = 'tähtaeg ületatud'
    
    if overdue_invoices:
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


@dashboard_bp.route('/settings')
def settings():
    """Settings page."""
    return render_template('settings.html')