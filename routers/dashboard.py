"""API routes for dashboard metrics."""

from fastapi import APIRouter, Depends
from datetime import datetime
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



class MonthlyRevenue(BaseModel):
    name: str
    total: float


class FiscalRevenue(BaseModel):
    year_to_date: float
    quarter_to_date: float
    current_year: int
    current_quarter: int


class DashboardMetrics(BaseModel):
    total_quotes: int
    total_clients: int
    quotes_by_status: list[StatusCount]
    totals_by_currency: list[CurrencyTotal]
    recent_quotes: list[RecentQuote]
    monthly_revenue: list[MonthlyRevenue]
    fiscal_revenue: FiscalRevenue


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

    # Monthly Revenue (Last 6 months)
    # Using SQL date_trunc and to_char for Postgres
    monthly_data = db.exec(
        select(
            func.to_char(Quote.created_at, 'Mon'),
            func.sum(Quote.total)
        )
        .where(
            Quote.user_id == current_user.id,
            Quote.status == QuoteStatus.ACCEPTED,
            # We fetch all time for now, or could limit to last 12 months
            # func.now() - interval '1 year' is cleaner in raw SQL, but here simple is fine
        )
        .group_by(func.date_trunc('month', Quote.created_at), func.to_char(Quote.created_at, 'Mon'))
        .order_by(func.date_trunc('month', Quote.created_at))
    ).all()

    monthly_revenue = [
        MonthlyRevenue(name=month, total=float(total or 0))
        for month, total in monthly_data
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
    
    today = datetime.now()
    current_year = today.year
    current_quarter = (today.month - 1) // 3 + 1
    
    # Year to Date Revenue (Accepted quotes in current year)
    ytd_revenue = db.exec(
        select(func.sum(Quote.total))
        .where(
            Quote.user_id == current_user.id,
            Quote.status == QuoteStatus.ACCEPTED,
            func.extract('year', Quote.created_at) == current_year
        )
    ).one() or 0.0

    # Current Quarter Revenue
    quarter_revenue = db.exec(
        select(func.sum(Quote.total))
        .where(
            Quote.user_id == current_user.id,
            Quote.status == QuoteStatus.ACCEPTED,
            func.extract('year', Quote.created_at) == current_year,
            func.extract('quarter', Quote.created_at) == current_quarter
        )
    ).one() or 0.0
    
    fiscal_revenue = FiscalRevenue(
        year_to_date=float(ytd_revenue),
        quarter_to_date=float(quarter_revenue),
        current_year=current_year,
        current_quarter=current_quarter
    )
    
    return DashboardMetrics(
        total_quotes=total_quotes or 0,
        total_clients=total_clients or 0,
        quotes_by_status=quotes_by_status,
        totals_by_currency=totals_by_currency,
        recent_quotes=recent_quotes,
        monthly_revenue=monthly_revenue,
        fiscal_revenue=fiscal_revenue
    )
