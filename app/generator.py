from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


def generate_certificate(name: str, course_title: str, date: str, output_path: str) -> str:
    """Draw one certificate from the fixed template and save it as a PDF."""
    page_width, page_height = landscape(A4)
    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    center = page_width / 2

    # Double border
    c.setStrokeColor(colors.HexColor("#1F3A5F"))
    c.setLineWidth(6)
    c.rect(25, 25, page_width - 50, page_height - 50)
    c.setLineWidth(1.5)
    c.rect(40, 40, page_width - 80, page_height - 80)

    # Title
    c.setFillColor(colors.HexColor("#1F3A5F"))
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(center, page_height - 130, "CERTIFICATE OF COMPLETION")

    # Intro line
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 16)
    c.drawCentredString(center, page_height - 190, "This is to certify that")

    # Recipient name
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(center, page_height - 250, name)
    c.setLineWidth(1)
    c.line(center - 200, page_height - 260, center + 200, page_height - 260)

    # Course line
    c.setFont("Helvetica", 16)
    c.drawCentredString(center, page_height - 310, "has successfully completed")
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(center, page_height - 350, course_title)

    # Date
    c.setFont("Helvetica", 14)
    c.drawCentredString(center, 100, f"Date: {date}")

    c.showPage()
    c.save()
    return output_path