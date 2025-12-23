"""
Share and sign quotes - public endpoints for electronic signature.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from db.session import get_session
from models.quote import Quote, QuoteItem
from models.client import Client
from models.enums import QuoteStatus
from core.security import get_current_user
from models.user import User


router = APIRouter(tags=["share"])


# ============ Schemas ============

class ShareResponse(BaseModel):
    share_url: str
    expires_at: datetime


class PublicQuoteItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total: float


class PublicQuoteResponse(BaseModel):
    quote_number: str
    client_name: str
    client_email: str
    client_company: str | None
    currency: str
    subtotal: float
    tax_rate: float
    tax_amount: float
    total: float
    notes: str | None
    payment_terms: str | None
    items: list[PublicQuoteItem]
    status: str
    is_signed: bool
    signed_at: datetime | None
    signer_name: str | None
    created_at: datetime


class SignRequest(BaseModel):
    signer_name: str
    signature_data: str  # Base64 PNG


class SignResponse(BaseModel):
    success: bool
    message: str
    signed_at: datetime


# ============ Authenticated Endpoints ============

@router.post("/quotes/{quote_id}/share", response_model=ShareResponse)
async def generate_share_link(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Generate a shareable link for a quote (owner only)."""
    quote = db.exec(
        select(Quote).where(Quote.id == quote_id, Quote.user_id == current_user.id)
    ).first()
    
    if not quote:
        raise HTTPException(status_code=404, detail="Devis non trouvé")
    
    # Generate unique token
    token = str(uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    
    quote.share_token = token
    quote.share_token_expires_at = expires_at
    quote.status = QuoteStatus.SENT
    quote.sent_at = datetime.now(timezone.utc)
    quote.updated_at = datetime.now(timezone.utc)
    
    db.add(quote)
    db.commit()
    db.refresh(quote)
    
    # Build the share URL (frontend will be at /sign/[token])
    share_url = f"/sign/{token}"
    
    return ShareResponse(share_url=share_url, expires_at=expires_at)


# ============ Public Endpoints (No Auth) ============

@router.get("/public/quotes/{token}", response_model=PublicQuoteResponse)
async def get_public_quote(
    token: str,
    db: Session = Depends(get_session)
):
    """Get quote details by share token (public, no auth required)."""
    quote = db.exec(
        select(Quote).where(Quote.share_token == token)
    ).first()
    
    if not quote:
        raise HTTPException(status_code=404, detail="Devis non trouvé ou lien invalide")
    
    # Check expiration
    if quote.share_token_expires_at and quote.share_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Ce lien de partage a expiré")
    
    # Get client info
    client = db.exec(select(Client).where(Client.id == quote.client_id)).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client associé non trouvé")
    
    # Get quote items
    items = db.exec(
        select(QuoteItem).where(QuoteItem.quote_id == quote.id).order_by(QuoteItem.order)
    ).all()
    
    return PublicQuoteResponse(
        quote_number=quote.quote_number,
        client_name=client.name,
        client_email=client.email,
        client_company=client.company,
        currency=quote.currency.value,
        subtotal=float(quote.subtotal),
        tax_rate=float(quote.tax_rate),
        tax_amount=float(quote.tax_amount),
        total=float(quote.total),
        notes=quote.notes,
        payment_terms=quote.payment_terms,
        items=[
            PublicQuoteItem(
                description=item.description,
                quantity=float(item.quantity),
                unit_price=float(item.unit_price),
                total=float(item.total)
            )
            for item in items
        ],
        status=quote.status.value,
        is_signed=quote.signed_at is not None,
        signed_at=quote.signed_at,
        signer_name=quote.signer_name,
        created_at=quote.created_at
    )


@router.post("/public/quotes/{token}/sign", response_model=SignResponse)
async def sign_quote(
    token: str,
    sign_data: SignRequest,
    request: Request,
    db: Session = Depends(get_session)
):
    """Sign a quote electronically (public, no auth required)."""
    quote = db.exec(
        select(Quote).where(Quote.share_token == token)
    ).first()
    
    if not quote:
        raise HTTPException(status_code=404, detail="Devis non trouvé ou lien invalide")
    
    # Check expiration
    if quote.share_token_expires_at and quote.share_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Ce lien de partage a expiré")
    
    # Check if already signed
    if quote.signed_at:
        raise HTTPException(status_code=400, detail="Ce devis a déjà été signé")
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    
    # Save signature
    now = datetime.now(timezone.utc)
    quote.signed_at = now
    quote.signature_data = sign_data.signature_data
    quote.signer_name = sign_data.signer_name
    quote.signer_ip = client_ip
    quote.status = QuoteStatus.SIGNED
    quote.updated_at = now
    
    db.add(quote)
    db.commit()
    db.refresh(quote)
    
    return SignResponse(
        success=True,
        message="Devis signé avec succès",
        signed_at=now
    )
