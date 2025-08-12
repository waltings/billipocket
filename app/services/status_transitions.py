from datetime import date
from app.models import db, Invoice


class InvoiceStatusTransition:
    """Service class for managing invoice status transitions."""
    
    # Valid statuses
    DRAFT = 'mustand'
    SENT = 'saadetud'
    PAID = 'makstud'
    OVERDUE = 'tähtaeg ületatud'
    
    VALID_STATUSES = [DRAFT, SENT, PAID, OVERDUE]
    
    # Status messages in Estonian
    STATUS_MESSAGES = {
        DRAFT: 'Arve on muudetud mustandiks.',
        SENT: 'Arve on märgitud saadetud.',
        PAID: 'Arve on märgitud makstud.',
        OVERDUE: 'Arve on märgitud tähtaja ületanud.'
    }
    
    @classmethod
    def can_transition_to(cls, current_status, new_status):
        """
        Check if status transition is allowed.
        
        Args:
            current_status: Current invoice status
            new_status: Desired new status
            
        Returns:
            tuple: (can_change: bool, error_message: str|None)
        """
        # Validate new status
        if new_status not in cls.VALID_STATUSES:
            return False, f'Vigane staatus: {new_status}'
        
        # Same status - no change needed
        if current_status == new_status:
            return True, None
        
        # Paid invoices cannot be changed back to unpaid status
        if current_status == cls.PAID and new_status in [cls.DRAFT, cls.SENT, cls.OVERDUE]:
            return False, 'Makstud arveid ei saa tagasi maksmata staatusesse muuta.'
        
        return True, None
    
    @classmethod
    def can_transition_overdue_to_sent(cls, invoice, new_status):
        """
        Special check for overdue to sent transition.
        
        Args:
            invoice: Invoice object
            new_status: Desired new status
            
        Returns:
            tuple: (can_change: bool, error_message: str|None)
        """
        if (invoice.status == cls.OVERDUE and 
            new_status == cls.SENT and 
            invoice.is_overdue):
            return False, 'Tähtaja ületanud arvet ei saa saadetud staatusesse muuta, kui tähtaeg on endiselt ületatud.'
        
        return True, None
    
    @classmethod
    def transition_invoice_status(cls, invoice, new_status):
        """
        Transition invoice to new status with validation.
        
        Args:
            invoice: Invoice object
            new_status: New status to set
            
        Returns:
            tuple: (success: bool, message: str)
        """
        # Check basic transition rules
        can_change, error_msg = cls.can_transition_to(invoice.status, new_status)
        if not can_change:
            return False, error_msg
        
        # Check overdue specific rules
        can_change_overdue, overdue_error = cls.can_transition_overdue_to_sent(invoice, new_status)
        if not can_change_overdue:
            return False, overdue_error
        
        try:
            # Set new status
            invoice.set_status(new_status)
            
            # Get success message
            success_msg = cls.STATUS_MESSAGES.get(new_status, 'Staatust on muudetud.')
            
            return True, success_msg
            
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, 'Staatuse muutmisel tekkis viga. Palun proovi uuesti.'
    
    @classmethod
    def update_overdue_invoices(cls):
        """
        Update all eligible invoices to overdue status.
        
        Returns:
            int: Number of invoices updated
        """
        return Invoice.update_overdue_invoices()
    
    @classmethod
    def get_valid_transitions(cls, current_status):
        """
        Get list of valid status transitions from current status.
        
        Args:
            current_status: Current invoice status
            
        Returns:
            list: List of valid status transitions
        """
        if current_status == cls.PAID:
            # Paid invoices cannot be changed to unpaid statuses
            return [cls.PAID]
        
        return cls.VALID_STATUSES
    
    @classmethod
    def get_status_display_name(cls, status):
        """
        Get human-readable display name for status.
        
        Args:
            status: Status code
            
        Returns:
            str: Display name
        """
        display_names = {
            cls.DRAFT: 'Mustand',
            cls.SENT: 'Saadetud',
            cls.PAID: 'Makstud',
            cls.OVERDUE: 'Tähtaeg ületatud'
        }
        return display_names.get(status, status)
    
    @classmethod
    def get_status_css_class(cls, status):
        """
        Get CSS class for status styling.
        
        Args:
            status: Status code
            
        Returns:
            str: CSS class name
        """
        css_classes = {
            cls.DRAFT: 'badge-secondary',
            cls.SENT: 'badge-primary', 
            cls.PAID: 'badge-success',
            cls.OVERDUE: 'badge-danger'
        }
        return css_classes.get(status, 'badge-light')