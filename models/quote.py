from sqlmodel import SQLModel, Field, Relationship
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone
from api.models.enums import Currency, QuoteStatus, DiscountType


class Quote(SQLModel, table=True):
    """Quote/invoice with line items and calculations."""
    
    __tablename__ = "quote"  # type: ignore
    
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    quote_number: str = Field(unique=True, index=True, max_length=50)
    user_id: str = Field(foreign_key="user.id", index=True)
    client_id: str = Field(foreign_key="client.id", index=True)
    currency: Currency = Field(default=Currency.EUR)
    status: QuoteStatus = Field(default=QuoteStatus.DRAFT, index=True)
    
    # Financial calculations
    subtotal: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    discount_type: DiscountType | None = Field(default=None)
    discount_value: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    tax_rate: Decimal = Field(default=Decimal("20.00"), max_digits=5, decimal_places=2)
    tax_amount: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    total: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    
    # PDF and metadata
    pdf_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None)
    payment_terms: str | None = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: datetime | None = Field(default=None)
    
    # Relationships
    items: list["QuoteItem"] = Relationship(back_populates="quote", cascade_delete=True)


class QuoteItem(SQLModel, table=True):
    """Line item within a quote."""
    
    __tablename__ = "quote_item"  # type: ignore
    
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    quote_id: str = Field(foreign_key="quote.id", index=True, ondelete="CASCADE")
    description: str
    quantity: Decimal = Field(max_digits=10, decimal_places=2)
    unit_price: Decimal = Field(max_digits=12, decimal_places=2)
    total: Decimal = Field(max_digits=12, decimal_places=2)
    order: int = Field(default=0)  # For sorting items
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relationships
    quote: Quote = Relationship(back_populates="items")
