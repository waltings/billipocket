from flask import Flask, url_for, render_template
import os
import click
from datetime import date, timedelta
from app.logging_config import setup_logging


def create_app(config_name=None):
    """Application factory pattern."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    # Get the base directory (project root)
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    app = Flask(__name__, 
                template_folder=os.path.join(basedir, 'templates'),
                static_folder=os.path.join(basedir, 'static'))
    
    # Load configuration
    from app.config import config
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    from app.models import db
    from flask_wtf.csrf import CSRFProtect, generate_csrf
    
    db.init_app(app)
    csrf = CSRFProtect(app)
    
    # Setup logging
    setup_logging(app)
    
    # Security headers
    @app.after_request
    def set_security_headers(response):
        if not app.config.get('DEBUG'):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
        return response
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500
    
    @app.errorhandler(400)
    def csrf_error(error):
        from flask_wtf.csrf import CSRFError
        if isinstance(error, CSRFError):
            return render_template('400.html', 
                                 error_message='CSRF token on puudu või vigane. Palun proovi uuesti.'), 400
        return render_template('400.html'), 400
    
    # Global context processor for navigation
    @app.context_processor
    def inject_nav():
        try:
            return {
                "nav": {
                    "overview": url_for('dashboard.overview'),
                    "invoices": url_for('invoices.invoices'),
                    "clients": url_for('clients.clients'),
                    "reports": url_for('dashboard.reports'),
                    "settings": url_for('dashboard.settings'),
                }
            }
        except RuntimeError:
            # Return empty nav when outside request context (e.g., PDF generation)
            return {"nav": {}}
    
    # Make CSRF token available in templates
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf)
    
    # Register blueprints
    from app.routes.dashboard import dashboard_bp
    from app.routes.clients import clients_bp
    from app.routes.invoices import invoices_bp
    from app.routes.pdf import pdf_bp
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(pdf_bp)
    
    # CLI commands
    @app.cli.command()
    def init_db():
        """Initialize the database."""
        with app.app_context():
            db.create_all()
            click.echo('Database tables created successfully.')
    
    @app.cli.command()
    def seed_data():
        """Seed the database with sample data."""
        with app.app_context():
            from app.models import Client, Invoice, InvoiceLine, VatRate
            
            # First ensure VAT rates exist
            VatRate.create_default_rates()
            standard_vat = VatRate.get_default_rate()
            
            # Create sample clients
            client1 = Client(
                name='Nordics OÜ',
                registry_code='12345678',
                email='info@nordics.ee',
                phone='+372 5555 1234',
                address='Tallinn, Estonia'
            )
            client2 = Client(
                name='Viridian AS',
                registry_code='87654321',
                email='contact@viridian.ee',
                phone='+372 5555 5678',
                address='Tartu, Estonia'
            )
            
            db.session.add(client1)
            db.session.add(client2)
            db.session.flush()  # Get IDs
            
            # Create sample invoices
            invoice1 = Invoice(
                number='2025-0001',
                client_id=client1.id,
                date=date(2025, 8, 10),
                due_date=date(2025, 8, 24),
                vat_rate_id=standard_vat.id if standard_vat else None,
                vat_rate=standard_vat.rate if standard_vat else 24,
                status='saadetud'
            )
            invoice2 = Invoice(
                number='2025-0002',
                client_id=client2.id,
                date=date(2025, 8, 8),
                due_date=date(2025, 8, 22),
                vat_rate_id=standard_vat.id if standard_vat else None,
                vat_rate=standard_vat.rate if standard_vat else 24,
                status='makstud'
            )
            
            db.session.add(invoice1)
            db.session.add(invoice2)
            db.session.flush()
            
            # Create sample invoice lines
            line1 = InvoiceLine(
                invoice_id=invoice1.id,
                description='Web development services',
                qty=1,
                unit_price=344.26,
                line_total=344.26
            )
            line2 = InvoiceLine(
                invoice_id=invoice2.id,
                description='Consulting services',
                qty=8,
                unit_price=131.15,
                line_total=1049.20
            )
            
            db.session.add(line1)
            db.session.add(line2)
            
            # Calculate totals
            invoice1.calculate_totals()
            invoice2.calculate_totals()
            
            db.session.commit()
            click.echo('Sample data created successfully.')
            click.echo(f'Created invoices with VAT rate: {standard_vat.name if standard_vat else "24% (fallback)"}')
    
    @app.cli.command()
    @click.argument('username')
    @click.argument('email')
    def create_admin(username, email):
        """Create an admin user (placeholder for future auth system)."""
        click.echo(f'Admin user {username} with email {email} would be created.')
        click.echo('Note: Authentication system not implemented yet.')
    
    @app.cli.command()
    def init_vat_rates():
        """Initialize default Estonian VAT rates."""
        with app.app_context():
            from app.models import VatRate
            
            try:
                VatRate.create_default_rates()
                click.echo('Default Estonian VAT rates created successfully:')
                
                # Display created rates
                rates = VatRate.get_active_rates()
                for rate in rates:
                    click.echo(f'  • {rate.name}: {rate.rate}% - {rate.description}')
                
            except Exception as e:
                click.echo(f'Error creating VAT rates: {str(e)}')
                return
    
    @app.cli.command()
    def update_overdue():
        """Update overdue invoice statuses."""
        with app.app_context():
            from app.models import Invoice
            
            try:
                updated_count = Invoice.update_overdue_invoices()
                if updated_count > 0:
                    db.session.commit()
                    click.echo(f'Updated {updated_count} invoices to overdue status.')
                else:
                    click.echo('No invoices found that need overdue status update.')
                    
            except Exception as e:
                db.session.rollback()
                click.echo(f'Error updating overdue invoices: {str(e)}')
    
    return app