"""
PDF Report Generator using ReportLab
"""
import os
from datetime import datetime, date
import calendar

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from config import LOGS_DIR, LOW_ATTENDANCE_THRESHOLD
import database as db

os.makedirs(LOGS_DIR, exist_ok=True)

# ── Colours ────────────────────────────────────────────
PRIMARY   = colors.HexColor("#2C3E50")
ACCENT    = colors.HexColor("#3498DB")
GREEN     = colors.HexColor("#27AE60")
RED       = colors.HexColor("#E74C3C")
ORANGE    = colors.HexColor("#E67E22")
LIGHT_BG  = colors.HexColor("#ECF0F1")
WHITE     = colors.white


def _header_style():
    styles = getSampleStyleSheet()
    return ParagraphStyle("Title", parent=styles["Title"],
                          textColor=WHITE, fontSize=18, alignment=TA_CENTER)


def _build_styles():
    s = getSampleStyleSheet()
    return s


def generate_daily_report(target_date: str = None) -> str:
    target_date = target_date or date.today().isoformat()
    records = db.get_by_date(target_date)
    filename = os.path.join(LOGS_DIR, f"daily_report_{target_date}.pdf")

    doc  = SimpleDocTemplate(filename, pagesize=A4,
                              leftMargin=1.5*cm, rightMargin=1.5*cm,
                              topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = _build_styles()
    story  = []

    # Title block
    story.append(Paragraph(
        f"<font color='white'><b>Daily Attendance Report</b></font>",
        ParagraphStyle("H", fontSize=20, textColor=WHITE, alignment=TA_CENTER,
                       backColor=PRIMARY, spaceAfter=6, spaceBefore=6,
                       leftIndent=-50, rightIndent=-50)
    ))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"Date: {target_date}  |  Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}",
                            styles["Normal"]))
    story.append(Spacer(1, 0.4*cm))

    # Summary row
    present = sum(1 for r in records if r["status"] in ("PRESENT","LATE"))
    late    = sum(1 for r in records if r["status"] == "LATE")
    total   = len(db.get_all_users())
    absent  = total - len(records)

    summary = [
        ["Total Enrolled", "Present", "Late", "Absent"],
        [str(total), str(present), str(late), str(absent)]
    ]
    st = TableStyle([
        ("BACKGROUND", (0,0), (-1,0), ACCENT),
        ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [LIGHT_BG, WHITE]),
        ("BOX",        (0,0), (-1,-1), 0.5, colors.grey),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
        ("FONTSIZE",   (0,0), (-1,-1), 11),
        ("PADDING",    (0,0), (-1,-1), 8),
    ])
    story.append(Table(summary, colWidths=[4*cm]*4, style=st))
    story.append(Spacer(1, 0.6*cm))

    # Detail table
    data = [["#", "Emp ID", "Name", "Status", "Time In", "Time Out", "Hours"]]
    for i, r in enumerate(records, 1):
        status_color = GREEN if r["status"] == "PRESENT" else (ORANGE if r["status"] == "LATE" else RED)
        data.append([
            str(i), r["emp_id"], r["name"],
            r["status"], r["time_in"] or "—",
            r["time_out"] or "—",
            f"{r['work_hours']:.1f}h" if r["work_hours"] else "—"
        ])

    col_w = [1*cm, 2.5*cm, 5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2*cm]
    ts = TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PRIMARY),
        ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [LIGHT_BG, WHITE]),
        ("BOX",        (0,0), (-1,-1), 0.5, colors.grey),
        ("GRID",       (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("PADDING",    (0,0), (-1,-1), 6),
    ])
    story.append(Table(data, colWidths=col_w, style=ts))
    doc.build(story)
    return filename


def generate_monthly_report(year: int = None, month: int = None) -> str:
    now   = datetime.now()
    year  = year  or now.year
    month = month or now.month
    month_name = calendar.month_name[month]

    stats    = db.get_all_percentages(year, month)
    filename = os.path.join(LOGS_DIR, f"monthly_report_{year}_{month:02d}.pdf")

    doc    = SimpleDocTemplate(filename, pagesize=A4,
                               leftMargin=1.5*cm, rightMargin=1.5*cm,
                               topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = _build_styles()
    story  = []

    story.append(Paragraph(
        f"Monthly Attendance Report — {month_name} {year}",
        ParagraphStyle("H", fontSize=18, textColor=PRIMARY, alignment=TA_CENTER,
                       spaceAfter=4, spaceBefore=4)
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}  |  "
        f"Threshold: {LOW_ATTENDANCE_THRESHOLD}%",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.5*cm))

    # Stats table
    data = [["#", "Emp ID", "Name", "Department", "Present", "Total Days", "Percentage", "Flag"]]
    for i, s in enumerate(stats, 1):
        flag = "⚠ LOW" if s["percentage"] < LOW_ATTENDANCE_THRESHOLD else "✓ OK"
        data.append([
            str(i), s["emp_id"], s["name"], s["department"] or "—",
            str(s["present"]), str(s["total"]),
            f"{s['percentage']:.1f}%", flag
        ])

    col_w = [0.8*cm, 2.2*cm, 4.5*cm, 3*cm, 1.8*cm, 2.2*cm, 2.5*cm, 1.8*cm]
    ts = TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PRIMARY),
        ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [LIGHT_BG, WHITE]),
        ("BOX",        (0,0), (-1,-1), 0.5, colors.grey),
        ("GRID",       (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("FONTSIZE",   (0,0), (-1,-1), 8.5),
        ("PADDING",    (0,0), (-1,-1), 6),
    ])
    # Highlight low attendance rows in red
    for i, s in enumerate(stats, 1):
        if s["percentage"] < LOW_ATTENDANCE_THRESHOLD:
            ts.add("TEXTCOLOR", (7, i), (7, i), RED)
            ts.add("FONTNAME",  (7, i), (7, i), "Helvetica-Bold")

    story.append(Table(data, colWidths=col_w, style=ts))
    story.append(Spacer(1, 0.5*cm))

    # Summary paragraph
    low_count = sum(1 for s in stats if s["percentage"] < LOW_ATTENDANCE_THRESHOLD)
    story.append(Paragraph(
        f"<b>Summary:</b> {len(stats)} enrolled &nbsp;|&nbsp; "
        f"<font color='red'>{low_count} below threshold</font>",
        styles["Normal"]
    ))

    doc.build(story)
    return filename
