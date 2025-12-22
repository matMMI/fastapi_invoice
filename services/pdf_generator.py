"""PDF generation service for quotes using ReportLab."""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from io import BytesIO
from decimal import Decimal
from datetime import datetime

from models.quote import Quote


def generate_quote_pdf(quote: Quote) -> bytes:
    """
    Generate a professional PDF for a quote.
    
    Args:
        quote: Quote model instance with items loaded
        
    Returns:
        PDF content as bytes
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    # Container for PDF elements
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#4a4a4a'),
        spaceAfter=12,
    )
    
    # Title
    elements.append(Paragraph(f"Quote #{quote.quote_number}", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # Quote info table
    info_data = [
        ['Date:', datetime.now().strftime('%d/%m/%Y')],
        ['Status:', quote.status.value],
        ['Currency:', quote.currency.value],
    ]
    
    info_table = Table(info_data, colWidths=[4*cm, 6*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 1*cm))
    
    # Line items table
    elements.append(Paragraph("Line Items", heading_style))
    
    # Table header
    items_data = [['Description', 'Qty', 'Unit Price', 'Total']]
    
    # Table rows
    for item in quote.items:
        items_data.append([
            item.description,
            str(item.quantity),
            f"{float(item.unit_price):.2f}",
            f"{float(item.total):.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[9*cm, 2*cm, 3*cm, 3*cm])
    items_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#333333')),
        
        # Alignment
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 1*cm))
    
    # Totals table
    totals_data = [
        ['Subtotal:', f"{float(quote.subtotal):.2f} {quote.currency.value}"],
        [f'Tax ({float(quote.tax_rate)}%):', f"{float(quote.tax_amount):.2f} {quote.currency.value}"],
        ['Total:', f"{float(quote.total):.2f} {quote.currency.value}"],
    ]
    
    totals_table = Table(totals_data, colWidths=[10*cm, 7*cm])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -2), 10),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#333333')),
        ('TOPPADDING', (0, -1), (-1, -1), 12),
    ]))
    
    elements.append(totals_table)
    
    # Notes
    if quote.notes:
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph("Notes", heading_style))
        elements.append(Paragraph(quote.notes, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
