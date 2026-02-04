import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from models.enums import Currency, TaxStatus


class UserSettingsSchema(BaseModel):
    """Unified settings schema combining User identity and App preferences."""

    # User Identity (Source: User table)
    name: str = Field(..., max_length=200)
    business_name: Optional[str] = Field(None, max_length=200)
    email: str = Field(..., max_length=255)
    siret: Optional[str] = Field(None, max_length=14)
    address: Optional[str] = Field(None, max_length=1000)
    tax_status: TaxStatus = TaxStatus.FRANCHISE
    logo_url: Optional[str] = Field(None, max_length=2000)

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        # Allow relative paths starting with / or valid http(s) URLs
        if v.startswith("/"):
            return v
        if not re.match(r"^https?://", v):
            raise ValueError("L'URL du logo doit commencer par http:// ou https://")
        return v

    # Company Contact (Source: Settings table, fallback to User)
    company_email: Optional[str] = Field(None, max_length=255)
    company_phone: Optional[str] = Field(None, max_length=50)
    company_website: Optional[str] = Field(None, max_length=500)

    # App Preferences (Source: Settings table)
    default_currency: Currency = Currency.EUR
    default_tax_rate: float = 20.0
    pdf_footer_text: Optional[str] = Field(None, max_length=2000)

    # Legal Text Customization
    vat_exemption_text: Optional[str] = Field(None, max_length=2000)
    late_payment_penalties: Optional[str] = Field(None, max_length=2000)
