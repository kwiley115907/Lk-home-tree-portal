# invoice_generator.py

import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from models import ServiceRequest


def generate_invoice(request: ServiceRequest) -> str:
    """
    Generate a professional styled PDF invoice.

    :param request: ServiceRequest instance
    :return: Path to generated PDF file
    """

    os.makedirs("invoices", exist_ok=True)

    filename = f"invoices/invoice_{request.id}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4)

    elements = []
    styles = getSampleStyleSheet()

    # --- Logo ---
    logo_path = "static/images/logo.png"
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2 * inch, height=1 * inch)
        elements.append(logo)

    elements.append(Spacer(1, 12))

    # --- Company Info ---
    elements.append(Paragraph("<b>LK Home & Tree Co.</b>", styles["Title"]))
    elements.append(Paragraph("Professional Tree & Home Services", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # --- Invoice Info ---
    elements.append(Paragraph(f"Invoice #: {request.id}", styles["Normal"]))
    elements.append(Paragraph(f"Date: {datetime.utcnow().date()}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # --- Customer Info ---
    elements.append(Paragraph("<b>Billed To:</b>", styles["Heading3"]))
    elements.append(Paragraph(request.user.email, styles["Normal"]))
    elements.append(Spacer(1, 20))

    # --- Pricing Table ---
    subtotal = request.hours * request.rate
    tax = subtotal * 0.07  # 7% tax (adjust if needed)
    total = subtotal + tax

    data = [
        ["Description", "Hours", "Rate", "Amount"],
        [
            request.description,
            f"{request.hours}",
            f"${request.rate:.2f}",
            f"${subtotal:.2f}",
        ],
        ["", "", "Tax (7%)", f"${tax:.2f}"],
        ["", "", "<b>Total</b>", f"<b>${total:.2f}</b>"],
    ]

    table = Table(data, colWidths=[3 * inch, 1 * inch, 1 * inch, 1 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    elements.append(table)
    elements.append(Spacer(1, 30))

    elements.append(
        Paragraph("Thank you for your business!", styles["Normal"])
    )

    doc.build(elements)

    request.invoice_file = filename
    request.completed = True

    return filename
