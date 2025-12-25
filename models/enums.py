from enum import Enum


class Currency(str, Enum):
    """Supported currencies for quotes."""
    EUR = "EUR"


class QuoteStatus(str, Enum):
    """Quote lifecycle statuses."""
    DRAFT = "Draft"
    SENT = "Sent"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    SIGNED = "Signed"


class DiscountType(str, Enum):
    """Discount calculation methods."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class TaxStatus(str, Enum):
    """Fiscal status for VAT calculation."""
    FRANCHISE = "FRANCHISE"  # TVA non applicable (Art. 293 B du CGI)
    ASSUJETTI = "ASSUJETTI"  # TVA applicable (20%)
