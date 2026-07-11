"""
Flask Web Dashboard — Face Attendance System
Run: python app.py
Open: http://localhost:5000
"""
import os, csv, io, threading
from datetime import datetime, date
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, send_file, Response)
import database as db
import face_auth as fa
from email_alerts import send_low_attendance_alert, send_absence_alert
from pdf_report import generate_daily_report, generate_monthly_report

app = Flask(__name__)
app.secret_key = os.urandom(24)

db.init_db()

# ── AUTH DECORATOR ─────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ── AUTH ROUTES ────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        if db.verify_admin(u, p):
            session["admin"] = u
            db.log_action(u, "LOGIN")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    db.log_action(session.get("admin","?"), "LOGOUT")
    session.clear()
    return redirect(url_for("login"))

# ── DASHBOARD ──────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    today_rows  = db.get_today()
    total_users = len(db.all_users())
    present     = sum(1 for r in today_rows if r["status"] in ("PRESENT","LATE"))
    late        = sum(1 for r in today_rows if r["status"] == "LATE")
    now         = datetime.now()
    month_stats = db.monthly_stats(now.year, now.month)
    low_att     = db.low_attendance_users(now.year, now.month)
    return render_template("dashboard.html",
        today_rows=today_rows, total_users=total_users,
        present=present, late=late, absent=total_users-present,
        low_att=low_att, month_stats=month_stats,
        today=date.today().isoformat())

# ── ATTENDANCE ─────────────────────────────────────────────────────────────

@app.route("/attendance")
@login_required
def attendance():
    target = request.args.get("date", date.today().isoformat())
    rows   = db.get_by_date(target)
    return render_template("attendance.html", rows=rows, target_date=target)

@app.route("/attendance/export")
@login_required
def export_csv():
    target = request.args.get("date", date.today().isoformat())
    rows   = db.get_by_date(target)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["#","Emp ID","Name","Date","Check-In","Check-Out","Status"])
    for i,r in enumerate(rows,1):
        writer.writerow([i,r["emp_id"],r["name"],target,
                         r["check_in"] or "",r["check_out"] or "",r["status"]])
    output.seek(0)
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=attendance_{target}.csv"})

@app.route("/attendance/pdf")
@login_required
def export_pdf():
    target = request.args.get("date", date.today().isoformat())
    rows   = db.get_by_date(target)
    path   = generate_daily_report(rows, target)
    return send_file(path, as_attachment=True,
                     download_name=f"attendance_{target}.pdf")

@app.route("/attendance/monthly_pdf")
@login_required
def monthly_pdf():
    now   = datetime.now()
    y,m   = int(request.args.get("year",now.year)), int(request.args.get("month",now.month))
    stats = db.monthly_stats(y, m)
    path  = generate_monthly_report(stats, y, m)
    return send_file(path, as_attachment=True,
                     download_name=f"monthly_{y}_{m:02d}.pdf")

# ── CAMERA / LIVE ──────────────────────────────────────────────────────────

camera_thread_active = False

@app.route("/live")
@login_required
def live_page():
    return render_template("live.html")

@app.route("/start_camera/<mode>")
@login_required
def start_camera(mode):
    global camera_thread_active
    if camera_thread_active:
        return jsonify({"status": "already_running"})

    check_out = (mode == "checkout")

    def on_recognize(emp_id, conf, action):
        user = db.get_user(emp_id)
        name = user["name"] if user else emp_id
        if action == "check_in":
            result = db.mark_check_in(emp_id, name)
            if result["success"] and user and user["email"]:
                from email_alerts import send_attendance_confirmation
                send_attendance_confirmation(name, user["email"],
                                              result["time"], result["status"])
        else:
            db.mark_check_out(emp_id)

    def run():
        global camera_thread_active
        camera_thread_active = True
        fa.run_attendance_loop(on_recognize, check_out_mode=check_out,
                               liveness_required=True)
        camera_thread_active = False

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return jsonify({"status": "started", "mode": mode})

# ── USERS ──────────────────────────────────────────────────────────────────

@app.route("/users")
@login_required
def users():
    all_u = db.all_users()
    now   = datetime.now()
    user_stats = []
    for u in all_u:
        pct = db.attendance_percentage(u["emp_id"], now.year, now.month)
        user_stats.append({"user": u, "pct": pct})
    return render_template("users.html", user_stats=user_stats)

