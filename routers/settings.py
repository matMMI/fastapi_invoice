from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional
from models.settings import Settings
from models.user import User
from db.session import get_session
from core.security import get_current_user
from datetime import datetime

router = APIRouter()

from schemas.settings import UserSettingsSchema
from models.enums import TaxStatus, Currency

@router.get("", response_model=UserSettingsSchema)
def get_settings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get unified settings (User identity + App preferences)."""
    statement = select(Settings).where(Settings.user_id == current_user.id)
    settings = session.exec(statement).first()
    
    if not settings:
        settings = Settings(
            user_id=current_user.id,
            company_name=current_user.name or "My Company",
            company_email=current_user.email
        )
        session.add(settings)
        session.commit()
        session.refresh(settings)
        
    return UserSettingsSchema(
        # User Identity
        name=current_user.name,
        business_name=current_user.business_name,
        email=current_user.email,
        siret=current_user.siret,
        address=current_user.address,
        tax_status=current_user.tax_status,
        logo_url=current_user.logo_url,
        
        # Settings
        company_email=settings.company_email,
        company_phone=settings.company_phone,
        company_website=settings.company_website,
        default_currency=Currency(settings.default_currency) if settings.default_currency else Currency.EUR,
        default_tax_rate=settings.default_tax_rate,
        pdf_footer_text=settings.pdf_footer_text,
        vat_exemption_text=settings.vat_exemption_text,
        late_payment_penalties=settings.late_payment_penalties
    )

@router.put("", response_model=UserSettingsSchema)
def update_settings(
    payload: UserSettingsSchema,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update User identity and App settings."""
    # 1. Update User Identity
    current_user.name = payload.name
    current_user.business_name = payload.business_name
    current_user.siret = payload.siret
    current_user.address = payload.address
    current_user.tax_status = payload.tax_status
    if payload.logo_url:
        current_user.logo_url = payload.logo_url
        
    session.add(current_user)
    
    # 2. Update Settings
    statement = select(Settings).where(Settings.user_id == current_user.id)
    settings = session.exec(statement).first()
    
    if not settings:
        settings = Settings(user_id=current_user.id)
    
    settings.company_name = payload.business_name or payload.name # Sync
    settings.company_email = payload.company_email
    settings.company_phone = payload.company_phone
    settings.company_website = payload.company_website
    settings.company_logo_url = payload.logo_url # Sync
    settings.default_currency = payload.default_currency.value
    settings.default_tax_rate = payload.default_tax_rate
    settings.pdf_footer_text = payload.pdf_footer_text
    
    if payload.vat_exemption_text:
        settings.vat_exemption_text = payload.vat_exemption_text
    if payload.late_payment_penalties:
        settings.late_payment_penalties = payload.late_payment_penalties
        
    settings.updated_at = datetime.utcnow()
    
    session.add(settings)
    session.commit()
    session.refresh(current_user)
    session.refresh(settings)
    
    return payload

@router.delete("/reset", status_code=204)
def reset_account_data(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    DANGER: Delete all data for the current user (Quotes, Items, Clients).
    Does NOT delete the User account or global Settings.
    """
    from models.quote import Quote, QuoteItem
    from models.client import Client
    
    # 1. Delete all Quotes (and cascade Items)
    statement_quotes = select(Quote).where(Quote.user_id == current_user.id)
    quotes = session.exec(statement_quotes).all()
    for quote in quotes:
        session.delete(quote)
        
    # 2. Delete all Clients
    statement_clients = select(Client).where(Client.user_id == current_user.id)
    clients = session.exec(statement_clients).all()
    for client in clients:
        session.delete(client)
        
    session.commit()
    return None
