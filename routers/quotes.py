"""API routes for quote management."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select, func
from db.session import get_session
from core.security import get_current_user
from models.user import User
from models.quote import Quote, QuoteItem
from models.client import Client
from models.enums import QuoteStatus, TaxStatus
from schemas.quote import QuoteCreate, QuoteUpdate, QuoteResponse, QuoteListResponse
from datetime import datetime, timezone
from decimal import Decimal

router = APIRouter()

def calculate_quote_totals(quote: Quote, items: list[QuoteItem]):
    """Calculate subtotal, tax and total for a quote."""
    subtotal = sum(item.total for item in items)
    
    # Discount logic could be complex, simple version here
    discount_amount = Decimal("0.00")
    if quote.discount_value:
        # TODO: handle Percentage vs Fixed
        discount_amount = quote.discount_value 
        
    taxable_amount = max(subtotal - discount_amount, Decimal("0.00"))
    tax_amount = (taxable_amount * quote.tax_rate) / Decimal("100.00")
    total = taxable_amount + tax_amount
    
    quote.subtotal = subtotal
    quote.tax_amount = tax_amount
    quote.total = total

@router.post("/quotes", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_quote(
    quote_data: QuoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Create a new quote with items."""
    
    # Verify client ownership
    client = db.get(Client, quote_data.client_id)
    if not client or client.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Client not found")

    # Generate quote number if not provided
    quote_number = quote_data.quote_number
    if not quote_number:
        quote_number = f"Q-{int(datetime.now().timestamp() * 1000)}"

    # Determine Tax Rate based on Status
    # If FRANCHISE, force 0. If ASSUJETTI, use provided or default.
    effective_tax_rate = quote_data.tax_rate
    if current_user.tax_status == TaxStatus.FRANCHISE:
        effective_tax_rate = Decimal("0.00")

    # Create Quote
    quote = Quote(
        user_id=current_user.id,
        client_id=quote_data.client_id,
        quote_number=quote_number,
        currency=quote_data.currency,
        tax_rate=effective_tax_rate,
        discount_type=quote_data.discount_type,
        discount_value=quote_data.discount_value,
        notes=quote_data.notes,
        payment_terms=quote_data.payment_terms,
        status=QuoteStatus.DRAFT,
        tax_status=current_user.tax_status # Snapshot
    )
    
    # Create Items and Calculate
    db_items = []
    for item_in in quote_data.items:
        item_total = item_in.quantity * item_in.unit_price
        db_item = QuoteItem(
            description=item_in.description,
            quantity=item_in.quantity,
            unit_price=item_in.unit_price,
            total=item_total,
            order=item_in.order,
            quote=quote 
        )
        db_items.append(db_item)
    
    calculate_quote_totals(quote, db_items)
    
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote

@router.get("/quotes", response_model=QuoteListResponse)
async def list_quotes(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """List all quotes for the current user with pagination."""
    try:
        query = select(Quote).where(Quote.user_id == current_user.id)
        count_query = select(func.count()).select_from(query.subquery())
        total = db.exec(count_query).one()
        
        offset = (page - 1) * limit
        statement = query.order_by(Quote.created_at.desc()).offset(offset).limit(limit)
        quotes = db.exec(statement).all()
        
        return QuoteListResponse(quotes=quotes, total=total)
    except Exception as e:
        print(f"Error listing quotes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quotes/{quote_id}", response_model=QuoteResponse)
async def get_quote(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get a specific quote."""
    quote = db.get(Quote, quote_id)
    if not quote or quote.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote

@router.put("/quotes/{quote_id}", response_model=QuoteResponse)
async def update_quote(
    quote_id: str,
    quote_data: QuoteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Update a quote and its items."""
    quote = db.get(Quote, quote_id)
    if not quote or quote.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Quote not found")

    # Inalterability Check
    if quote.is_paid:
        raise HTTPException(status_code=403, detail="Cannot modify a paid invoice (Inalterability rule).")

    # Update header fields
    if quote_data.client_id: quote.client_id = quote_data.client_id
    if quote_data.quote_number: quote.quote_number = quote_data.quote_number
    if quote_data.currency: quote.currency = quote_data.currency
    if quote_data.status: quote.status = quote_data.status
    
    # Update Payment Status (Allow setting is_paid via update)
    # Note: QuoteUpdate schema needs to support is_paid if we want frontend to set it.
    # Assuming QuoteUpdate has extra=ignore or we added it? 
    # Spec says "Quote Model: Add ... is_paid". Frontend "Bouton pour marquer comme Payé".
    # I should check QuoteUpdate schema. If strict, I need to update it.
    # For now, I'll update it if present in dict form or model.
    if hasattr(quote_data, "is_paid") and quote_data.is_paid is not None:
         quote.is_paid = quote_data.is_paid
         if quote.is_paid and not quote.payment_date:
             quote.payment_date = datetime.now(timezone.utc)
    
    # Enforce Tax Rate Logic on Update too
    if quote_data.tax_rate is not None:
        if quote.tax_status == TaxStatus.FRANCHISE:
            quote.tax_rate = Decimal("0.00")
        else:
            quote.tax_rate = quote_data.tax_rate
    
    # Handle Items
    if quote_data.items is not None:
        existing_items = {item.id: item for item in quote.items}
        new_items_list = []
        
        for item_in in quote_data.items:
            item_total = (item_in.quantity or Decimal(0)) * (item_in.unit_price or Decimal(0))
            
            if item_in.id and item_in.id in existing_items:
                existing_item = existing_items[item_in.id]
                if item_in.description: existing_item.description = item_in.description
                if item_in.quantity: existing_item.quantity = item_in.quantity
                if item_in.unit_price: existing_item.unit_price = item_in.unit_price
                if item_in.order is not None: existing_item.order = item_in.order
                existing_item.total = existing_item.quantity * existing_item.unit_price
                new_items_list.append(existing_item)
                del existing_items[item_in.id]
            else:
                new_item = QuoteItem(
                    quote_id=quote.id,
                    description=item_in.description or "",
                    quantity=item_in.quantity or Decimal(1),
                    unit_price=item_in.unit_price or Decimal(0),
                    total=item_total,
                    order=item_in.order or 0
                )
                db.add(new_item)
                new_items_list.append(new_item)
        
        for old_item in existing_items.values():
            db.delete(old_item)
            
        calculate_quote_totals(quote, new_items_list)
        
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


@router.get("/export/revenue")
async def export_revenue(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Export 'Livre des Recettes' as CSV."""
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    # Query paid quotes
    query = (
        select(Quote)
        .where(Quote.user_id == current_user.id)
        .where(Quote.is_paid == True)
        .order_by(Quote.payment_date.desc())
    )
    quotes = db.exec(query).all()
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Date Encaissement", 
        "Référence", 
        "Client", 
        "Montant HT", 
        "TVA", 
        "Montant TTC", 
        "Mode de Paiement"
    ])
    
    for q in quotes:
        client_name = q.client.name if q.client else "Inconnu"
        payment_date = q.payment_date.strftime("%d/%m/%Y") if q.payment_date else ""
        
        writer.writerow([
            payment_date,
            q.quote_number,
            client_name,
            f"{q.subtotal:.2f}",
            f"{q.tax_amount:.2f}",
            f"{q.total:.2f}",
            "Virement" # Placeholder, could be a field later
        ])
        
    output.seek(0)
    
    filename = f"livre_recettes_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
