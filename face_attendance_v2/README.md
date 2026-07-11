# 🎭 FaceAttend v2 — Face Authentication + Attendance System

A full-featured, production-ready attendance system with GUI, web dashboard, liveness detection, PDF reports, and email alerts.

---

## 🆕 New Features in v2

| Feature | Details |
|---------|---------|
| 🖥️ **Tkinter GUI** | Click-based desktop app, no terminal needed |
| 🌐 **Flask Web Dashboard** | Browser admin panel with live charts |
| ⏰ **Late Detection** | Auto-marks LATE after 9:15 AM |
| 🚪 **Check-in + Check-out** | Tracks entry, exit, and total work hours |
| 👁️ **Liveness Detection** | EAR blink detection — rejects printed photos |
| 📊 **Attendance %** | Monthly percentage per student/employee |
| 📄 **PDF Reports** | Daily + monthly printable reports (ReportLab) |
| 🚨 **Low Attendance Alert** | Flags and emails students below 75% |
| 📧 **Email Notifications** | Absence alerts + low-attendance emails |
| 🔐 **Admin Login** | Password-protected web panel |
| 📋 **Audit Log** | Every admin action is logged |

---

## 📁 Project Structure

```
face_attendance_v2/
│
├── run.py                  ← 🚀 START HERE (launches GUI + web)
├── desktop_app.py          ← Tkinter GUI
├── web_app.py              ← Flask web dashboard
├── face_auth.py            ← Face recognition + liveness
├── database.py             ← SQLite database layer
├── pdf_reports.py          ← ReportLab PDF generator
├── email_alerts.py         ← SMTP email notifications
├── config.py               ← All settings in one place
├── requirements.txt
│
├── templates/              ← Flask HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── attendance.html
│   ├── users.html
│   ├── reports.html
│   ├── audit.html
│   └── change_password.html
│
├── data/
│   ├── registered_faces/   ← Face encodings + user JSON
│   └── attendance.db       ← SQLite database
│
└── attendance_logs/        ← Exported PDF/CSV files
```

---

## ⚙️ Installation

### 1. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate       # Linux/Mac
venv\Scripts\activate          # Windows
```

### 2. Install core dependencies
```bash
pip install opencv-python numpy Pillow Flask reportlab
```

### 3. Install face_recognition (needs dlib)
```bash
# Windows
pip install cmake dlib face_recognition

# Linux
sudo apt install build-essential cmake libopenblas-dev liblapack-dev
pip install face_recognition

# Mac
brew install cmake
pip install face_recognition

# If dlib fails on any platform:
conda install -c conda-forge dlib
pip install face_recognition
```

---

## 🚀 Running the System

### Option A — Launch both GUI + Web together:
```bash
python run.py
```
This starts:
- 🖥️ Tkinter desktop app
- 🌐 Web dashboard at http://127.0.0.1:5000 (auto-opens in browser)

### Option B — Desktop only:
```bash
python desktop_app.py
```

### Option C — Web dashboard only:
```bash
python web_app.py
```

---

## 🔐 Default Admin Login

| Field | Value |
|-------|-------|
| URL | http://127.0.0.1:5000/login |
| Username | `admin` |
| Password | `admin123` |

> ⚠️ Change password immediately via **Settings → Change Password**

---

## 📧 Email Setup (Optional)

Edit `config.py`:
```python
EMAIL_ENABLED    = True
SENDER_EMAIL     = "your_email@gmail.com"
SENDER_PASSWORD  = "your_gmail_app_password"
```

> Use a **Gmail App Password** (not your Gmail login):
> Gmail → Account → Security → 2-Step Verification → App Passwords

---

## ⏰ Timing Configuration

In `config.py`:
```python
LATE_CUTOFF_HOUR   = 9    # 9 AM
LATE_CUTOFF_MINUTE = 15   # 15-minute grace period → LATE after 9:15
LOW_ATTENDANCE_THRESHOLD = 75.0   # Below 75% → alert
```

---

## 👁️ Liveness Detection

The system uses **Eye Aspect Ratio (EAR)** blink detection:
- If dlib's 68-point landmark predictor is available → precise EAR calculation
- Fallback: OpenCV eye Haar cascade (detects eye open/close)

For best liveness detection, download the dlib landmarks file:
```
shape_predictor_68_face_landmarks.dat
```
Place it in `data/registered_faces/`. Download from:
https://github.com/italojs/facial-landmarks-recognition/raw/master/shape_predictor_68_face_landmarks.dat

---

## 🔄 Workflow

```
1. python run.py
2. Web: Add users via Users page
3. Desktop: Click "Register Face" → capture 5 samples
4. Desktop: Click "Start Attendance" → camera detects faces
5. Web: View dashboard, generate PDF reports, send alerts
```

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| Camera not opening | Try `VideoCapture(1)` in `face_auth.py` |
| `ModuleNotFoundError: flask` | `pip install Flask` |
| `ModuleNotFoundError: reportlab` | `pip install reportlab` |
| dlib won't install | Use conda: `conda install -c conda-forge dlib` |
| Port 5000 in use | Change `FLASK_PORT = 5001` in `config.py` |
| Low accuracy | Re-register in good lighting; lower tolerance to 0.45 |

---

## 📦 Tech Stack

| Component | Library |
|-----------|---------|
| Face recognition | face_recognition (dlib) / OpenCV fallback |
| Liveness detection | EAR + dlib landmarks / Haar cascade fallback |
| Desktop GUI | Tkinter + Pillow |
| Web dashboard | Flask + Chart.js |
| Database | SQLite3 (built-in) |
| PDF reports | ReportLab |
| Email | smtplib (built-in) |

---

## 📄 License
MIT — Free for educational use.
