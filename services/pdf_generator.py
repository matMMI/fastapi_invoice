"""PDF generation service for quotes using ReportLab."""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from io import BytesIO
from xml.sax.saxutils import escape as xml_escape
import ipaddress
import os
import socket
import urllib.request
import urllib.parse
import logging

from models.quote import Quote
from models.settings import Settings
from models.enums import QuoteStatus

from models.user import User
from models.enums import TaxStatus

logger = logging.getLogger(__name__)

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}
BLOCKED_IP_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                       "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                       "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                       "172.30.", "172.31.", "192.168.", "169.254.", "100.64.")


def _esc(text: str | None) -> str:
    """Escape user input for safe use in ReportLab Paragraph XML markup."""
    if text is None:
        return ""
    return xml_escape(str(text))


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is private/reserved (covers IPv4 and IPv6)."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_link_local
    except ValueError:
        return True  # If we can't parse it, block it


def _is_safe_url(url: str) -> bool:
    """Validate that a URL does not point to internal/private resources.

    Resolves DNS to prevent DNS rebinding and checks all resolved IPs.
    """
    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if hostname in BLOCKED_HOSTS:
        return False
    if any(hostname.startswith(prefix) for prefix in BLOCKED_IP_PREFIXES):
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    # Resolve DNS and check all IPs to prevent DNS rebinding
    try:
        addrinfos = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addrinfos:
            ip_str = sockaddr[0]
            if _is_private_ip(ip_str):
                return False
    except socket.gaierror:
        return False  # Cannot resolve = block
    return True


