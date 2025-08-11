from datetime import date
from app.models import db, Invoice


def generate_invoice_number(year=None):
    """
    Generate next invoice number for the given year in format YYYY-####.
    
    Args:
        year: Year for the invoice number. If None, uses current year.
    
    Returns:
        str: Next invoice number in format YYYY-####
    """
    if year is None:
        year = date.today().year
    
    # Find the highest invoice number for this year
    year_prefix = f"{year}-"
    last_invoice = (Invoice.query
                   .filter(Invoice.number.like(f"{year_prefix}%"))
                   .order_by(Invoice.number.desc())
                   .first())
    
    if last_invoice:
        # Extract the number part and increment
        number_part = last_invoice.number.split('-')[1]
        next_number = int(number_part) + 1
    else:
        # First invoice of the year
        next_number = 1
    
    return f"{year}-{next_number:04d}"


def is_invoice_number_available(number):
    """
    Check if an invoice number is available.
    
    Args:
        number: Invoice number to check
    
    Returns:
        bool: True if available, False if taken
    """
    existing = Invoice.query.filter_by(number=number).first()
    return existing is None


def validate_invoice_number_format(number):
    """
    Validate that invoice number follows the YYYY-#### format.
    
    Args:
        number: Invoice number to validate
    
    Returns:
        bool: True if format is valid, False otherwise
    """
    if not number or not isinstance(number, str):
        return False
    
    parts = number.split('-')
    if len(parts) != 2:
        return False
    
    year_part, number_part = parts
    
    # Validate year part (4 digits)
    if not year_part.isdigit() or len(year_part) != 4:
        return False
    
    # Validate number part (4 digits)
    if not number_part.isdigit() or len(number_part) != 4:
        return False
    
    return True