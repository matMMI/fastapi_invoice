from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlmodel import Session, func, select

from core.rate_limit import limiter
from core.security import get_current_user
from db.session import get_session
from models.client import Client
from models.enums import QuoteStatus
from models.quote import Quote
from models.user import User

router = APIRouter()

# Seuils legaux 2026 (source de verite unique)
SEUIL_TVA_FRANCHISE = 37500.0
SEUIL_TVA_TOLERANCE = 39100.0
SEUIL_MICRO_BNC = 77700.0
TAUX_URSSAF = 0.256  # BNC 2026
TAUX_ABATTEMENT_BNC = 0.34
ABATTEMENT_MINIMUM = 305.0


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
    urssaf_rate: float


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


class ThresholdAlert(BaseModel):
    level: str  # "info", "warning", "danger", "critical"
    threshold_name: str
    current_value: float
    threshold_value: float
    percentage: float
    message: str
    recommendation: str


class ProjectionData(BaseModel):
    ca_previsionnel_fin_annee: float
    jours_ecoules: int
    jours_total: int
    risque_depassement_tva: bool
    risque_depassement_micro: bool
    date_prevu_depassement_tva: str | None
    date_prevu_depassement_micro: str | None


class FiscalSimulation(BaseModel):
    ca_annuel: float
    urssaf_rate: float
    cotisations_urssaf: float
    abattement: float
    revenu_imposable: float
    impot: float
    revenu_net_annuel: float
    revenu_net_mensuel: float
    taux_charges_global: float
    tmi: int


class ThresholdStatus(BaseModel):
    revenue: float
    base_threshold: float  # Seuil franchise TVA: 37 500 €
    tolerance_threshold: float  # Seuil tolérance TVA: 39 100 €
    micro_ceiling: float  # Plafond micro-entreprise: 77 700 €
    status: str  # "ok", "info", "warning", "danger", "critical", "assujetti"
    message: str
    alerts: list[ThresholdAlert]
    projection: ProjectionData
    fiscal_simulation: FiscalSimulation


