"""
Face Auth — Registration, Recognition, Liveness Detection (blink)
"""
import cv2, os, pickle, numpy as np
from datetime import datetime

try:
    import face_recognition
    FR = True
except ImportError:
    FR = False

DATA_DIR  = os.path.join(os.path.dirname(__file__), "data", "registered_faces")
ENC_FILE  = os.path.join(DATA_DIR, "encodings.pkl")
os.makedirs(DATA_DIR, exist_ok=True)

CASCADE   = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
EYE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

# ── EAR BLINK DETECTION ────────────────────────────────────────────────────
try:
    import dlib
    from imutils import face_utils
    DLIB_OK = True
    detector  = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(
        os.path.join(DATA_DIR, "shape_predictor_68_face_landmarks.dat")
    ) if os.path.exists(os.path.join(DATA_DIR, "shape_predictor_68_face_landmarks.dat")) else None
except Exception:
    DLIB_OK = False
    predictor = None

def _ear(eye):
    from scipy.spatial import distance as dist
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

# ── ENCODING STORE ─────────────────────────────────────────────────────────

def _load_enc():
    if os.path.exists(ENC_FILE):
        with open(ENC_FILE, "rb") as f: return pickle.load(f)
    return {"ids": [], "encodings": []}

def _save_enc(data):
    with open(ENC_FILE, "wb") as f: pickle.dump(data, f)

def _remove_enc(emp_id):
    data = _load_enc()
    idx  = [i for i,uid in enumerate(data["ids"]) if uid == emp_id]
    for i in sorted(idx, reverse=True):
        data["ids"].pop(i); data["encodings"].pop(i)
    _save_enc(data)

# ── REGISTRATION ───────────────────────────────────────────────────────────

