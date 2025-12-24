"""Pydantic schemas for Quote API endpoints."""

from pydantic import BaseModel, Field, validator
from datetime import datetime
from decimal import Decimal
from models.enums import Currency, QuoteStatus, DiscountType

class QuoteItemCreate(BaseModel):
    """Schema for creating a quote item."""
    description: str = Field(..., min_length=1)
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    order: int = Field(default=0)

class QuoteItemUpdate(BaseModel):
    """Schema for updating a quote item."""
    id: str | None = None
    description: str | None = Field(None, min_length=1)
    quantity: Decimal | None = Field(None, gt=0)
    unit_price: Decimal | None = Field(None, ge=0)
    order: int | None = None

class QuoteItemResponse(BaseModel):
    """Schema for quote item response."""
    id: str
    quote_id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    total: Decimal
    order: int

    model_config = {"from_attributes": True}

class QuoteCreate(BaseModel):
    """Schema for creating a new quote."""
    client_id: str
    quote_number: str | None = None
    currency: Currency = Currency.EUR
    tax_rate: Decimal = Field(default=Decimal("20.00"), ge=0)
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = None
    
    notes: str | None = None
    payment_terms: str | None = None
    
    items: list[QuoteItemCreate]

class QuoteUpdate(BaseModel):
    """Schema for updating a quote."""
    client_id: str | None = None
    quote_number: str | None = None
    currency: Currency | None = None
    status: QuoteStatus | None = None
    tax_rate: Decimal | None = Field(None, ge=0)
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = None
    
    notes: str | None = None
    payment_terms: str | None = None
    
    is_paid: bool | None = None  # Allow updating payment status
    
    items: list[QuoteItemUpdate] | None = None

class QuoteResponse(BaseModel):
    """Schema for full quote response."""
    id: str
    quote_number: str
    user_id: str
    client_id: str
    status: QuoteStatus
    currency: Currency
    
    # Financials
    subtotal: Decimal
    discount_type: DiscountType | None
    discount_value: Decimal | None
    tax_rate: Decimal
    tax_amount: Decimal
    total: Decimal
    
    # Fiscal & Payment
    tax_status: str | None = None # Enum as str
    is_paid: bool
    payment_date: datetime | None
    
    # Metadata
    pdf_url: str | None
    notes: str | None
    payment_terms: str | None
    
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    
    items: list[QuoteItemResponse]

    model_config = {"from_attributes": True}

class QuoteListResponse(BaseModel):
    quotes: list[QuoteResponse]
    total: int
