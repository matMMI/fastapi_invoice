"""API routes for PDF generation."""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from io import BytesIO

from db.session import get_session
from core.security import get_current_user
from models.user import User
from models.quote import Quote
from services.pdf_generator import generate_quote_pdf

router = APIRouter()


@router.post("/quotes/{quote_id}/generate-pdf")
async def generate_pdf(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Generate a PDF for a quote.
    
    Returns the PDF as a downloadable file.
    For now, we return the PDF directly. 
    In the future, we can upload to Vercel Blob and return a URL.
    """
    # Fetch quote
    quote = db.get(Quote, quote_id)
    if not quote or quote.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    # Generate PDF
    try:
        pdf_bytes = generate_quote_pdf(quote)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
    
    # Return as downloadable PDF
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
    """
    Get the PDF for a quote (generates it on the fly).
    
    This endpoint returns the PDF inline for preview.
    """
    quote = db.get(Quote, quote_id)
    if not quote or quote.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    try:
        pdf_bytes = generate_quote_pdf(quote)
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
