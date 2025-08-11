from flask import Blueprint, render_template, request, send_file, abort
from datetime import date
from io import BytesIO
from weasyprint import HTML, CSS
from app.models import Invoice

pdf_bp = Blueprint('pdf', __name__)


@pdf_bp.route('/invoice/<int:invoice_id>/pdf')
@pdf_bp.route('/invoice/<int:invoice_id>/pdf/<template>')
def invoice_pdf(invoice_id, template='standard'):
    """Generate PDF for invoice with specified template."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Support both ?template= and ?style= parameters for backwards compatibility
    if 'style' in request.args:
        template = request.args.get('style', 'standard')
    elif 'template' in request.args:
        template = request.args.get('template', 'standard')
    
    # Validate template
    valid_templates = ['standard', 'modern', 'elegant']
    if template not in valid_templates:
        template = 'standard'
    
    # Select template file
    template_file = f'pdf/invoice_{template}.html'
    
    try:
        # Render HTML with invoice data
        html = render_template(
            template_file, 
            invoice=invoice, 
            today=date.today()
        )
        
        # Generate PDF with WeasyPrint
        pdf_bytes = HTML(
            string=html, 
            base_url=request.base_url
        ).write_pdf()
        
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
        # Log error in production
        print(f"PDF generation error: {e}")
        abort(500)


@pdf_bp.route('/invoice/<int:invoice_id>/preview')
@pdf_bp.route('/invoice/<int:invoice_id>/preview/<template>')
def invoice_preview(invoice_id, template='standard'):
    """Preview invoice HTML before PDF generation."""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Validate template
    valid_templates = ['standard', 'modern', 'elegant']
    if template not in valid_templates:
        template = 'standard'
    
    # Select template file
    template_file = f'pdf/invoice_{template}.html'
    
    try:
        # Render and return HTML directly
        return render_template(
            template_file, 
            invoice=invoice, 
            today=date.today()
        )
    except Exception as e:
        # Log error in production
        print(f"Preview generation error: {e}")
        abort(500)


@pdf_bp.route('/invoice/<int:invoice_id>/pdf/all')
def invoice_pdf_all_templates(invoice_id):
    """Generate PDFs in all templates and return as zip file (future enhancement)."""
    # This could be implemented to generate all three templates
    # and return them as a zip file for comparison
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # For now, redirect to standard template
    return invoice_pdf(invoice_id, 'standard')