@app.route("/users/add", methods=["GET","POST"])
@login_required
def add_user():
    if request.method == "POST":
        emp_id = request.form["emp_id"].strip()
        name   = request.form["name"].strip()
        email  = request.form.get("email","").strip()
        phone  = request.form.get("phone","").strip()
        dept   = request.form.get("department","").strip()
        db.add_user(emp_id, name, email, phone, dept)
        db.log_action(session["admin"], "ADD_USER", f"{emp_id} - {name}")

        # Register face in background
        def reg():
            fa.register_face(emp_id, name)
        threading.Thread(target=reg, daemon=True).start()
        flash(f"User {name} added. Camera will open for face registration.", "success")
        return redirect(url_for("users"))
    return render_template("add_user.html")

@app.route("/users/delete/<emp_id>")
@login_required
def delete_user(emp_id):
    db.delete_user(emp_id)
    fa.delete_face(emp_id)
    db.log_action(session["admin"], "DELETE_USER", emp_id)
    flash(f"User {emp_id} deleted.", "info")
    return redirect(url_for("users"))

@app.route("/users/<emp_id>")
@login_required
def user_detail(emp_id):
    user    = db.get_user(emp_id)
    if not user: return "User not found", 404
    now     = datetime.now()
    history = db.get_by_range(f"{now.year}-01-01", date.today().isoformat())
    user_history = [r for r in history if r["emp_id"] == emp_id]
    pct     = db.attendance_percentage(emp_id, now.year, now.month)
    return render_template("user_detail.html", user=user,
                            history=user_history, pct=pct)

# ── REPORTS ────────────────────────────────────────────────────────────────

@app.route("/reports")
@login_required
def reports():
    now   = datetime.now()
    stats = db.monthly_stats(now.year, now.month)
    low   = db.low_attendance_users(now.year, now.month)
    return render_template("reports.html", stats=stats, low=low,
                            year=now.year, month=now.month,
                            month_name=now.strftime("%B %Y"))

@app.route("/reports/send_alerts")
@login_required
def send_alerts():
    now  = datetime.now()
    low  = db.low_attendance_users(now.year, now.month)
    sent = 0
    for u in low:
        if u["email"]:
            send_low_attendance_alert(u["name"], u["email"],
                                      u["percentage"], now.strftime("%B %Y"))
            sent += 1
    flash(f"Sent {sent} low-attendance alert(s).", "success")
    db.log_action(session["admin"], "SEND_ALERTS", f"{sent} emails")
    return redirect(url_for("reports"))

# ── SETTINGS ───────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    from email_alerts import load_config, save_config
    if request.method == "POST":
        action = request.form.get("action")
        if action == "change_password":
            new_pw = request.form.get("new_password","")
            confirm= request.form.get("confirm_password","")
            if new_pw and new_pw == confirm:
                db.change_password(session["admin"], new_pw)
                flash("Password changed successfully.", "success")
            else:
                flash("Passwords do not match.", "error")
        elif action == "save_email":
            cfg = load_config()
            cfg["smtp_host"]        = request.form.get("smtp_host", cfg["smtp_host"])
            cfg["smtp_port"]        = int(request.form.get("smtp_port", 587))
            cfg["sender_email"]     = request.form.get("sender_email","")
            cfg["sender_password"]  = request.form.get("sender_password","")
            cfg["enabled"]          = "enabled" in request.form
            save_config(cfg)
            flash("Email settings saved.", "success")
        return redirect(url_for("settings"))
    from email_alerts import load_config
    email_cfg = load_config()
    audit     = db.get_audit_log(50)
    return render_template("settings.html", email_cfg=email_cfg, audit=audit)

# ── API (for chart data) ───────────────────────────────────────────────────

@app.route("/api/weekly_chart")
@login_required
def weekly_chart():
    from datetime import timedelta
    today = date.today()
    labels, present_counts, late_counts = [], [], []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        rows = db.get_by_date(d.isoformat())
        labels.append(d.strftime("%a %d"))
        present_counts.append(sum(1 for r in rows if r["status"]=="PRESENT"))
        late_counts.append(sum(1 for r in rows if r["status"]=="LATE"))
    return jsonify({"labels": labels, "present": present_counts, "late": late_counts})

if __name__ == "__main__":
    print("🚀 Face Attendance System starting...")
    print("📌 Open: http://localhost:5000")
    print("👤 Login: admin / admin123")
    app.run(debug=True, host="0.0.0.0", port=5000)
