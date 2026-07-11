"""
Desktop GUI — Tkinter
Full-featured GUI with face registration, live attendance, check-in/out
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import cv2
from PIL import Image, ImageTk
from datetime import datetime, date

from config import (OFFICE_START_HOUR, OFFICE_START_MINUTE,
                    LATE_CUTOFF_HOUR, LATE_CUTOFF_MINUTE)
import database as db
from face_auth import FaceAuthenticator

auth = FaceAuthenticator()


class FaceAttendApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🎭 FaceAttend Desktop")
        self.geometry("1100x700")
        self.configure(bg="#1a1a2e")
        self.resizable(True, True)

        self._camera_running = False
        self._cap = None
        self._frame_count = 0
        self._marked_session = set()

        db.init_db()
        self._build_ui()
        self._refresh_table()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI Build ────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg="#16213e", pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🎭  Face Authentication + Attendance System",
                 font=("Segoe UI", 16, "bold"), bg="#16213e", fg="white").pack()
        tk.Label(hdr, text=f"Today: {date.today().strftime('%A, %d %B %Y')}",
                 font=("Segoe UI", 9), bg="#16213e", fg="#888").pack()

        # Main area
        main = tk.Frame(self, bg="#1a1a2e")
        main.pack(fill="both", expand=True, padx=16, pady=12)

        # Left panel — camera + controls
        left = tk.Frame(main, bg="#0f3460", bd=0, relief="flat")
        left.pack(side="left", fill="y", padx=(0,10))

        self.cam_label = tk.Label(left, bg="#000", width=46, height=18)
        self.cam_label.pack(padx=12, pady=(12,6))

        self.status_var = tk.StringVar(value="Camera Off")
        tk.Label(left, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg="#0f3460", fg="#00d4ff").pack()

        btn_frame = tk.Frame(left, bg="#0f3460")
        btn_frame.pack(padx=12, pady=8, fill="x")

        self._btn(btn_frame, "▶ Start Attendance", "#27AE60", self._start_camera).pack(fill="x", pady=2)
        self._btn(btn_frame, "⏹ Stop Camera",      "#E74C3C", self._stop_camera).pack(fill="x", pady=2)
        tk.Frame(btn_frame, bg="#0f3460", height=8).pack()
        self._btn(btn_frame, "📷 Register Face",   "#3498DB", self._open_register).pack(fill="x", pady=2)
        self._btn(btn_frame, "🚪 Manual Check-Out", "#E67E22", self._manual_checkout).pack(fill="x", pady=2)
        self._btn(btn_frame, "🔍 Check Liveness",   "#9B59B6", self._liveness_check).pack(fill="x", pady=2)
        tk.Frame(btn_frame, bg="#0f3460", height=8).pack()
        self._btn(btn_frame, "🌐 Open Web Dashboard","#2C3E50", self._open_browser).pack(fill="x", pady=2)
        self._btn(btn_frame, "🔄 Refresh Table",    "#1ABC9C", self._refresh_table).pack(fill="x", pady=2)

        # Session info
        self.session_label = tk.Label(left, text="Session: 0 marked",
                                       font=("Segoe UI", 9), bg="#0f3460", fg="#aaa")
        self.session_label.pack(pady=(4,10))

        # Right panel — attendance table
        right = tk.Frame(main, bg="#1a1a2e")
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text="📋 Today's Attendance", font=("Segoe UI", 12, "bold"),
                 bg="#1a1a2e", fg="white").pack(anchor="w", pady=(0,6))

        # Treeview
        cols = ("ID", "Name", "Status", "Time In", "Time Out", "Hours")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=22)
        widths = [90, 180, 90, 90, 90, 70]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#16213e", foreground="white",
                         fieldbackground="#16213e", rowheight=26, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#0f3460",
                         foreground="white", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected","#3498DB")])

        self.tree.tag_configure("present", foreground="#27AE60")
        self.tree.tag_configure("late",    foreground="#E67E22")
        self.tree.tag_configure("out",     foreground="#aaa")

        sb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

    def _btn(self, parent, text, color, cmd):
        return tk.Button(parent, text=text, command=cmd,
                         bg=color, fg="white", font=("Segoe UI", 9, "bold"),
                         bd=0, relief="flat", cursor="hand2", pady=6,
                         activebackground=color, activeforeground="white")

    # ── Camera Loop ────────────────────────────────
    def _start_camera(self):
        if self._camera_running:
            return
        self._cap = cv2.VideoCapture(0)
        if not self._cap.isOpened():
            messagebox.showerror("Error", "Cannot open camera.")
            return
        self._camera_running = True
        self.status_var.set("🎥 Camera Running — Detecting faces...")
        threading.Thread(target=self._camera_loop, daemon=True).start()

    def _stop_camera(self):
        self._camera_running = False
        if self._cap:
            self._cap.release()
        self.status_var.set("Camera Off")
        self.cam_label.configure(image="", bg="#000")

    def _camera_loop(self):
        while self._camera_running:
            ret, frame = self._cap.read()
            if not ret:
                break

            self._frame_count += 1
            display = frame.copy()

            if self._frame_count % 3 == 0:
                results = auth.recognize_frame(frame)
                for (emp_id_or_unk, raw_id, conf, (x, y, w, h)) in results:
                    is_known = raw_id is not None
                    color = (0, 220, 0) if is_known else (0, 0, 220)

                    user = db.get_user(raw_id) if is_known else None
                    name = user["name"] if user else "Unknown"

                    cv2.rectangle(display, (x, y), (x+w, y+h), color, 2)
                    cv2.rectangle(display, (x, y-32), (x+w, y), color, -1)
                    cv2.putText(display, f"{name} ({conf:.0%})",
                                (x+4, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 1)

                    if is_known and raw_id not in self._marked_session:
                        now = datetime.now()
                        status = self._compute_status(now)
                        success, time_in = db.mark_checkin(raw_id, name, status)
                        if success:
                            self._marked_session.add(raw_id)
                            self.after(0, self._refresh_table)
                            self.after(0, lambda n=name, s=status:
                                self.status_var.set(f"✅ Marked: {n} — {s}"))

            # Convert to Tkinter image
            rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb).resize((480, 320))
            imgtk = ImageTk.PhotoImage(img)
            self.after(0, lambda i=imgtk: self._update_cam(i))

    def _update_cam(self, imgtk):
        self.cam_label.configure(image=imgtk)
        self.cam_label.image = imgtk

    def _compute_status(self, now):
        cutoff_h, cutoff_m = LATE_CUTOFF_HOUR, LATE_CUTOFF_MINUTE
        if now.hour > cutoff_h or (now.hour == cutoff_h and now.minute > cutoff_m):
            return "LATE"
        return "PRESENT"

    # ── Actions ─────────────────────────────────────
    def _open_register(self):
        win = tk.Toplevel(self)
        win.title("Register New Face")
        win.geometry("360x320")
        win.configure(bg="#1a1a2e")
        win.grab_set()

        def lbl(text):
            tk.Label(win, text=text, bg="#1a1a2e", fg="white",
                     font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(12,2))

        lbl("Employee / Student ID *")
        id_var = tk.StringVar()
        tk.Entry(win, textvariable=id_var, font=("Segoe UI", 10),
                 bd=1, relief="solid").pack(fill="x", padx=24)

        lbl("Full Name *")
        name_var = tk.StringVar()
        tk.Entry(win, textvariable=name_var, font=("Segoe UI", 10),
                 bd=1, relief="solid").pack(fill="x", padx=24)

        lbl("Email (optional)")
        email_var = tk.StringVar()
        tk.Entry(win, textvariable=email_var, font=("Segoe UI", 10),
                 bd=1, relief="solid").pack(fill="x", padx=24)

        progress_var = tk.StringVar(value="")
        tk.Label(win, textvariable=progress_var, bg="#1a1a2e", fg="#00d4ff",
                 font=("Segoe UI", 9)).pack(pady=6)

        def do_register():
            eid   = id_var.get().strip()
            name  = name_var.get().strip()
            email = email_var.get().strip()
            if not eid or not name:
                messagebox.showerror("Error", "ID and Name are required.", parent=win)
                return
            db.add_user(eid, name, email)

            def progress(n, total):
                progress_var.set(f"Captured {n}/{total} samples...")

            def run():
                ok, msg = auth.register_face(eid, name, progress_callback=progress)
                if ok:
                    win.after(0, lambda: messagebox.showinfo("Success",
                        f"'{name}' registered successfully!", parent=win))
                    win.after(0, win.destroy)
                else:
                    win.after(0, lambda: messagebox.showerror("Failed", msg, parent=win))

            threading.Thread(target=run, daemon=True).start()

        tk.Button(win, text="📷 Start Registration", command=do_register,
                  bg="#27AE60", fg="white", font=("Segoe UI", 10, "bold"),
                  bd=0, pady=8, cursor="hand2").pack(fill="x", padx=24, pady=12)

    def _manual_checkout(self):
        emp_id = simpledialog.askstring("Check Out", "Enter Employee/Student ID:")
        if not emp_id:
            return
        ok, time_out, hours = db.mark_checkout(emp_id.strip())
        if ok:
            messagebox.showinfo("Checked Out", f"Check-out at {time_out} | {hours:.1f} hours worked.")
            self._refresh_table()
        else:
            messagebox.showwarning("Not Found", "No active check-in found for this ID today.")

    def _liveness_check(self):
        result = auth.check_liveness()
        if result:
            messagebox.showinfo("Liveness", "✅ Live person confirmed!")
        else:
            messagebox.showwarning("Liveness", "❌ Liveness check failed. Possible spoof attempt.")

    def _open_browser(self):
        import webbrowser
        webbrowser.open("http://127.0.0.1:5000")

    def _refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        records = db.get_today()
        for r in records:
            tag = "late" if r["status"]=="LATE" else ("out" if r["time_out"] else "present")
            self.tree.insert("", "end", values=(
                r["emp_id"], r["name"], r["status"],
                r["time_in"] or "—", r["time_out"] or "—",
                f"{r['work_hours']:.1f}h" if r["work_hours"] else "—"
            ), tags=(tag,))
        self.session_label.configure(text=f"Session: {len(self._marked_session)} marked")

    def _on_close(self):
        self._stop_camera()
        self.destroy()


if __name__ == "__main__":
    try:
        from PIL import Image
    except ImportError:
        print("Installing Pillow...")
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])

    app = FaceAttendApp()
    app.mainloop()