@router.get("/dashboard/metrics", response_model=DashboardMetrics)
@limiter.limit("20/minute")
async def get_dashboard_metrics(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
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

    status_counts = db.exec(
        select(Quote.status, func.count(Quote.id))
        .where(Quote.user_id == current_user.id)
        .group_by(Quote.status)
    ).all()

    quotes_by_status = [
        StatusCount(
            status=str(status.value) if hasattr(status, "value") else str(status), count=count
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
            total=float(total or 0),
        )
        for currency, total in currency_totals
    ]

    monthly_data = db.exec(
        select(func.to_char(Quote.created_at, "Mon"), func.sum(Quote.total))
        .where(
            Quote.user_id == current_user.id,
            Quote.status.in_([QuoteStatus.ACCEPTED, QuoteStatus.SIGNED]),
        )
        .group_by(func.date_trunc("month", Quote.created_at), func.to_char(Quote.created_at, "Mon"))
        .order_by(func.date_trunc("month", Quote.created_at))
    ).all()

    monthly_revenue = [
        MonthlyRevenue(name=month, total=float(total or 0)) for month, total in monthly_data
    ]

    # Recent Quotes are now fetched separately by the RecentQuotes component
    # We return empty here to satisfy the schema until we rigorously cleanup
    recent_quotes = []
    recent_quotes_total = 0

    today = datetime.now()
    current_year = today.year
    current_quarter = (today.month - 1) // 3 + 1

    ytd_revenue = (
        db.exec(
            select(func.sum(Quote.total)).where(
                Quote.user_id == current_user.id,
                Quote.status.in_([QuoteStatus.ACCEPTED, QuoteStatus.SIGNED]),
                func.extract("year", Quote.created_at) == current_year,
            )
        ).one()
        or 0.0
    )

    quarter_revenue = (
        db.exec(
            select(func.sum(Quote.total)).where(
                Quote.user_id == current_user.id,
                Quote.status.in_([QuoteStatus.ACCEPTED, QuoteStatus.SIGNED]),
                func.extract("year", Quote.created_at) == current_year,
                func.extract("quarter", Quote.created_at) == current_quarter,
            )
        ).one()
        or 0.0
    )

    fiscal_revenue = FiscalRevenue(
        year_to_date=float(ytd_revenue),
        quarter_to_date=float(quarter_revenue),
        current_year=current_year,
        current_quarter=current_quarter,
        urssaf_rate=TAUX_URSSAF,
    )

    # ====== Threshold Logic - Regles Comptables Micro-Entreprise BNC ======
    # CA = date encaissement (is_paid + payment_date), PAS date de facturation
    collected_revenue = (
        db.exec(
            select(func.sum(Quote.total)).where(
                Quote.user_id == current_user.id,
                Quote.is_paid,
                func.extract("year", Quote.payment_date) == current_year,
            )
        ).one()
        or 0.0
    )

    collected_revenue = float(collected_revenue)

    # Calcul impot progressif (bareme 2025)
    def calculate_progressive_tax(rev_imp: float) -> tuple[float, int]:
        brackets = [
            (11497, 0.00),
            (29315, 0.11),
            (83823, 0.30),
            (180294, 0.41),
            (float("inf"), 0.45),
        ]
        tax = 0.0
        prev_limit = 0
        cur_tmi = 0
        for limit, rate in brackets:
            if rev_imp <= prev_limit:
                break
            taxable = min(rev_imp, limit) - prev_limit
            tax += taxable * rate
            if taxable > 0:
                cur_tmi = int(rate * 100)
            prev_limit = limit
        return tax, cur_tmi

    # Simulation fiscale
    cotisations_urssaf = collected_revenue * TAUX_URSSAF
    abattement = (
        max(collected_revenue * TAUX_ABATTEMENT_BNC, ABATTEMENT_MINIMUM)
        if collected_revenue > 0
        else 0.0
    )
    revenu_imposable = max(collected_revenue - abattement, 0.0)
    impot, tmi = calculate_progressive_tax(revenu_imposable)
    revenu_net_annuel = collected_revenue - cotisations_urssaf - impot
    revenu_net_mensuel = revenu_net_annuel / 12 if revenu_net_annuel > 0 else 0.0
    taux_charges = (
        ((cotisations_urssaf + impot) / collected_revenue * 100) if collected_revenue > 0 else 0.0
    )

    fiscal_sim = FiscalSimulation(
        ca_annuel=collected_revenue,
        urssaf_rate=TAUX_URSSAF,
        cotisations_urssaf=round(cotisations_urssaf, 2),
        abattement=round(abattement, 2),
        revenu_imposable=round(revenu_imposable, 2),
        impot=round(impot, 2),
        revenu_net_annuel=round(revenu_net_annuel, 2),
        revenu_net_mensuel=round(revenu_net_mensuel, 2),
        taux_charges_global=round(taux_charges, 1),
        tmi=tmi,
    )

    # Projection fin annee
    today_date = date.today()
    jan1 = date(current_year, 1, 1)
    dec31 = date(current_year, 12, 31)
    jours_ecoules = (today_date - jan1).days + 1
    jours_total = (dec31 - jan1).days + 1

    ca_previsionnel = (
        (collected_revenue / jours_ecoules) * jours_total if jours_ecoules > 0 else 0.0
    )
    daily_rate = collected_revenue / jours_ecoules if jours_ecoules > 0 else 0.0

    date_prevu_tva = None
    date_prevu_micro = None

    if daily_rate > 0 and collected_revenue < SEUIL_TVA_FRANCHISE:
        days_to_tva = (SEUIL_TVA_FRANCHISE - collected_revenue) / daily_rate
        d = today_date + timedelta(days=int(days_to_tva))
        if d.year == current_year:
            date_prevu_tva = d.isoformat()

    if daily_rate > 0 and collected_revenue < SEUIL_MICRO_BNC:
        days_to_micro = (SEUIL_MICRO_BNC - collected_revenue) / daily_rate
        d = today_date + timedelta(days=int(days_to_micro))
        if d.year == current_year:
            date_prevu_micro = d.isoformat()

    projection = ProjectionData(
        ca_previsionnel_fin_annee=round(ca_previsionnel, 2),
        jours_ecoules=jours_ecoules,
        jours_total=jours_total,
        risque_depassement_tva=ca_previsionnel > SEUIL_TVA_FRANCHISE,
        risque_depassement_micro=ca_previsionnel > SEUIL_MICRO_BNC,
        date_prevu_depassement_tva=date_prevu_tva,
        date_prevu_depassement_micro=date_prevu_micro,
    )

    # Alertes multi-niveaux
    alerts: list[ThresholdAlert] = []
    threshold_status_val = "ok"
    threshold_msg = "En dessous du seuil de franchise TVA (37 500 euros)."

    if current_user.tax_status == "ASSUJETTI":
        threshold_status_val = "assujetti"
        threshold_msg = "Vous etes assujetti a la TVA."
    else:
        # Alertes TVA
        if collected_revenue > SEUIL_TVA_TOLERANCE:
            threshold_status_val = "critical"
            threshold_msg = (
                "Seuil de tolerance TVA (39 100 euros) depasse ! TVA applicable IMMEDIATEMENT."
            )
            alerts.append(
                ThresholdAlert(
                    level="critical",
                    threshold_name="tva_tolerance",
                    current_value=collected_revenue,
                    threshold_value=SEUIL_TVA_TOLERANCE,
                    percentage=round(collected_revenue / SEUIL_TVA_TOLERANCE * 100, 1),
                    message="Seuil de tolerance TVA (39 100 euros) depasse ! Vous DEVEZ facturer avec TVA 20% IMMEDIATEMENT.",
                    recommendation="Contacter un comptable en URGENCE.",
                )
            )
        elif collected_revenue > SEUIL_TVA_FRANCHISE:
            threshold_status_val = "danger"
            threshold_msg = "Seuil de franchise TVA (37 500 euros) depasse."
            alerts.append(
                ThresholdAlert(
                    level="danger",
                    threshold_name="tva_franchise",
                    current_value=collected_revenue,
                    threshold_value=SEUIL_TVA_FRANCHISE,
                    percentage=round(collected_revenue / SEUIL_TVA_FRANCHISE * 100, 1),
                    message="Seuil de franchise TVA depasse. TVA applicable au 01/01 de l annee prochaine.",
                    recommendation="STOP nouvelles missions. Preparer passage TVA.",
                )
            )
        elif collected_revenue >= SEUIL_TVA_FRANCHISE * 0.95:
            threshold_status_val = "warning"
            threshold_msg = "DANGER - Seuil TVA imminent."
            marge = round(SEUIL_TVA_FRANCHISE - collected_revenue, 2)
            pct = round(collected_revenue / SEUIL_TVA_FRANCHISE * 100, 1)
            alerts.append(
                ThresholdAlert(
                    level="warning",
                    threshold_name="tva_95",
                    current_value=collected_revenue,
                    threshold_value=SEUIL_TVA_FRANCHISE,
                    percentage=pct,
                    message=f"Vous etes a {pct}% du seuil TVA. Marge restante : {marge} euros.",
                    recommendation="Refuser/reporter les missions non critiques.",
                )
            )
        elif collected_revenue >= SEUIL_TVA_FRANCHISE * 0.90:
            threshold_status_val = "info"
            threshold_msg = "Attention, vous approchez du seuil TVA."
            marge = round(SEUIL_TVA_FRANCHISE - collected_revenue, 2)
            pct = round(collected_revenue / SEUIL_TVA_FRANCHISE * 100, 1)
            alerts.append(
                ThresholdAlert(
                    level="info",
                    threshold_name="tva_90",
                    current_value=collected_revenue,
                    threshold_value=SEUIL_TVA_FRANCHISE,
                    percentage=pct,
                    message=f"Approche du seuil TVA (37 500 euros). Marge restante : {marge} euros.",
                    recommendation="Calculez bien vos nouveaux devis.",
                )
            )

        # Alertes plafond micro-entreprise
        if collected_revenue > SEUIL_MICRO_BNC:
            threshold_status_val = "critical"
            alerts.append(
                ThresholdAlert(
                    level="critical",
                    threshold_name="micro_depassement",
                    current_value=collected_revenue,
                    threshold_value=SEUIL_MICRO_BNC,
                    percentage=round(collected_revenue / SEUIL_MICRO_BNC * 100, 1),
                    message="Plafond micro-entreprise (77 700 euros) depasse ! Sortie du regime.",
                    recommendation="Passage obligatoire en entreprise individuelle au regime reel.",
                )
            )
        elif collected_revenue >= SEUIL_MICRO_BNC * 0.95:
            alerts.append(
                ThresholdAlert(
                    level="warning",
                    threshold_name="micro_95",
                    current_value=collected_revenue,
                    threshold_value=SEUIL_MICRO_BNC,
                    percentage=round(collected_revenue / SEUIL_MICRO_BNC * 100, 1),
                    message="DANGER - Plafond micro-entreprise imminent.",
                    recommendation="Refuser les nouvelles missions.",
                )
            )
        elif collected_revenue >= SEUIL_MICRO_BNC * 0.90:
            alerts.append(
                ThresholdAlert(
                    level="info",
                    threshold_name="micro_90",
                    current_value=collected_revenue,
                    threshold_value=SEUIL_MICRO_BNC,
                    percentage=round(collected_revenue / SEUIL_MICRO_BNC * 100, 1),
                    message=f"Approche du plafond micro (77 700 euros). Marge : {round(SEUIL_MICRO_BNC - collected_revenue, 2)} euros.",
                    recommendation="Surveillez votre CA de pres.",
                )
            )

        # Alerte TMI 11%
        if revenu_imposable > 29315:
            alerts.append(
                ThresholdAlert(
                    level="warning",
                    threshold_name="tmi_30",
                    current_value=revenu_imposable,
                    threshold_value=29315,
                    percentage=round(revenu_imposable / 29315 * 100, 1),
                    message="Passage TMI 30%. Au-dela de 29 315 euros, imposition a 30%.",
                    recommendation="Evaluer report de missions au 01/01 prochain.",
                )
            )
        elif revenu_imposable >= 29315 * 0.95:
            alerts.append(
                ThresholdAlert(
                    level="info",
                    threshold_name="tmi_11_limit",
                    current_value=revenu_imposable,
                    threshold_value=29315,
                    percentage=round(revenu_imposable / 29315 * 100, 1),
                    message="Attention, passage TMI 30% imminent.",
                    recommendation="Optimisation : rester sous 29 315 euros de revenu imposable.",
                )
            )

        # Alerte projection fin annee
        if ca_previsionnel > SEUIL_TVA_FRANCHISE and collected_revenue <= SEUIL_TVA_FRANCHISE:
            alerts.append(
                ThresholdAlert(
                    level="warning",
                    threshold_name="projection_tva",
                    current_value=ca_previsionnel,
                    threshold_value=SEUIL_TVA_FRANCHISE,
                    percentage=round(ca_previsionnel / SEUIL_TVA_FRANCHISE * 100, 1),
                    message=f"Risque depassement TVA prevu. CA previsionnel : {round(ca_previsionnel, 2)} euros.",
                    recommendation=f"Date previsionnelle depassement : {date_prevu_tva or 'N/A'}.",
                )
            )

    threshold_data = ThresholdStatus(
        revenue=collected_revenue,
        base_threshold=SEUIL_TVA_FRANCHISE,
        tolerance_threshold=SEUIL_TVA_TOLERANCE,
        micro_ceiling=SEUIL_MICRO_BNC,
        status=threshold_status_val,
        message=threshold_msg,
        alerts=alerts,
        projection=projection,
        fiscal_simulation=fiscal_sim,
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
        threshold_status=threshold_data,
    )