def register_face(emp_id: str, name: str, num_samples=5, on_progress=None):
    """Capture face samples. Returns (True, msg) or (False, msg)."""
    _remove_enc(emp_id)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened(): return False, "Cannot open camera"

    samples, all_enc = 0, []
    while samples < num_samples:
        ret, frame = cap.read()
        if not ret: break
        display = frame.copy()
        gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces   = CASCADE.detectMultiScale(gray, 1.1, 5, minSize=(80,80))
        for (x,y,w,h) in faces:
            cv2.rectangle(display,(x,y),(x+w,y+h),(0,255,0),2)
        cv2.putText(display, f"SPACE=Capture ({samples}/{num_samples}) Q=Cancel",
                    (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)
        cv2.putText(display, f"Registering: {name}", (10, frame.shape[0]-15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,200,255), 2)
        cv2.imshow("Register Face", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            cap.release(); cv2.destroyAllWindows()
            return False, "Cancelled"
        if key == ord(" "):
            if len(faces) != 1:
                continue
            if FR:
                rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                locs  = face_recognition.face_locations(rgb, model="hog")
                encs  = face_recognition.face_encodings(rgb, locs)
                if encs: all_enc.append(encs[0]); samples += 1
            else:
                (x,y,w,h) = faces[0]
                crop = cv2.resize(gray[y:y+h,x:x+w], (100,100)).flatten().astype(np.float32)
                all_enc.append(crop); samples += 1
            if on_progress: on_progress(samples, num_samples)
    cap.release(); cv2.destroyAllWindows()
    if samples == num_samples:
        avg = np.mean(all_enc, axis=0)
        data = _load_enc()
        data["ids"].append(emp_id); data["encodings"].append(avg)
        _save_enc(data)
        return True, f"Registered {name} successfully"
    return False, "Incomplete registration"

# ── MATCHING ───────────────────────────────────────────────────────────────

def _match_fr(encoding, data, tol=0.5):
    if not data["encodings"]: return None, 0.0
    dists = face_recognition.face_distance(data["encodings"], encoding)
    idx   = np.argmin(dists)
    conf  = 1 - dists[idx]
    return (data["ids"][idx], conf) if dists[idx] <= tol else (None, conf)

def _match_cv(face_flat, data):
    def cos(a,b): return np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-9)
    if not data["encodings"]: return None, 0.0
    sims = [cos(face_flat, e) for e in data["encodings"]]
    idx  = int(np.argmax(sims))
    return (data["ids"][idx], sims[idx]) if sims[idx] > 0.75 else (None, sims[idx])

# ── LIVENESS (blink) ───────────────────────────────────────────────────────

class LivenessChecker:
    EAR_THRESH = 0.21
    CONSEC_FRAMES = 2

    def __init__(self):
        self.counter = 0
        self.blinks  = 0

    def update(self, frame) -> bool:
        """Returns True if a blink was detected this call."""
        if not DLIB_OK or predictor is None:
            return True  # fallback: always pass liveness
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rects = detector(gray, 0)
        for rect in rects:
            shape = face_utils.shape_to_np(predictor(gray, rect))
            lEye  = shape[42:48]
            rEye  = shape[36:42]
            ear   = (_ear(lEye) + _ear(rEye)) / 2.0
            if ear < self.EAR_THRESH:
                self.counter += 1
            else:
                if self.counter >= self.CONSEC_FRAMES:
                    self.blinks += 1
                    self.counter = 0
                    return True
                self.counter = 0
        return False

# ── LIVE ATTENDANCE LOOP ───────────────────────────────────────────────────

def run_attendance_loop(on_recognize, check_out_mode=False, liveness_required=True):
    """
    Opens camera. Calls on_recognize(emp_id, confidence, status) for each match.
    status: 'check_in' | 'check_out'
    """
    data     = _load_enc()
    cap      = cv2.VideoCapture(0)
    liveness = LivenessChecker()
    if not cap.isOpened(): return

    processed  = set()
    frame_cnt  = 0

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame_cnt += 1
        display    = frame.copy()
        gray       = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces      = CASCADE.detectMultiScale(gray, 1.1, 5, minSize=(60,60))

        if liveness_required:
            blinked = liveness.update(frame)
        else:
            blinked = True

        if frame_cnt % 3 == 0:
            for (x,y,w,h) in faces:
                emp_id, conf = None, 0.0
                if FR:
                    rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    locs = [(y, x+w, y+h, x)]
                    encs = face_recognition.face_encodings(rgb, locs)
                    if encs: emp_id, conf = _match_fr(encs[0], data)
                else:
                    crop = cv2.resize(gray[y:y+h,x:x+w],(100,100)).flatten().astype(np.float32)
                    emp_id, conf = _match_cv(crop, data)

                color = (0,255,0) if emp_id else (0,0,255)
                label = f"Unknown"
                if emp_id:
                    if not blinked and liveness_required:
                        label = "SPOOF DETECTED"; color = (0,0,200)
                    elif emp_id not in processed:
                        mode = "check_out" if check_out_mode else "check_in"
                        on_recognize(emp_id, conf, mode)
                        processed.add(emp_id)
                        label = f"ID:{emp_id} ({conf:.0%})"
                    else:
                        label = f"ID:{emp_id} ✓"

                cv2.rectangle(display,(x,y),(x+w,y+h),color,2)
                cv2.rectangle(display,(x,y-30),(x+w,y),color,-1)
                cv2.putText(display,label,(x+4,y-8),cv2.FONT_HERSHEY_SIMPLEX,0.55,(255,255,255),2)

        mode_txt = "CHECK-OUT MODE" if check_out_mode else "CHECK-IN MODE"
        live_txt = f"Blinks: {liveness.blinks}" if liveness_required else "Liveness: OFF"
        cv2.putText(display, mode_txt, (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,(0,255,255),2)
        cv2.putText(display, live_txt, (10,60), cv2.FONT_HERSHEY_SIMPLEX, 0.6,(200,200,200),1)
        cv2.putText(display, "Q = Quit", (10,90), cv2.FONT_HERSHEY_SIMPLEX, 0.6,(200,200,200),1)
        cv2.imshow("Face Attendance", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

def delete_face(emp_id):
    _remove_enc(emp_id)

def list_registered_ids():
    return _load_enc()["ids"]
