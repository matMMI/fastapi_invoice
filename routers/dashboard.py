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
    client_name: str | None
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
    recent_quotes_total: int  # Total count for pagination
    monthly_revenue: list[MonthlyRevenue]
    fiscal_revenue: FiscalRevenue
    threshold_status: "ThresholdStatus"


class ThresholdStatus(BaseModel):
    revenue: float
    base_threshold: float
    max_threshold: float
    status: str # "ok", "warning", "exceeded", "assujetti"
    message: str


@router.get("/dashboard/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    page: int = 1,
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get dashboard metrics for the current user. Supports pagination for recent_quotes."""
    
    # Total quotes
    total_quotes = db.exec(
        select(func.count(Quote.id)).where(Quote.user_id == current_user.id)
    ).one()
    
    # Total clients
    total_clients = db.exec(
        select(func.count(Client.id)).where(Client.user_id == current_user.id)
    ).one()
    
    status_counts = db.exec(
        select(Quote.status, func.count(Quote.id))
        .where(Quote.user_id == current_user.id)
        .group_by(Quote.status)
    ).all()
    
    quotes_by_status = [
        StatusCount(
            status=str(status.value) if hasattr(status, "value") else str(status),
            count=count
        )
        for status, count in status_counts
    ]
    currency_totals = db.exec(
        select(Quote.currency, func.sum(Quote.total))
        .where(Quote.user_id == current_user.id)
        .where(Quote.status.in_([QuoteStatus.ACCEPTED, QuoteStatus.SIGNED]))
        .group_by(Quote.currency)
    ).all()
    
    totals_by_currency = [
        CurrencyTotal(
            currency=str(currency.value) if hasattr(currency, "value") else str(currency),
            total=float(total or 0)
        )
        for currency, total in currency_totals
    ]

    monthly_data = db.exec(
        select(
            func.to_char(Quote.created_at, 'Mon'),
            func.sum(Quote.total)
        )
        .where(
            Quote.user_id == current_user.id,
            Quote.status.in_([QuoteStatus.ACCEPTED, QuoteStatus.SIGNED]),
        )
        .group_by(func.date_trunc('month', Quote.created_at), func.to_char(Quote.created_at, 'Mon'))
        .order_by(func.date_trunc('month', Quote.created_at))
    ).all()

    monthly_revenue = [
        MonthlyRevenue(name=month, total=float(total or 0))
        for month, total in monthly_data
    ]
    
    # Get total count for pagination
    recent_quotes_total = db.exec(
        select(func.count(Quote.id)).where(Quote.user_id == current_user.id)
    ).one()

    # Calculate offset
    offset = (page - 1) * limit

    recent = db.exec(
        select(Quote, Client.name)
        .join(Client, Quote.client_id == Client.id, isouter=True)
        .where(Quote.user_id == current_user.id)
        .order_by(Quote.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    
    recent_quotes = [
        RecentQuote(
            id=str(q.id),
            quote_number=q.quote_number,
            client_name=client_name,
            status=str(q.status.value) if hasattr(q.status, "value") else str(q.status),
            currency=str(q.currency.value) if hasattr(q.currency, "value") else str(q.currency),
            total=float(q.total),
            created_at=q.created_at.isoformat()
        )
        for q, client_name in recent
    ]
    
    today = datetime.now()
    current_year = today.year
    current_quarter = (today.month - 1) // 3 + 1
    
    ytd_revenue = db.exec(
        select(func.sum(Quote.total))
        .where(
            Quote.user_id == current_user.id,
            Quote.status.in_([QuoteStatus.ACCEPTED, QuoteStatus.SIGNED]),
            func.extract('year', Quote.created_at) == current_year
        )
    ).one() or 0.0

    quarter_revenue = db.exec(
        select(func.sum(Quote.total))
        .where(
            Quote.user_id == current_user.id,
            Quote.status.in_([QuoteStatus.ACCEPTED, QuoteStatus.SIGNED]),
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
    
    # Threshold Logic (Phase 18)
    # Calculate Collected Revenue (Paid Date in Current Year)
    collected_revenue = db.exec(
        select(func.sum(Quote.total))
        .where(
            Quote.user_id == current_user.id,
            Quote.is_paid == True,
            func.extract('year', Quote.payment_date) == current_year
        )
    ).one() or 0.0
    
    collected_revenue = float(collected_revenue)
    threshold_status = "ok"
    threshold_msg = "En dessous du seuil de franchise (37 500 €)."
    
    if current_user.tax_status == "ASSUJETTI":
        threshold_status = "assujetti"
        threshold_msg = "Vous êtes assujetti à la TVA."
    else:
        if collected_revenue > 41250:
            threshold_status = "exceeded"
            threshold_msg = "Seuil majoré (41 250 €) dépassé ! Passage à la TVA obligatoire."
        elif collected_revenue > 37500:
            threshold_status = "warning"
            threshold_msg = "Seuil de base (37 500 €) dépassé. Attention au seuil majoré."
            
    threshold_data = ThresholdStatus(
        revenue=collected_revenue,
        base_threshold=37500.0,
        max_threshold=41250.0,
        status=threshold_status,
        message=threshold_msg
    )
    
    return DashboardMetrics(
        total_quotes=total_quotes or 0,
        total_clients=total_clients or 0,
        quotes_by_status=quotes_by_status,
        totals_by_currency=totals_by_currency,
        recent_quotes=recent_quotes,
        recent_quotes_total=recent_quotes_total or 0,
        monthly_revenue=monthly_revenue,
        fiscal_revenue=fiscal_revenue,
        threshold_status=threshold_data
    )
