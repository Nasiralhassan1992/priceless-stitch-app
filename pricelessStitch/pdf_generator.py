import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

PRIMARY_COLOR = colors.HexColor("#58111A")  # Brand Wine Color
SECONDARY_COLOR = colors.HexColor("#333333")

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_client_invoice(filepath, client_data, measurements):
    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    # Brand Title Header
    title_style = ParagraphStyle(
        'HeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#4A0E17') # Wine Color
    )
    sub_style = ParagraphStyle(
        'HeaderSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#333333')
    )

    story.append(Paragraph("PRICELESS STITCH", title_style))
    story.append(Paragraph("Bespoke Tailoring & Fashion House", sub_style))
    story.append(Spacer(1, 10))

    # Divider Line
    divider = Table([['']], colWidths=[540], rowHeights=[2])
    divider.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#4A0E17'))]))
    story.append(divider)
    story.append(Spacer(1, 15))

    # Client Info Metadata Grid
    meta_data = [
        [
            Paragraph("<b>Client Name:</b>", styles['Normal']), Paragraph(str(client_data.get('full_name', 'N/A')), styles['Normal']),
            Paragraph("<b>Order ID:</b>", styles['Normal']), Paragraph(f"#{client_data.get('id', 'N/A')}", styles['Normal'])
        ],
        [
            Paragraph("<b>Phone:</b>", styles['Normal']), Paragraph(str(client_data.get('phone', 'N/A')), styles['Normal']),
            Paragraph("<b>Order Date:</b>", styles['Normal']), Paragraph(str(client_data.get('created_at', 'N/A')), styles['Normal'])
        ],
        [
            Paragraph("<b>Garment Type:</b>", styles['Normal']), Paragraph(str(client_data.get('garment_type', 'N/A')), styles['Normal']),
            Paragraph("<b>Status:</b>", styles['Normal']), Paragraph(str(client_data.get('status', 'Pending')), styles['Normal'])
        ],
        [
            Paragraph("<b>Expected Delivery:</b>", styles['Normal']), Paragraph(str(client_data.get('delivery_date', 'N/A')), styles['Normal']),
            "", ""
        ]
    ]
    meta_table = Table(meta_data, colWidths=[100, 170, 100, 170])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))

    # Section Heading
    sec_heading = ParagraphStyle(
        'SecHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.HexColor('#4A0E17')
    )
    story.append(Paragraph("Client Measurement Slip (Inches)", sec_heading))
    story.append(Spacer(1, 10))

    # Extract all 14 measurement fields
    m_list = [
        ("Length / Shift", measurements.get("length_shift", 0.0)),
        ("Shoulder Width", measurements.get("shoulder", 0.0)),
        ("Neck", measurements.get("neck", 0.0)),
        ("Chest / Bust", measurements.get("chest", 0.0)),
        ("Sleeve Length", measurements.get("sleeves", 0.0)),
        ("Tommy / Midsection", measurements.get("tommy", 0.0)),
        ("Under Bust Round", measurements.get("under_bust_round", 0.0)),
        ("Shoulder to Under Bust", measurements.get("shoulder_to_under_bust", 0.0)),
        ("Trouser Length", measurements.get("trouser_length", 0.0)),
        ("Waist", measurements.get("waist", 0.0)),
        ("Hips", measurements.get("hips", 0.0)),
        ("Thigh / Lap", measurements.get("thigh", 0.0)),
        ("Knee", measurements.get("knee", 0.0)),
        ("Ankle", measurements.get("ankle", 0.0)),
    ]

    # Format into a 2-Column Table Grid (7 rows, 4 cells per row)
    table_rows = []
    for i in range(0, len(m_list), 2):
        item1 = m_list[i]
        item2 = m_list[i+1] if (i+1) < len(m_list) else ("", "")
        
        val1 = f'{item1[1]}"' if item1[0] else ""
        val2 = f'{item2[1]}"' if item2[0] else ""
        
        table_rows.append([item1[0], val1, item2[0], val2])

    m_table = Table(table_rows, colWidths=[150, 120, 150, 120])
    m_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FAFAFA')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    story.append(m_table)
    story.append(Spacer(1, 25))
    
    # Financial Calculation
    total = float(client_data.get('total_price', 0.0))
    deposit = float(client_data.get('down_payment', 0.0))
    balance = total - deposit

    # Payment Summary Table
    story.append(Paragraph("Payment Summary", sec_heading))
    story.append(Spacer(1, 8))

    payment_data = [
        ["Total Negotiated Price:", f"NGN {total:,.2f}"],
        ["Down Payment (Paid):", f"NGN {deposit:,.2f}"],
        ["Balance Remaining:", f"NGN {balance:,.2f}"]
    ]

    payment_table = Table(payment_data, colWidths=[360, 180])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,2), (1,2), colors.HexColor('#991B1B')), # Wine color highlight for balance
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))

    story.append(payment_table)
    story.append(Spacer(1, 20))

    # Footer note
    footer_style = ParagraphStyle(
        'FooterText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        textColor=colors.HexColor('#666666')
    )
    story.append(Paragraph("Thank you for choosing Priceless Stitch. For inquiries or fittings updates, contact us directly.", footer_style))

    doc.build(story)

