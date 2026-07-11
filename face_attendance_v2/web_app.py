"""
Flask Web Dashboard — Admin Panel
"""
from flask import (Flask, render_template, redirect, url_for,
                   request, session, flash, jsonify, send_file)
from functools import wraps
from datetime import datetime, date
import os, json

from config import SECRET_KEY, FLASK_PORT, LOW_ATTENDANCE_THRESHOLD
import database as db
from pdf_reports import generate_daily_report, generate_monthly_report
from email_alerts import send_low_attendance_alert

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ── Auth decorator ─────────────────────────────────────
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "admin" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ── Auth routes ────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","").strip()
        if db.verify_admin(u, p):
            session["admin"] = u
            db.log_action("LOGIN", u)
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    admin = session.pop("admin", "unknown")
    db.log_action("LOGOUT", admin)
    return redirect(url_for("login"))

@app.route("/change-password", methods=["GET","POST"])
@login_required
def change_password():
    if request.method == "POST":
        new_pw = request.form.get("new_password","").strip()
        if len(new_pw) >= 6:
            db.change_admin_password(session["admin"], new_pw)
            flash("Password changed successfully.", "success")
            db.log_action("PASSWORD_CHANGE", session["admin"])
        else:
            flash("Password must be at least 6 characters.", "danger")
    return render_template("change_password.html")


# ── Dashboard ──────────────────────────────────────────
@app.route("/")
@login_required
def dashboard():
    today_records = db.get_today()
    all_users     = db.get_all_users()
    now           = datetime.now()
    stats = {
        "total_users":   len(all_users),
        "present_today": sum(1 for r in today_records if r["status"] in ("PRESENT","LATE")),
        "late_today":    sum(1 for r in today_records if r["status"] == "LATE"),
        "absent_today":  len(all_users) - len(today_records),
        "month":         now.strftime("%B %Y"),
        "today":         date.today().isoformat(),
    }
    return render_template("dashboard.html", stats=stats,
                           records=today_records, admin=session["admin"])


# ── Attendance ─────────────────────────────────────────
@app.route("/attendance")
@login_required
def attendance():
    target = request.args.get("date", date.today().isoformat())
    records = db.get_by_date(target)
    return render_template("attendance.html", records=records, target_date=target)

@app.route("/api/today")
@login_required
def api_today():
    records = db.get_today()
    return jsonify([dict(r) for r in records])

@app.route("/api/chart-data")
@login_required
def api_chart_data():
    """Last 7 days attendance count for chart."""
    from datetime import timedelta
    data = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        recs = db.get_by_date(d)
        data.append({"date": d, "count": len(recs)})
    return jsonify(data)

@app.route("/api/monthly-stats")
@login_required
def api_monthly_stats():
    now   = datetime.now()
    stats = db.get_all_percentages(now.year, now.month)
    return jsonify(stats)


# ── Users ──────────────────────────────────────────────
@app.route("/users")
@login_required
def users():
    all_users = db.get_all_users()
    return render_template("users.html", users=all_users)

@app.route("/users/add", methods=["POST"])
@login_required
def add_user():
    emp_id = request.form.get("emp_id","").strip()
    name   = request.form.get("name","").strip()
    email  = request.form.get("email","").strip()
    dept   = request.form.get("department","").strip()
    phone  = request.form.get("phone","").strip()
    if emp_id and name:
        db.add_user(emp_id, name, email, dept, phone)
        db.log_action("ADD_USER", session["admin"], f"{name} ({emp_id})")
        flash(f"User '{name}' added. Register their face via the desktop app.", "success")
    return redirect(url_for("users"))

@app.route("/users/delete/<emp_id>")
@login_required
def delete_user(emp_id):
    user = db.get_user(emp_id)
    if user:
        db.delete_user(emp_id)
        db.log_action("DELETE_USER", session["admin"], f"{user['name']} ({emp_id})")
        flash(f"User '{user['name']}' deleted.", "warning")
    return redirect(url_for("users"))


# ── Reports ────────────────────────────────────────────
@app.route("/reports")
@login_required
def reports():
    now   = datetime.now()
    stats = db.get_all_percentages(now.year, now.month)
    low   = [s for s in stats if s["percentage"] < LOW_ATTENDANCE_THRESHOLD]
    return render_template("reports.html", stats=stats, low_attendance=low,
                           month=now.strftime("%B %Y"), threshold=LOW_ATTENDANCE_THRESHOLD)

@app.route("/reports/daily-pdf")
@login_required
def daily_pdf():
    target = request.args.get("date", date.today().isoformat())
    path   = generate_daily_report(target)
    db.log_action("EXPORT_DAILY_PDF", session["admin"], target)
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path))

@app.route("/reports/monthly-pdf")
@login_required
def monthly_pdf():
    now  = datetime.now()
    path = generate_monthly_report(now.year, now.month)
    db.log_action("EXPORT_MONTHLY_PDF", session["admin"])
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path))

@app.route("/reports/alert-low")
@login_required
def alert_low_attendance():
    now   = datetime.now()
    stats = db.get_all_percentages(now.year, now.month)
    sent  = 0
    for s in stats:
        if s["percentage"] < LOW_ATTENDANCE_THRESHOLD and s.get("email"):
            send_low_attendance_alert(
                s["name"], s["emp_id"], s["email"],
                s["percentage"], now.strftime("%B %Y")
            )
            sent += 1
    flash(f"Low-attendance alerts sent to {sent} student(s).", "info")
    db.log_action("SEND_LOW_ALERTS", session["admin"], f"{sent} alerts")
    return redirect(url_for("reports"))


# ── Audit Log ──────────────────────────────────────────
@app.route("/audit")
@login_required
def audit():
    logs = db.get_audit_log(200)
    return render_template("audit.html", logs=logs)


if __name__ == "__main__":
    db.init_db()
    print(f"\n🌐 Dashboard running at http://127.0.0.1:{FLASK_PORT}")
    print("   Login: admin / admin123  (change in config.py)\n")
    app.run(debug=True, port=FLASK_PORT)
