"""
Email Alerts Module
Sends absence / low-attendance alerts via SMTP
Configure SMTP settings in config.json or env vars
"""

import smtplib, json, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "data", "email_config.json")

DEFAULT_CONFIG = {
    "smtp_host":  "smtp.gmail.com",
    "smtp_port":  587,
    "sender_email": "",
    "sender_password": "",
    "enabled": False
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f: return json.load(f)
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f: json.dump(cfg, f, indent=2)

def _send(to_email: str, subject: str, body_html: str) -> bool:
    cfg = load_config()
    if not cfg.get("enabled") or not cfg.get("sender_email"):
        print(f"[Email disabled] Would send to {to_email}: {subject}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = cfg["sender_email"]
        msg["To"]      = to_email
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as s:
            s.starttls()
            s.login(cfg["sender_email"], cfg["sender_password"])
            s.sendmail(cfg["sender_email"], to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[Email error] {e}")
        return False

def send_attendance_confirmation(name: str, email: str, time_in: str, status: str):
    icon = "✅" if status == "PRESENT" else "⚠️"
    subject = f"{icon} Attendance Marked — {date.today()}"
    body = f"""
    <h2 style='color:#2d6a4f'>{icon} Attendance Confirmed</h2>
    <p>Dear <b>{name}</b>,</p>
    <p>Your attendance has been recorded.</p>
    <table style='border-collapse:collapse;font-size:15px'>
      <tr><td style='padding:6px 20px 6px 0'><b>Date</b></td><td>{date.today()}</td></tr>
      <tr><td style='padding:6px 20px 6px 0'><b>Check-in</b></td><td>{time_in}</td></tr>
      <tr><td style='padding:6px 20px 6px 0'><b>Status</b></td><td style='color:{"green" if status=="PRESENT" else "orange"}'>{status}</td></tr>
    </table>
    <br><p style='color:#888;font-size:12px'>This is an automated message from the Attendance System.</p>
    """
    return _send(email, subject, body)

def send_absence_alert(name: str, email: str, target_date: str):
    subject = f"❌ Absence Alert — {target_date}"
    body = f"""
    <h2 style='color:#c0392b'>❌ Absence Alert</h2>
    <p>Dear <b>{name}</b>,</p>
    <p>You were <b>absent</b> on <b>{target_date}</b>.</p>
    <p>If this is incorrect, please contact your administrator.</p>
    <br><p style='color:#888;font-size:12px'>Automated message — Attendance System</p>
    """
    return _send(email, subject, body)

def send_low_attendance_alert(name: str, email: str, percentage: float, month_label: str):
    subject = f"⚠️ Low Attendance Warning — {month_label}"
    body = f"""
    <h2 style='color:#e67e22'>⚠️ Low Attendance Warning</h2>
    <p>Dear <b>{name}</b>,</p>
    <p>Your attendance for <b>{month_label}</b> is <b style='color:red'>{percentage}%</b>,
       which is below the required <b>75%</b> threshold.</p>
    <p>Please ensure regular attendance to avoid academic/professional consequences.</p>
    <br><p style='color:#888;font-size:12px'>Automated message — Attendance System</p>
    """
    return _send(email, subject, body)
