from pydantic import BaseModel
from typing import Optional
from models.enums import TaxStatus, Currency

class UserSettingsSchema(BaseModel):
    """Unified settings schema combining User identity and App preferences."""
    
    # User Identity (Source: User table)
    name: str
    business_name: Optional[str] = None
    email: str
    siret: Optional[str] = None
    address: Optional[str] = None
    tax_status: TaxStatus = TaxStatus.FRANCHISE
    logo_url: Optional[str] = None
    
    # Company Contact (Source: Settings table, fallback to User)
    company_email: Optional[str] = None
    company_phone: Optional[str] = None
    company_website: Optional[str] = None
    
    # App Preferences (Source: Settings table)
    default_currency: Currency = Currency.EUR
    default_tax_rate: float = 20.0
    pdf_footer_text: Optional[str] = None
    
    # Legal Text Customization
    vat_exemption_text: Optional[str] = None
    late_payment_penalties: Optional[str] = None
