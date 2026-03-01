import base64
import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from core.rate_limit import limiter
from core.security import get_current_user
from db.session import get_session
from models.enums import QuoteStatus
from models.quote import Quote
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["share"])


class ShareResponse(BaseModel):
    share_url: str
    expires_at: datetime


class PublicQuoteItem(BaseModel):
    description: str
    detailed_description: str | None = None
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
    deposit_percentage: float | None = None
    deposit_amount: float | None = None
    notes: str | None
    payment_terms: str | None
    items: list[PublicQuoteItem]
    status: str
    is_signed: bool
    signed_at: datetime | None
    signer_name: str | None
    created_at: datetime


class SignRequest(BaseModel):
    signer_name: str = Field(..., min_length=1, max_length=200)
    signer_email: str = Field(..., min_length=1, max_length=255)
    signer_function: str | None = Field(None, max_length=200)
    signature_data: str = Field(..., max_length=500_000)

    @field_validator("signer_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Adresse email invalide")
        return v

    @field_validator("signature_data")
    @classmethod
    def validate_signature_data(cls, v: str) -> str:
        base64_data = v.split(",", 1)[1] if "," in v else v
        try:
            decoded = base64.b64decode(base64_data)
        except Exception:
            raise ValueError("Encodage base64 invalide")
        if len(decoded) > 500_000:
            raise ValueError("Image de signature trop volumineuse (max 500Ko)")
        if not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("La signature doit être une image PNG")
        return v


class SignResponse(BaseModel):
    success: bool
    message: str
    signed_at: datetime


@router.post("/quotes/{quote_id}/share", response_model=ShareResponse)
async def generate_share_link(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Generate a shareable link for a quote (owner only)."""
    quote = db.exec(
        select(Quote).where(Quote.id == quote_id, Quote.user_id == current_user.id)
    ).first()

    if not quote:
        raise HTTPException(status_code=404, detail="Devis non trouvé")

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

    share_url = f"/sign/{token}"

    return ShareResponse(share_url=share_url, expires_at=expires_at)


@router.get("/public/quotes/{token}", response_model=PublicQuoteResponse)
@limiter.limit("10/minute")
async def get_public_quote(request: Request, token: str, db: Session = Depends(get_session)):
    """Get quote details by share token (public, no auth required)."""
    statement = (
        select(Quote)
        .where(Quote.share_token == token)
        .options(selectinload(Quote.client), selectinload(Quote.items))
    )
    quote = db.scalar(statement)

    if not quote:
        raise HTTPException(status_code=404, detail="Devis non trouvé ou lien invalide")
    if not quote.signed_at and quote.share_token_expires_at:
        expires_at = quote.share_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Ce lien de partage a expiré")
    client = quote.client
    if not client:
        raise HTTPException(status_code=404, detail="Client associé non trouvé")
    items = sorted(quote.items, key=lambda x: x.order)

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
        deposit_percentage=float(quote.deposit_percentage) if quote.deposit_percentage else None,
        deposit_amount=float(quote.deposit_amount) if quote.deposit_amount else None,
        notes=quote.notes,
        payment_terms=quote.payment_terms,
        items=[
            PublicQuoteItem(
                description=item.description,
                detailed_description=item.detailed_description,
                quantity=float(item.quantity),
                unit_price=float(item.unit_price),
                total=float(item.total),
            )
            for item in items
        ],
        status=quote.status.value,
        is_signed=quote.signed_at is not None,
        signed_at=quote.signed_at,
        signer_name=quote.signer_name,
        created_at=quote.created_at,
    )


@router.post("/public/quotes/{token}/sign", response_model=SignResponse)
@limiter.limit("3/minute")
async def sign_quote(
    token: str, sign_data: SignRequest, request: Request, db: Session = Depends(get_session)
):
    """Sign a quote electronically (public, no auth required)."""
    quote = db.exec(select(Quote).where(Quote.share_token == token)).first()

    if not quote:
        raise HTTPException(status_code=404, detail="Devis non trouvé ou lien invalide")

    if quote.share_token_expires_at:
        expires_at = quote.share_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Ce lien de partage a expiré")

    if quote.signed_at:
        raise HTTPException(status_code=400, detail="Ce devis a déjà été signé")

    now = datetime.now(timezone.utc)
    quote.signed_at = now
    quote.signature_data = sign_data.signature_data
    quote.signer_name = sign_data.signer_name
    quote.signer_email = sign_data.signer_email
    quote.signer_function = sign_data.signer_function
    quote.status = QuoteStatus.SIGNED
    quote.updated_at = now

    db.add(quote)
    db.commit()
    db.refresh(quote)

    return SignResponse(success=True, message="Devis signé avec succès", signed_at=now)


@router.get("/public/quotes/{token}/pdf")
@limiter.limit("5/minute")
async def get_public_quote_pdf(request: Request, token: str, db: Session = Depends(get_session)):
    """Download quote PDF (public, no auth required)."""
    from fastapi.responses import Response

    from models.settings import Settings
    from services.pdf_generator import generate_quote_pdf

    statement = (
        select(Quote)
        .where(Quote.share_token == token)
        .options(selectinload(Quote.client), selectinload(Quote.items))
    )
    quote = db.exec(statement).first()

    if not quote:
        raise HTTPException(status_code=404, detail="Devis non trouvé ou lien invalide")

    if not quote.signed_at and quote.share_token_expires_at:
        expires_at = quote.share_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Ce lien de partage a expiré")

    settings = db.exec(select(Settings).where(Settings.user_id == quote.user_id)).first()
    if not settings:
        settings = Settings(
            user_id=quote.user_id,
            company_name="My Company",
            default_currency="EUR",
            default_tax_rate=20.0,
        )

    user = db.get(User, quote.user_id)
    if not user:
        raise HTTPException(status_code=500, detail="Utilisateur non trouvé")

    try:
        pdf_bytes = generate_quote_pdf(quote, settings, user)
    except Exception as e:
        logger.error(f"PDF generation failed for quote {quote.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de la génération du PDF")

    safe_number = re.sub(r"[^\w\s\-.]", "", quote.quote_number).strip()
    filename = f"Devis_{safe_number}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
