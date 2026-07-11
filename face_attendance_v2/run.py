"""
Launcher — Start both GUI and Web Dashboard simultaneously
"""
import threading
import subprocess
import sys
import os
import webbrowser
import time

def start_web():
    """Start Flask in background thread."""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    from web_app import app
    import database as db
    db.init_db()
    print("🌐 Web dashboard: http://127.0.0.1:5000")
    app.run(port=5000, debug=False, use_reloader=False)

def start_desktop():
    """Start Tkinter GUI."""
    from desktop_app import FaceAttendApp
    app = FaceAttendApp()
    app.mainloop()

if __name__ == "__main__":
    print("=" * 55)
    print("  FaceAttend v2 — Starting...")
    print("=" * 55)

    # Start Flask in daemon thread
    web_thread = threading.Thread(target=start_web, daemon=True)
    web_thread.start()
    time.sleep(1.5)   # Let Flask start

    # Open browser
    webbrowser.open("http://127.0.0.1:5000")

    # Start Tkinter (blocks until window closed)
    start_desktop()
