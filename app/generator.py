from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


def fit_font_size(text: str, font: str, max_size: int, max_width: float, min_size: int = 8) -> int:
    """Largest font size (<= max_size) at which text fits within max_width."""
    size = max_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def draw_qr(c: canvas.Canvas, data: str, x: float, y: float, size: float) -> None:
    """Draw a QR code encoding `data` with its lower-left corner at (x, y)."""
    widget = QrCodeWidget(data)
    x1, y1, x2, y2 = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, c, x, y)


def generate_certificate(
    name: str,
    course_title: str,
    date: str,
    output_path: str,
    certificate_id: str | None = None,
    verify_url: str | None = None,
) -> str:
    """Draw one certificate from the fixed template and save it as a PDF."""
    page_width, page_height = landscape(A4)
    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    center = page_width / 2
    max_text_width = page_width - 160  # keep text well inside the inner border

    c.setStrokeColor(colors.HexColor("#1F3A5F"))
    c.setLineWidth(6)
    c.rect(25, 25, page_width - 50, page_height - 50)
    c.setLineWidth(1.5)
    c.rect(40, 40, page_width - 80, page_height - 80)

    c.setFillColor(colors.HexColor("#1F3A5F"))
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(center, page_height - 130, "CERTIFICATE OF COMPLETION")

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 16)
    c.drawCentredString(center, page_height - 190, "This is to certify that")

    c.setFont("Helvetica-Bold", fit_font_size(name, "Helvetica-Bold", 34, max_text_width))
    c.drawCentredString(center, page_height - 250, name)
    c.setLineWidth(1)
    c.line(center - 200, page_height - 260, center + 200, page_height - 260)

    c.setFont("Helvetica", 16)
    c.drawCentredString(center, page_height - 310, "has successfully completed")
    c.setFont("Helvetica-Bold", fit_font_size(course_title, "Helvetica-Bold", 24, max_text_width))
    c.drawCentredString(center, page_height - 350, course_title)

    c.setFont("Helvetica", 14)
    c.drawCentredString(center, 100, f"Date: {date}")

    if certificate_id:
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.grey)
        c.drawCentredString(center, 62, f"Certificate ID: {certificate_id}  |  Verify at /verify/{certificate_id}")

    if verify_url:
        qr_size = 64
        qr_x = page_width - 40 - 16 - qr_size
        draw_qr(c, verify_url, qr_x, 62, qr_size)
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.grey)
        c.drawCentredString(qr_x + qr_size / 2, 52, "Scan to verify")

    c.showPage()
    c.save()
    return output_path