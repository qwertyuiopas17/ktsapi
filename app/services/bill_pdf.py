"""
KTS — Bill PDF Generator
Generates printable invoice PDFs for customers.

Supports two formats:
  1. Thermal (80mm) — for receipt printers (most common for distributors)
  2. A4 — for formal invoices with GST details

Uses reportlab for PDF generation (pure Python, no external dependencies).
"""
from __future__ import annotations

import io
import sys
from datetime import date, datetime

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm as MM
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
except ImportError:
    print("[KTS PDF] WARNING: reportlab not installed. Run: pip install reportlab", file=sys.stderr)
    SimpleDocTemplate = None


def generate_bill_pdf(
    bill_data: dict,
    business_data: dict | None = None,
    format: str = "a4",  # "a4" or "thermal"
) -> bytes:
    """
    Generate a professional invoice PDF.

    Args:
        bill_data: Dict with bill details (from BillResponse schema)
        business_data: Optional business info (name, address, GSTIN)
        format: "a4" for formal invoice, "thermal" for receipt printer

    Returns:
        PDF bytes ready for download/share
    """
    if SimpleDocTemplate is None:
        raise RuntimeError("reportlab not installed. Run: pip install reportlab")

    buffer = io.BytesIO()

    if format == "thermal":
        page_size = (80 * MM, 297 * MM)  # 80mm thermal roll
    else:
        page_size = A4

    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=10 * MM,
        leftMargin=10 * MM,
        topMargin=10 * MM,
        bottomMargin=10 * MM,
    )

    styles = getSampleStyleSheet()
    story = []

    # Custom styles
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontSize=16 if format == "a4" else 12,
        alignment=TA_CENTER,
        spaceAfter=3 * MM,
    )
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Normal"],
        fontSize=10 if format == "a4" else 8,
        alignment=TA_CENTER,
        textColor=colors.grey,
    )
    normal_style = ParagraphStyle(
        "BillNormal",
        parent=styles["Normal"],
        fontSize=9 if format == "a4" else 7,
    )
    bold_style = ParagraphStyle(
        "BillBold",
        parent=styles["Normal"],
        fontSize=9 if format == "a4" else 7,
        fontName="Helvetica-Bold",
    )
    right_style = ParagraphStyle(
        "RightAlign",
        parent=styles["Normal"],
        fontSize=9 if format == "a4" else 7,
        alignment=TA_RIGHT,
    )

    # ─── Header ───
    biz = business_data or {}
    biz_name = biz.get("name", "Your Business")
    biz_address = biz.get("address", "")
    biz_gstin = biz.get("gstin", "")
    biz_phone = biz.get("phone", "")

    story.append(Paragraph(biz_name, title_style))
    if biz_address:
        story.append(Paragraph(biz_address, header_style))
    if biz_gstin:
        story.append(Paragraph(f"GSTIN: {biz_gstin}", header_style))
    if biz_phone:
        story.append(Paragraph(f"Phone: {biz_phone}", header_style))

    story.append(Spacer(1, 3 * MM))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 3 * MM))

    if bill_data.get("status") == "cancelled":
        story.append(Paragraph("<b>CANCELLED</b>", title_style))
        story.append(Spacer(1, 2 * MM))

    # ─── Invoice Info ───
    bill_number = bill_data.get("bill_number", "N/A")
    bill_date = bill_data.get("bill_date", str(date.today()))
    customer_name = bill_data.get("customer_name", "Walk-in Customer")

    info_data = [
        [Paragraph(f"<b>Invoice #:</b> {bill_number}", normal_style),
         Paragraph(f"<b>Date:</b> {bill_date}", right_style)],
        [Paragraph(f"<b>Customer:</b> {customer_name}", normal_style),
         Paragraph(f"<b>Type:</b> {bill_data.get('bill_type', 'Invoice').upper()}", right_style)],
    ]
    info_table = Table(info_data, colWidths=["50%", "50%"])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 5 * MM))

    # ─── Items Table ───
    items = bill_data.get("items", [])

    if format == "a4":
        header_row = ["#", "Item", "Qty", "Unit", "Rate", "GST%", "Amount"]
        col_widths = [8 * MM, None, 15 * MM, 15 * MM, 20 * MM, 15 * MM, 25 * MM]
    else:
        header_row = ["Item", "Qty", "Rate", "Amt"]
        col_widths = [None, 12 * MM, 15 * MM, 18 * MM]

    table_data = [header_row]

    for i, item in enumerate(items, 1):
        name = item.get("product_name", "Item")
        qty = item.get("quantity", 0)
        unit = item.get("unit", "")
        rate = item.get("rate", 0)
        gst = item.get("gst_rate", 0)
        total = item.get("total", 0)

        if format == "a4":
            table_data.append([
                str(i), name, f"{qty}", unit, f"{rate:.2f}", f"{gst}%", f"{total:.2f}"
            ])
        else:
            table_data.append([name, f"{qty} {unit}", f"{rate:.0f}", f"{total:.0f}"])

    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9 if format == "a4" else 7),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        # Body
        ("FONTSIZE", (0, 1), (-1, -1), 9 if format == "a4" else 7),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 5 * MM))

    # ─── Totals ───
    subtotal = bill_data.get("subtotal", 0)
    cgst = bill_data.get("cgst_amount", 0)
    sgst = bill_data.get("sgst_amount", 0)
    igst = bill_data.get("igst_amount", 0)
    total = bill_data.get("total_amount", 0)

    totals_data = [
        ["Subtotal", f"Rs {subtotal:.2f}"],
    ]
    if float(cgst) > 0:
        totals_data.append(["CGST", f"Rs {cgst:.2f}"])
    if float(sgst) > 0:
        totals_data.append(["SGST", f"Rs {sgst:.2f}"])
    if float(igst) > 0:
        totals_data.append(["IGST", f"Rs {igst:.2f}"])

    round_off = float(bill_data.get("round_off", 0) or 0)
    if round_off:
        totals_data.append(["Round off", f"Rs {round_off:+.2f}"])

    totals_data.append(["TOTAL", f"Rs {total:.2f}"])

    totals_table = Table(totals_data, colWidths=[None, 30 * MM])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10 if format == "a4" else 8),
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    # Right-align the totals table
    totals_wrapper = Table([[None, totals_table]], colWidths=["50%", "50%"])
    story.append(totals_wrapper)

    # ─── Payment Info ───
    story.append(Spacer(1, 5 * MM))
    payment_status = bill_data.get("payment_status", "credit")
    amount_paid = bill_data.get("amount_paid", 0)

    if payment_status == "paid":
        story.append(Paragraph("<b>Payment: PAID IN FULL</b>", bold_style))
    elif payment_status == "partial":
        story.append(Paragraph(f"<b>Paid: Rs {amount_paid:.2f} | Due: Rs {float(total) - float(amount_paid):.2f}</b>", bold_style))
    else:
        story.append(Paragraph(f"<b>CREDIT — Amount Due: Rs {total:.2f}</b>", bold_style))

    # ─── Footer ───
    story.append(Spacer(1, 8 * MM))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 2 * MM))
    story.append(Paragraph(
        f"Generated by KTS | {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7, textColor=colors.grey, alignment=TA_CENTER),
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