def generate_admission_letter(filepath, student_data):
    """
    Generates an official Admission Letter for Priceless Stitch Fashion Academy with a Director Signature line.
    """
    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        rightMargin=45, leftMargin=45, topMargin=45, bottomMargin=45
    )
    story = []
    styles = getSampleStyleSheet()

    # Letterhead Header
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=PRIMARY_COLOR,
        alignment=1,
        fontName='Helvetica-Bold'
    )
    story.append(Paragraph("PRICELESS STITCH FASHION ACADEMY", header_style))
    story.append(Paragraph("<font size=10 color='#555555'>Excellence in Bespoke Garment Construction &amp; Fashion Design</font>", ParagraphStyle('Sub', alignment=1)))
    story.append(Spacer(1, 15))

    # Divider
    story.append(Table([['']], colWidths=[520], rowHeights=[2], style=TableStyle([('BACKGROUND', (0,0), (-1,-1), PRIMARY_COLOR)])))
    story.append(Spacer(1, 20))

    # Letter Metadata
    meta_info = [
        [Paragraph(f"<b>Date:</b> {student_data.get('registered_at', '')}", styles['Normal']),
         Paragraph(f"<b>Registration No:</b> <font color='#58111A'><b>{student_data.get('reg_number', '')}</b></font>", styles['Normal'])]
    ]
    t_meta = Table(meta_info, colWidths=[260, 260])
    story.append(t_meta)
    story.append(Spacer(1, 20))

    # Recipient
    story.append(Paragraph(f"<b>To:</b> {student_data.get('full_name', '')}", styles['Normal']))
    story.append(Paragraph(f"<b>Phone:</b> {student_data.get('phone', '')}", styles['Normal']))
    story.append(Spacer(1, 15))

    # Letter Title
    letter_title = ParagraphStyle('LTitle', parent=styles['Heading2'], fontSize=14, alignment=1, textColor=PRIMARY_COLOR, fontName='Helvetica-Bold')
    story.append(Paragraph("OFFICIAL LETTER OF ADMISSION", letter_title))
    story.append(Spacer(1, 15))

    # Body Content
    body_text = f"""
    Dear <b>{student_data.get('full_name', '')}</b>,<br/><br/>
    We are pleased to inform you that your application for admission into the <b>Priceless Stitch Fashion Academy</b> 
    has been accepted. You have been enrolled in the following program track:
    """
    story.append(Paragraph(body_text, styles['Normal']))
    story.append(Spacer(1, 10))

    # Course Details Box
    course_info = [
        [
            Paragraph("<b>Program Track:</b>", styles["Normal"]),
            Paragraph(student_data.get("program", ""), styles["Normal"]),
        ],
        [
            Paragraph("<b>Duration:</b>", styles["Normal"]),
            Paragraph(student_data.get("duration", ""), styles["Normal"]),
        ],
        [
            Paragraph("<b>Start Date:</b>", styles["Normal"]),
            Paragraph(
                str(student_data.get("start_date", "N/A")), styles["Normal"]
            ),
        ],
        [
            Paragraph("<b>End Date:</b>", styles["Normal"]),
            Paragraph(
                str(student_data.get("end_date", "N/A")), styles["Normal"]
            ),
        ],
        [
            Paragraph("<b>Tuition Fee:</b>", styles["Normal"]),
            Paragraph(
                f"₦{float(student_data.get('tuition_fee', 0.0)):,.2f}",
                styles["Normal"],
            ),
        ],
        [
            Paragraph("<b>Amount Paid:</b>", styles["Normal"]),
            Paragraph(
                f"₦{float(student_data.get('amount_paid', 0.0)):,.2f}",
                styles["Normal"],
            ),
        ],
        [
            Paragraph("<b>Payment Status:</b>", styles["Normal"]),
            Paragraph(
                student_data.get("payment_status", "Pending"), styles["Normal"]
            ),
        ],
    ]
    t_course = Table(course_info, colWidths=[140, 360])
    t_course.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(t_course)
    story.append(Spacer(1, 15))

    closing_text = """
    Please ensure all required practical kits are obtained prior to orientation. We look forward to guiding you on your 
    journey toward fashion mastery.
    """
    story.append(Paragraph(closing_text, styles['Normal']))
    story.append(Spacer(1, 30))

    # ---------------------------------------------------------
    # DIRECTOR SIGNATURE SECTION
    # ---------------------------------------------------------
    sig_line = Table([['']], colWidths=[200], rowHeights=[1])
    sig_line.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#333333'))]))

    sig_data = [
        ["", Paragraph("<b>For: PRICELESS STITCH ACADEMY</b>", styles['Normal'])],
        ["", ""],  # Empty space for physical signature or stamp
        ["", sig_line],
        ["", Paragraph("<b>Authorized Director Signature</b>", ParagraphStyle('SigSub', fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#444444')))]
    ]

    sig_table = Table(sig_data, colWidths=[300, 220], rowHeights=[12, 40, 2, 14])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('ALIGN', (1,0), (1,-1), 'LEFT'),
    ]))

    story.append(sig_table)

    doc.build(story)