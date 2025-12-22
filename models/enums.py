from enum import Enum


class Currency(str, Enum):
    """Supported currencies for quotes."""
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"
    CHF = "CHF"
    CAD = "CAD"


class QuoteStatus(str, Enum):
    """Quote lifecycle statuses."""
    DRAFT = "Draft"
    SENT = "Sent"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"


class DiscountType(str, Enum):
    """Discount calculation methods."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"
