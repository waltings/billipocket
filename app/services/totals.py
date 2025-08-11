from decimal import Decimal, ROUND_HALF_UP


def calculate_line_total(qty, unit_price):
    """
    Calculate total for an invoice line.
    
    Args:
        qty: Quantity (Decimal or float)
        unit_price: Unit price (Decimal or float)
    
    Returns:
        Decimal: Line total rounded to 2 decimal places
    """
    if qty is None or unit_price is None:
        return Decimal('0.00')
    
    qty = Decimal(str(qty))
    unit_price = Decimal(str(unit_price))
    
    total = qty * unit_price
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_subtotal(lines):
    """
    Calculate subtotal from invoice lines.
    
    Args:
        lines: List of invoice lines (each should have line_total attribute)
    
    Returns:
        Decimal: Subtotal rounded to 2 decimal places
    """
    subtotal = Decimal('0.00')
    for line in lines:
        if hasattr(line, 'line_total') and line.line_total:
            subtotal += Decimal(str(line.line_total))
    
    return subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_vat_amount(subtotal, vat_rate):
    """
    Calculate VAT amount.
    
    Args:
        subtotal: Subtotal amount (Decimal or float)
        vat_rate: VAT rate as percentage (Decimal or float)
    
    Returns:
        Decimal: VAT amount rounded to 2 decimal places
    """
    if subtotal is None or vat_rate is None:
        return Decimal('0.00')
    
    subtotal = Decimal(str(subtotal))
    vat_rate = Decimal(str(vat_rate))
    
    vat_amount = subtotal * (vat_rate / Decimal('100'))
    return vat_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_total(subtotal, vat_amount):
    """
    Calculate total amount (subtotal + VAT).
    
    Args:
        subtotal: Subtotal amount (Decimal or float)
        vat_amount: VAT amount (Decimal or float)
    
    Returns:
        Decimal: Total amount rounded to 2 decimal places
    """
    if subtotal is None:
        subtotal = Decimal('0.00')
    if vat_amount is None:
        vat_amount = Decimal('0.00')
    
    subtotal = Decimal(str(subtotal))
    vat_amount = Decimal(str(vat_amount))
    
    total = subtotal + vat_amount
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_invoice_totals(invoice):
    """
    Calculate all totals for an invoice and update the invoice object.
    
    Args:
        invoice: Invoice object with lines relationship loaded
    
    Returns:
        dict: Dictionary with subtotal, vat_amount, and total
    """
    # Calculate subtotal from lines
    subtotal = calculate_subtotal(invoice.lines)
    
    # Calculate VAT amount
    vat_amount = calculate_vat_amount(subtotal, invoice.vat_rate)
    
    # Calculate total
    total = calculate_total(subtotal, vat_amount)
    
    # Update invoice
    invoice.subtotal = subtotal
    invoice.total = total
    
    return {
        'subtotal': subtotal,
        'vat_amount': vat_amount,
        'total': total
    }