from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional
from models.settings import Settings
from models.user import User
from db.session import get_session
from core.security import get_current_user
from datetime import datetime

router = APIRouter()

@router.get("", response_model=Settings)
def get_settings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get settings for the current user. Create default if not exists."""
    statement = select(Settings).where(Settings.user_id == current_user.id)
    settings = session.exec(statement).first()
    
    if not settings:
        # Create default settings
        settings = Settings(
            user_id=current_user.id,
            company_name=current_user.name or "My Company",
            company_email=current_user.email
        )
        session.add(settings)
        session.commit()
        session.refresh(settings)
        
    return settings

@router.put("", response_model=Settings)
def update_settings(
    settings_update: Settings,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update settings for the current user."""
    statement = select(Settings).where(Settings.user_id == current_user.id)
    settings = session.exec(statement).first()
    
    if not settings:
        settings = Settings(user_id=current_user.id)
        session.add(settings)
    
    # Update fields
    settings.company_name = settings_update.company_name
    settings.company_address = settings_update.company_address
    settings.company_email = settings_update.company_email
    settings.company_phone = settings_update.company_phone
    settings.company_website = settings_update.company_website
    settings.company_logo_url = settings_update.company_logo_url
    settings.pdf_footer_text = settings_update.pdf_footer_text
    settings.default_currency = settings_update.default_currency
    settings.default_tax_rate = settings_update.default_tax_rate
    settings.updated_at = datetime.utcnow()
    
    session.add(settings)
    session.commit()
    session.refresh(settings)
    
    return settings
