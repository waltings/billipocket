from flask import Flask, url_for
import os
import click
from datetime import date, timedelta


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
    
    # Global context processor for navigation
    @app.context_processor
    def inject_nav():
        return {
            "nav": {
                "overview": url_for('dashboard.overview'),
                "invoices": url_for('invoices.invoices'),
                "clients": url_for('clients.clients'),
                "reports": url_for('dashboard.reports'),
                "settings": url_for('dashboard.settings'),
            }
        }
    
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
            from app.models import Client, Invoice, InvoiceLine
            
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
                status='saadetud'
            )
            invoice2 = Invoice(
                number='2025-0002',
                client_id=client2.id,
                date=date(2025, 8, 8),
                due_date=date(2025, 8, 22),
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
    
    @app.cli.command()
    @click.argument('username')
    @click.argument('email')
    def create_admin(username, email):
        """Create an admin user (placeholder for future auth system)."""
        click.echo(f'Admin user {username} with email {email} would be created.')
        click.echo('Note: Authentication system not implemented yet.')
    
    return app