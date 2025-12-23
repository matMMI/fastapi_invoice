from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
import uuid
from datetime import datetime

class Settings(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: str = Field(index=True, unique=True)
    
    # Company Details
    company_name: str = Field(default="My Company")
    company_address: Optional[str] = Field(default=None)
    company_email: Optional[str] = Field(default=None)
    company_phone: Optional[str] = Field(default=None)
    company_website: Optional[str] = Field(default=None)
    company_siret: Optional[str] = Field(default=None)
    
    # PDF Customization
    company_logo_url: Optional[str] = Field(default=None)
    pdf_footer_text: Optional[str] = Field(default=None)
    
    # Fiscal Settings
    is_vat_applicable: bool = Field(default=True)
    vat_exemption_text: str = Field(default="TVA non applicable, art. 293 B du CGI")
    late_payment_penalties: str = Field(default="3 fois le taux d'intérêt légal")
    
    # Defaults
    default_currency: str = Field(default="EUR")
    default_tax_rate: float = Field(default=20.0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
