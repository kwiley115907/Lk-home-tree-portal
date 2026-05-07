import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


COMPANY_NAME = "LK Home & Tree Co."
COMPANY_ADDRESS = [
    "3938 Surfside Blvd.",
    "Unit 3211",
    "Corpus Christi, TX 78402",
]


def generate_invoice_pdf(invoice) -> str:
    os.makedirs("invoices", exist_ok=True)

    filename = f"invoices/{invoice.invoice_number}.pdf"

    pdf = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    y = height - 50

    logo_path = "static/images/logo.png"

    if os.path.exists(logo_path):
        pdf.drawImage(
            logo_path,
            40,
            y - 45,
            width=90,
            height=60,
            preserveAspectRatio=True,
            mask="auto",
        )

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(150, y, COMPANY_NAME)
    y -= 20

    pdf.setFont("Helvetica", 10)
    for line in COMPANY_ADDRESS:
        pdf.drawString(150, y, line)
        y -= 13

    y -= 25

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "INVOICE")
    y -= 22

    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, y, f"Invoice #: {invoice.invoice_number}")
    y -= 16
    pdf.drawString(40, y, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    y -= 16
    pdf.drawString(40, y, f"Client: {invoice.client_name}")

    if invoice.client_email:
        y -= 16
        pdf.drawString(40, y, f"Email: {invoice.client_email}")

    y -= 35

    col_desc = 40
    col_qty = 320
    col_rate = 380
    col_amount = 465

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(col_desc, y, "Description")
    pdf.drawString(col_qty, y, "Qty")
    pdf.drawString(col_rate, y, "Rate")
    pdf.drawString(col_amount, y, "Amount")

    y -= 10
    pdf.line(40, y, width - 40, y)
    y -= 22

    subtotal = 0.0

    pdf.setFont("Helvetica", 10)

    for item in invoice.items:
        amount = item.quantity * item.rate
        subtotal += amount

        pdf.drawString(col_desc, y, item.description[:45])
        pdf.drawString(col_qty, y, f"{item.quantity:g}")
        pdf.drawString(col_rate, y, f"${item.rate:.2f}")
        pdf.drawString(col_amount, y, f"${amount:.2f}")

        y -= 20

        if y < 120:
            pdf.showPage()
            y = height - 50

    y -= 15

    tax = subtotal * invoice.tax_rate
    total = subtotal + tax

    pdf.setFont("Helvetica", 11)
    pdf.drawRightString(width - 40, y, f"Subtotal: ${subtotal:.2f}")
    y -= 18
    pdf.drawRightString(width - 40, y, f"Tax ({invoice.tax_rate * 100:.0f}%): ${tax:.2f}")
    y -= 20

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawRightString(width - 40, y, f"Total: ${total:.2f}")

    y -= 45
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, "Thank you for your business!")

    pdf.save()
    return filename
