"""API routes for PDF generation."""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from io import BytesIO
from db.session import get_session
from core.security import get_current_user
from models.user import User
from models.quote import Quote
from models.settings import Settings
from services.pdf_generator import generate_quote_pdf
router = APIRouter()
def get_user_settings(session: Session, user_id: str) -> Settings:
    statement = select(Settings).where(Settings.user_id == user_id)
    settings = session.exec(statement).first()
    if not settings:
        settings = Settings(user_id=user_id, company_name="My Company", default_currency="EUR", default_tax_rate=20.0)
    return settings


@router.post("/quotes/{quote_id}/generate-pdf")
async def generate_pdf(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Generate a PDF for a quote.
    
    Returns the PDF as a downloadable file.
    """
    statement = select(Quote).where(Quote.id == quote_id).options(
        selectinload(Quote.client),
        selectinload(Quote.items)
    )
    quote = db.exec(statement).first()
    
    if not quote or quote.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    try:
        settings = get_user_settings(db, current_user.id)
        pdf_bytes = generate_quote_pdf(quote, settings, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
    
    filename = f"{quote.quote_number}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/quotes/{quote_id}/pdf")
async def get_pdf(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    statement = select(Quote).where(Quote.id == quote_id).options(
        selectinload(Quote.client),
        selectinload(Quote.items)
    )
    quote = db.exec(statement).first()
    
    if not quote or quote.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    try:
        settings = get_user_settings(db, current_user.id)
        pdf_bytes = generate_quote_pdf(quote, settings, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
    
    filename = f"{quote.quote_number}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={filename}"
        }
    )
