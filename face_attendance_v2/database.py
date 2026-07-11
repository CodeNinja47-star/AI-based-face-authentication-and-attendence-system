"""
Database Layer — SQLite
Tables: users, attendance, admins, audit_log
"""

import sqlite3, os, hashlib, secrets
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "attendance.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            emp_id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT,
            phone TEXT, department TEXT, registered_at TEXT
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT NOT NULL, name TEXT NOT NULL, date TEXT NOT NULL,
            check_in TEXT, check_out TEXT, status TEXT DEFAULT 'PRESENT',
            UNIQUE(emp_id, date)
        );
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, salt TEXT NOT NULL, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, admin TEXT, action TEXT,
            detail TEXT, timestamp TEXT
        );
        """)
        row = c.execute("SELECT 1 FROM admins").fetchone()
        if not row:
            salt = secrets.token_hex(16)
            ph = hashlib.sha256(("admin123" + salt).encode()).hexdigest()
            c.execute("INSERT INTO admins (username,password_hash,salt,created_at) VALUES (?,?,?,?)",
                      ("admin", ph, salt, datetime.now().isoformat()))

def _hp(password, salt):
    return hashlib.sha256((salt + password).encode()).hexdigest()

def verify_admin(username, password):
    with _conn() as c:
        row = c.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
    if not row: return False
    return _hp(password, row["salt"]) == row["password_hash"]

def change_password(username, new_password):
    salt = secrets.token_hex(16)
    with _conn() as c:
        c.execute("UPDATE admins SET password_hash=?, salt=? WHERE username=?",
                  (_hp(new_password, salt), salt, username))

def add_user(emp_id, name, email="", phone="", department=""):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?)",
                  (emp_id, name, email, phone, department, datetime.now().isoformat()))

def get_user(emp_id):
    with _conn() as c:
        return c.execute("SELECT * FROM users WHERE emp_id=?", (emp_id,)).fetchone()

def all_users():
    with _conn() as c:
        return c.execute("SELECT * FROM users ORDER BY name").fetchall()

def delete_user(emp_id):
    with _conn() as c:
        c.execute("DELETE FROM users WHERE emp_id=?", (emp_id,))

LATE_HOUR = 9

def mark_check_in(emp_id, name):
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")
    status = "LATE" if int(now.split(":")[0]) >= LATE_HOUR else "PRESENT"
    try:
        with _conn() as c:
            c.execute("INSERT INTO attendance (emp_id,name,date,check_in,status) VALUES (?,?,?,?,?)",
                      (emp_id, name, today, now, status))
        return {"success": True, "action": "check_in", "time": now, "status": status}
    except sqlite3.IntegrityError:
        return {"success": False, "action": "already_checked_in"}

def mark_check_out(emp_id):
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")
    with _conn() as c:
        row = c.execute("SELECT check_out FROM attendance WHERE emp_id=? AND date=?",
                        (emp_id, today)).fetchone()
        if not row: return {"success": False, "action": "not_checked_in"}
        if row["check_out"]: return {"success": False, "action": "already_checked_out"}
        c.execute("UPDATE attendance SET check_out=? WHERE emp_id=? AND date=?",
                  (now, emp_id, today))
    return {"success": True, "action": "check_out", "time": now}

def get_today():
    with _conn() as c:
        return c.execute("SELECT * FROM attendance WHERE date=? ORDER BY check_in",
                         (date.today().isoformat(),)).fetchall()

def get_by_date(d):
    with _conn() as c:
        return c.execute("SELECT * FROM attendance WHERE date=? ORDER BY check_in", (d,)).fetchall()

def get_by_range(start, end):
    with _conn() as c:
        return c.execute("SELECT * FROM attendance WHERE date BETWEEN ? AND ? ORDER BY date,check_in",
                         (start, end)).fetchall()

def attendance_percentage(emp_id, year, month):
    import calendar
    prefix = f"{year}-{month:02d}"
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) as cnt FROM attendance WHERE emp_id=? AND date LIKE ?",
                        (emp_id, f"{prefix}%")).fetchone()
    days_present = row["cnt"] if row else 0
    _, total = calendar.monthrange(year, month)
    working = sum(1 for d in range(1, total+1) if datetime(year, month, d).weekday() < 5)
    return round((days_present / working) * 100, 1) if working else 0.0

def monthly_stats(year, month):
    with _conn() as c:
        return c.execute(
            "SELECT emp_id, name, COUNT(*) as days_present FROM attendance "
            "WHERE date LIKE ? GROUP BY emp_id ORDER BY days_present DESC",
            (f"{year}-{month:02d}%",)).fetchall()

def low_attendance_users(year, month, threshold=75.0):
    rows = monthly_stats(year, month)
    result = []
    for r in rows:
        pct = attendance_percentage(r["emp_id"], year, month)
        if pct < threshold:
            u = get_user(r["emp_id"])
            result.append({"emp_id": r["emp_id"], "name": r["name"],
                           "percentage": pct, "email": u["email"] if u else ""})
    return result

def log_action(admin, action, detail=""):
    with _conn() as c:
        c.execute("INSERT INTO audit_log (admin,action,detail,timestamp) VALUES (?,?,?,?)",
                  (admin, action, detail, datetime.now().isoformat()))

def get_audit_log(limit=100):
    with _conn() as c:
        return c.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
