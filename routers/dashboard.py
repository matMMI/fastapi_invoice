"""API routes for dashboard metrics."""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from db.session import get_session
from core.security import get_current_user
from models.user import User
from models.quote import Quote
from models.client import Client
from models.enums import QuoteStatus, Currency
from pydantic import BaseModel
from decimal import Decimal

router = APIRouter()


class StatusCount(BaseModel):
    status: str
    count: int


class CurrencyTotal(BaseModel):
    currency: str
    total: float


class RecentQuote(BaseModel):
    id: str
    quote_number: str
    status: str
    currency: str
    total: float
    created_at: str


class DashboardMetrics(BaseModel):
    total_quotes: int
    total_clients: int
    quotes_by_status: list[StatusCount]
    totals_by_currency: list[CurrencyTotal]
    recent_quotes: list[RecentQuote]


@router.get("/dashboard/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get dashboard metrics for the current user."""
    
    # Total quotes
    total_quotes = db.exec(
        select(func.count(Quote.id)).where(Quote.user_id == current_user.id)
    ).one()
    
    # Total clients
    total_clients = db.exec(
        select(func.count(Client.id)).where(Client.user_id == current_user.id)
    ).one()
    
    # Quotes by status
    status_counts = db.exec(
        select(Quote.status, func.count(Quote.id))
        .where(Quote.user_id == current_user.id)
        .group_by(Quote.status)
    ).all()
    
    quotes_by_status = [
        StatusCount(status=str(status.value), count=count)
        for status, count in status_counts
    ]
    
    # Totals by currency (only for accepted quotes)
    currency_totals = db.exec(
        select(Quote.currency, func.sum(Quote.total))
        .where(Quote.user_id == current_user.id)
        .where(Quote.status == QuoteStatus.ACCEPTED)
        .group_by(Quote.currency)
    ).all()
    
    totals_by_currency = [
        CurrencyTotal(currency=str(currency.value), total=float(total or 0))
        for currency, total in currency_totals
    ]
    
    # Recent quotes (last 5)
    recent = db.exec(
        select(Quote)
        .where(Quote.user_id == current_user.id)
        .order_by(Quote.created_at.desc())
        .limit(5)
    ).all()
    
    recent_quotes = [
        RecentQuote(
            id=str(q.id),
            quote_number=q.quote_number,
            status=str(q.status.value),
            currency=str(q.currency.value),
            total=float(q.total),
            created_at=q.created_at.isoformat()
        )
        for q in recent
    ]
    
    return DashboardMetrics(
        total_quotes=total_quotes or 0,
        total_clients=total_clients or 0,
        quotes_by_status=quotes_by_status,
        totals_by_currency=totals_by_currency,
        recent_quotes=recent_quotes
    )