def generate_quote_pdf(quote: Quote, settings: Settings, user: User) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=10,
        alignment=TA_RIGHT
    )
    
    company_name_style = ParagraphStyle(
        'CompanyName',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=2,
    )
    
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=10,
        leading=14
    )
    
    right_align_style = ParagraphStyle(
        'RightAlign',
        parent=normal_style,
        alignment=TA_RIGHT
    )

    def truncate(text, length=50):
        if text and len(text) > length:
             return text[:length] + "..."
        return text

    company_name = user.business_name or settings.company_name or user.name
    company_address = user.address or settings.company_address
    company_email = settings.company_email or user.email
    company_siret = user.siret or settings.company_siret
    
    # Left Column: Logo & Company Info
    left_column = []
    if settings.company_logo_url:
        try:
            logo_path = settings.company_logo_url
            img = None
            # Resolve relative paths (e.g. /logo.png) via the frontend URL
            if logo_path.startswith("/") and not os.path.exists(logo_path):
                frontend_url = os.getenv("FRONTEND_URL", "")
                if not frontend_url:
                    # Fallback: use the first CORS origin as frontend URL
                    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
                    frontend_url = cors_origins.split(",")[0].strip()
                logo_path = f"{frontend_url.rstrip('/')}{logo_path}"
            if logo_path.startswith("http"):
                # Always validate URL safety (no bypass for internal logos)
                if not _is_safe_url(logo_path):
                    logger.warning("Blocked unsafe logo URL")
                    raise ValueError("URL de logo non autorisée")
                req = urllib.request.Request(logo_path, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    img_data = response.read(5 * 1024 * 1024)  # 5MB max
                    img_stream = BytesIO(img_data)
                    img = Image(img_stream, width=1*cm, height=1*cm, kind='proportional')
            # Do NOT load arbitrary local file paths — only allow HTTP(S) URLs
                
            if img:
                img.hAlign = 'LEFT'
                left_column.append(img)
                left_column.append(Spacer(1, 0.3*cm))
        except Exception as e:
            logger.warning(f"Logo loading failed: {e}")
            
    left_column.append(Paragraph(_esc(company_name), company_name_style))
    if company_address:
        left_column.append(Paragraph(_esc(company_address).replace('\n', '<br/>'), normal_style))
    if company_email:
        left_column.append(Paragraph(f"Email: {_esc(company_email)}", normal_style))
    if settings.company_phone:
        left_column.append(Paragraph(f"Tel: {_esc(settings.company_phone)}", normal_style))
    if settings.company_website:
        left_column.append(Paragraph(f"Web: {_esc(settings.company_website)}", normal_style))
    if company_siret:
        left_column.append(Paragraph(f"SIRET: {_esc(company_siret)}", normal_style))

    # Right Column: Quote Params & Client Info
    right_column = []
    
    # Quote Details
    doc_type = "FACTURE" if quote.is_paid or quote.status == QuoteStatus.SIGNED else "DEVIS"
    if quote.is_paid: doc_type = "FACTURE ACQUITTÉE"
    
    right_column.append(Paragraph(doc_type, title_style))
    right_column.append(Paragraph(f"N° {_esc(quote.quote_number)}", right_align_style))
    right_column.append(Paragraph(f"Date: {quote.created_at.strftime('%d/%m/%Y')}", right_align_style))
    right_column.append(Paragraph(f"Validité: 30 jours", right_align_style))
    
    if quote.is_paid and quote.payment_date:
        right_column.append(Paragraph(f"<b>Payé le : {quote.payment_date.strftime('%d/%m/%Y')}</b>", right_align_style))
    
    right_column.append(Spacer(1, 1*cm))
    
    # Client Info (Right Aligned)
    right_column.append(Paragraph("<b>Facturer à :</b>", right_align_style))
    if quote.client:
        if quote.client.company:
            right_column.append(Paragraph(_esc(truncate(quote.client.company)), right_align_style))
        right_column.append(Paragraph(_esc(truncate(quote.client.name)), right_align_style))
        if quote.client.address:
            right_column.append(Paragraph(_esc(truncate(quote.client.address)).replace('\n', '<br/>'), right_align_style))
        right_column.append(Paragraph(_esc(truncate(quote.client.email)), right_align_style))

    # Unified Header Table
    header_data = [[left_column, right_column]]
    header_table = Table(header_data, colWidths=[9*cm, 8*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 1*cm))
    
    # --- Line Items Table ---
    items_data = [['Description', 'Qté', 'Prix Unit.', 'Total']]
    for item in quote.items:
        items_data.append([
            Paragraph(_esc(item.description), normal_style),
            str(item.quantity),
            f"{float(item.unit_price):.2f} {quote.currency.value}",
            f"{float(item.total):.2f} {quote.currency.value}"
        ])
        
    items_table = Table(items_data, colWidths=[9*cm, 2*cm, 3*cm, 3*cm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#111827')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'), 
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # --- Totals Section ---
    totals_data = []
    
    # Determine Fiscal logic
    is_vat_applicable = True
    if quote.tax_status == TaxStatus.FRANCHISE:
        is_vat_applicable = False
    elif quote.tax_status == TaxStatus.ASSUJETTI:
        is_vat_applicable = True
    else:
        # Fallback to legacy
        is_vat_applicable = getattr(settings, 'is_vat_applicable', True)

    if is_vat_applicable:
        totals_data = [
            ['Sous-total HT:', f"{float(quote.subtotal):.2f} {quote.currency.value}"],
            [f'TVA ({float(quote.tax_rate)}%):', f"{float(quote.tax_amount):.2f} {quote.currency.value}"],
            ['Total TTC:', f"{float(quote.total):.2f} {quote.currency.value}"],
        ]
    else:
        totals_data = [
            ['Total à payer:', f"{float(quote.total):.2f} {quote.currency.value}"],
        ]
    
    totals_table = Table(totals_data, colWidths=[13*cm, 4*cm])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), 
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
    ]))
    elements.append(totals_table)
    
    # --- Footer / Notes ---
    if quote.notes:
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph("<b>Notes:</b>", normal_style))
        elements.append(Paragraph(_esc(quote.notes).replace('\n', '<br/>'), normal_style))

    # --- Fiscal & Legal Mentions ---
    elements.append(Spacer(1, 1*cm))
    legal_style = ParagraphStyle('Legal', parent=normal_style, fontSize=8, textColor=colors.gray)
    
    if not is_vat_applicable:
        mention = settings.vat_exemption_text or "TVA non applicable, art. 293 B du CGI"
        elements.append(Paragraph(_esc(mention), legal_style))
        
    # Legal Mentions (Penalties)
    if settings.late_payment_penalties:
        elements.append(Paragraph(f"Pénalités de retard : {_esc(settings.late_payment_penalties)}", legal_style))

    # --- Electronic Signature ---
    if quote.status == QuoteStatus.SIGNED and quote.signature_data:
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph("<b>Signature Électronique :</b>", normal_style))
        
        import base64
        try:
            if "," in quote.signature_data:
                sig_data = quote.signature_data.split(",")[1]
            else:
                sig_data = quote.signature_data
            
            sig_bytes = base64.b64decode(sig_data)
            sig_stream = BytesIO(sig_bytes)
            sig_img = Image(sig_stream, width=8*cm, height=3*cm, kind='proportional')
            sig_img.hAlign = 'LEFT'
            elements.append(sig_img)
            
            details = []
            if quote.signed_at:
                signed_date = quote.signed_at.strftime('%d/%m/%Y à %H:%M')
                details.append(f"Signé le {signed_date}")
            if quote.signer_name:
                details.append(f"Par : {_esc(quote.signer_name)}")
            if getattr(quote, 'signer_function', None):
                details.append(f"Fonction : {_esc(quote.signer_function)}")
            if getattr(quote, 'signer_email', None):
                details.append(f"Email : {_esc(quote.signer_email)}")
                
            elements.append(Paragraph(" - ".join(details), ParagraphStyle('SigDetails', parent=normal_style, fontSize=8, textColor=colors.gray)))
        except Exception as e:
            logger.error(f"Signature rendering failed: {e}")
            elements.append(Paragraph("[Signature non disponible]", normal_style))
        
    # --- Footer Custom Text ---
    if settings.pdf_footer_text:
        elements.append(Spacer(1, 1*cm))
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.gray, alignment=TA_CENTER)
        elements.append(Paragraph(_esc(settings.pdf_footer_text).replace('\n', '<br/>'), footer_style))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
