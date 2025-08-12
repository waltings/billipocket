from flask import Blueprint, render_template, request, send_file, abort
from datetime import date
from io import BytesIO
from weasyprint import HTML, CSS
from app.models import Invoice, CompanySettings
from app.logging_config import get_logger

logger = get_logger(__name__)

pdf_bp = Blueprint('pdf', __name__)


@pdf_bp.route('/invoice/<int:id>/pdf')
@pdf_bp.route('/invoice/<int:id>/pdf/<template>')
def invoice_pdf(id, template=None):
    """Generate PDF for invoice with specified template."""
    invoice = Invoice.query.get_or_404(id)
    
    # Get company settings for default template
    company_settings = CompanySettings.get_settings()
    
    # Determine template to use (priority: URL param > query param > settings default)
    if not template:
        # Support both ?template= and ?style= parameters for backwards compatibility
        if 'style' in request.args:
            template = request.args.get('style')
        elif 'template' in request.args:
            template = request.args.get('template')
        else:
            # Use default from settings
            template = company_settings.default_pdf_template or 'standard'
    
    # Validate template
    valid_templates = ['standard', 'modern', 'elegant']
    if template not in valid_templates:
        template = company_settings.default_pdf_template or 'standard'
    
    # Select template file
    template_file = f'pdf/invoice_{template}.html'
    
    try:
        # Render HTML with invoice data and company settings
        html = render_template(
            template_file, 
            invoice=invoice, 
            company=company_settings,
            today=date.today()
        )
        
        # Generate PDF with WeasyPrint
        html_doc = HTML(string=html)
        pdf_bytes = html_doc.write_pdf()
        
        # Create filename
        filename = f"invoice_{invoice.number}_{template}.pdf"
        
        pdf_buffer = BytesIO(pdf_bytes)
        return send_file(
            pdf_buffer, 
            mimetype='application/pdf', 
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"PDF generation error for invoice {id}: {str(e)}", exc_info=True)
        abort(500)


@pdf_bp.route('/invoice/<int:id>/preview')
@pdf_bp.route('/invoice/<int:id>/preview/<template>')
def invoice_preview(id, template=None):
    """Preview invoice HTML before PDF generation."""
    invoice = Invoice.query.get_or_404(id)
    
    # Get company settings for default template
    company_settings = CompanySettings.get_settings()
    
    # Determine template to use
    if not template:
        template = request.args.get('template') or request.args.get('style') or company_settings.default_pdf_template or 'standard'
    
    # Validate template
    valid_templates = ['standard', 'modern', 'elegant']
    if template not in valid_templates:
        template = company_settings.default_pdf_template or 'standard'
    
    # Select template file
    template_file = f'pdf/invoice_{template}.html'
    
    try:
        # Render and return HTML directly with company settings
        return render_template(
            template_file, 
            invoice=invoice, 
            company=company_settings,
            today=date.today()
        )
    except Exception as e:
        logger.error(f"Preview generation error for invoice {id}: {str(e)}", exc_info=True)
        abort(500)


@pdf_bp.route('/invoice/<int:id>/pdf/all')
def invoice_pdf_all_templates(id):
    """Generate PDFs in all templates and return as zip file (future enhancement)."""
    # This could be implemented to generate all three templates
    # and return them as a zip file for comparison
    invoice = Invoice.query.get_or_404(id)
    
    # For now, redirect to standard template
    return invoice_pdf(id, 'standard')