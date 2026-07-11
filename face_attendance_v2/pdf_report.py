"""
PDF Report Generator using ReportLab
"""
import os
from datetime import datetime, date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

LOGS_DIR = os.path.join(os.path.dirname(__file__), "attendance_logs")
os.makedirs(LOGS_DIR, exist_ok=True)

PRIMARY   = colors.HexColor("#1a3c5e")
SECONDARY = colors.HexColor("#2ecc71")
LATE_CLR  = colors.HexColor("#f39c12")
ABSENT_CLR= colors.HexColor("#e74c3c")
ALT_ROW   = colors.HexColor("#f0f4f8")

def generate_daily_report(rows, target_date: str = None) -> str:
    target_date = target_date or date.today().isoformat()
    filename    = os.path.join(LOGS_DIR, f"daily_{target_date}.pdf")
    doc         = SimpleDocTemplate(filename, pagesize=A4,
                                    topMargin=1.5*cm, bottomMargin=1.5*cm,
                                    leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=styles["Title"],
                                 fontSize=18, textColor=PRIMARY, alignment=TA_CENTER)
    sub_style   = ParagraphStyle("s", parent=styles["Normal"],
                                 fontSize=11, textColor=colors.grey, alignment=TA_CENTER)
    story = [
        Paragraph("📋 Daily Attendance Report", title_style),
        Paragraph(f"Date: {target_date}  |  Generated: {datetime.now().strftime('%H:%M %d-%b-%Y')}",
                  sub_style),
        Spacer(1, 0.4*cm),
        HRFlowable(width="100%", thickness=2, color=PRIMARY),
        Spacer(1, 0.4*cm),
    ]

    # Summary cards
    total    = len(rows)
    present  = sum(1 for r in rows if r["status"] == "PRESENT")
    late     = sum(1 for r in rows if r["status"] == "LATE")
    absent   = total - present - late
    summary_data = [
        ["Total Registered", "Present", "Late", "Absent"],
        [str(total), str(present), str(late), str(absent)],
    ]
    summary_table = Table(summary_data, colWidths=[4*cm]*4)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PRIMARY),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 12),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("BACKGROUND", (0,1), (-1,1), ALT_ROW),
        ("BOX",        (0,0), (-1,-1), 1, PRIMARY),
        ("INNERGRID",  (0,0), (-1,-1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (1,1), (-1,-1), [colors.white, ALT_ROW]),
        ("FONTNAME", (0,1),(0,1),"Helvetica-Bold"),
    ]))
    story += [summary_table, Spacer(1, 0.6*cm)]

    # Main table
    headers = ["#", "Emp ID", "Name", "Check-In", "Check-Out", "Status"]
    data    = [headers]
    for i, r in enumerate(rows, 1):
        data.append([str(i), r["emp_id"], r["name"],
                     r["check_in"] or "—", r["check_out"] or "—", r["status"]])

    col_w = [1*cm, 2.5*cm, 5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
    t = Table(data, colWidths=col_w, repeatRows=1)
    row_colors = []
    for i, r in enumerate(rows, 1):
        if r["status"] == "LATE":
            row_colors.append(("BACKGROUND", (0,i), (-1,i), colors.HexColor("#fff3cd")))
        elif r["status"] == "ABSENT":
            row_colors.append(("BACKGROUND", (0,i), (-1,i), colors.HexColor("#fde8e8")))
        elif i % 2 == 0:
            row_colors.append(("BACKGROUND", (0,i), (-1,i), ALT_ROW))

    style = TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), PRIMARY),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 10),
        ("ALIGN",        (0,0), (-1,-1), "CENTER"),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("BOX",          (0,0), (-1,-1), 1, PRIMARY),
        ("INNERGRID",    (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("ROWHEIGHT",    (0,0), (-1,-1), 0.7*cm),
    ] + row_colors)
    t.setStyle(style)
    story.append(t)
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        "This report is system-generated. For queries contact the administrator.",
        ParagraphStyle("foot", parent=styles["Normal"], fontSize=8,
                       textColor=colors.grey, alignment=TA_CENTER)))
    doc.build(story)
    return filename


def generate_monthly_report(stats_rows, year: int, month: int) -> str:
    import calendar
    month_name = datetime(year, month, 1).strftime("%B %Y")
    filename   = os.path.join(LOGS_DIR, f"monthly_{year}_{month:02d}.pdf")
    doc = SimpleDocTemplate(filename, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=styles["Title"],
                                 fontSize=18, textColor=PRIMARY, alignment=TA_CENTER)
    sub_style   = ParagraphStyle("s", parent=styles["Normal"],
                                 fontSize=11, textColor=colors.grey, alignment=TA_CENTER)
    story = [
        Paragraph(f"📊 Monthly Attendance Report", title_style),
        Paragraph(f"{month_name}  |  Generated: {datetime.now().strftime('%H:%M %d-%b-%Y')}",
                  sub_style),
        Spacer(1, 0.4*cm),
        HRFlowable(width="100%", thickness=2, color=PRIMARY),
        Spacer(1, 0.5*cm),
    ]

    # Import here to avoid circular
    from database import attendance_percentage
    _, total_days = calendar.monthrange(year, month)
    working_days  = sum(1 for d in range(1, total_days+1)
                        if datetime(year, month, d).weekday() < 5)

    headers = ["#", "Emp ID", "Name", "Days Present", "Working Days", "Attendance %", "Status"]
    data    = [headers]
    for i, r in enumerate(stats_rows, 1):
        pct  = attendance_percentage(r["emp_id"], year, month)
        flag = "⚠️ LOW" if pct < 75 else "✅ OK"
        data.append([str(i), r["emp_id"], r["name"],
                     str(r["days_present"]), str(working_days),
                     f"{pct}%", flag])

    col_w = [0.8*cm, 2.5*cm, 4.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2*cm]
    t = Table(data, colWidths=col_w, repeatRows=1)
    row_colors = []
    for i, r in enumerate(stats_rows, 1):
        pct = attendance_percentage(r["emp_id"], year, month)
        if pct < 75:
            row_colors.append(("BACKGROUND", (0,i), (-1,i), colors.HexColor("#fde8e8")))
        elif i % 2 == 0:
            row_colors.append(("BACKGROUND", (0,i), (-1,i), ALT_ROW))

    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), PRIMARY),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("ALIGN",        (0,0), (-1,-1), "CENTER"),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("BOX",          (0,0), (-1,-1), 1, PRIMARY),
        ("INNERGRID",    (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("ROWHEIGHT",    (0,0), (-1,-1), 0.65*cm),
    ] + row_colors))
    story.append(t)
    doc.build(story)
    return filename
