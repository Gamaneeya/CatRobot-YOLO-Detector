#!/usr/bin/env python3
"""
Windows-only laptop simulator based on the teammate's robot_teleop.py.
Uses laptop webcam + YOLO V7.2, preserves the original :8080 controls,
and replaces ALL motor/servo/buzzer hardware commands with safe mock actions.
AUTO FOLLOW drives only a MOCK motor, NEVER a real robot.
"""
import math, os, subprocess, tempfile, threading, time, wave, cv2, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote
from pathlib import Path
from ultralytics import YOLO
import numpy as np

# ===== settings =====
ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "best.pt"
YOLO_CONF = 0.10
TRACK_CONF = 0.10
GREEN_CONF = 0.60
CONFIRM_FRAMES = 2
IMG_SIZE = 640

FOLLOW_LEFT = 0.42
FOLLOW_RIGHT = 0.58
SIM_STOP_AREA_RATIO = 0.22
SIM_FORWARD_SPEED = 0.10
SIM_TURN_SPEED = 0.40
MAX_AUTO_AGE = 0.50

PORT     = 8080
CAM_ID   = 0        # try 1 or 2 if no image
LIN      = 0.3      # forward speed (m/s)
ANG      = 1.0      # turn speed (rad/s)
TIMEOUT  = 0.5      # stop if no command for this many seconds
BACKEND  = "auto"   # "auto" | "ros2" | "lib"
BUZZER_TOPIC = "/Buzzer"   # ROS2 buzzer topic (std_msgs/Bool) on Yahboom robots
SOUND_DIR = str(ROOT / "sounds")
AUDIO_DEV = "auto"  # "auto" = first USB sound card (voice module); or e.g. "plughw:2,0"

# Camera gimbal (2DOF PTZ on PWM servo ports of the control board)
PAN_ID, TILT_ID = 1, 2      # servo ports S1 / S2 - swap if arrows move the wrong axis
PAN_RANGE  = (0, 180)       # degrees
TILT_RANGE = (40, 140)      # keep tilt away from hitting the frame
PAN_CENTER, TILT_CENTER = 90, 90
SERVO_STEP = 3              # degrees per 50 ms while an arrow is held
PAN_INVERT, TILT_INVERT = False, False   # set True if an axis moves the wrong way

# Buzzer patterns: list of (on_ms, off_ms). Add or change freely.
PATTERNS = {
    "1": ("Short beep",  [(100, 0)]),
    "2": ("Double beep", [(100, 100), (100, 0)]),
    "3": ("Long beep",   [(800, 0)]),
    "4": ("Reverse",     [(300, 300)] * 3),
    "5": ("SOS",         [(100, 100)] * 3 + [(400, 100)] * 3 + [(100, 100)] * 3),
}

# Meow variants (played on the voice-module speaker): key -> (label, pitch x, length x)
MEOWS = {
    "m": ("Meow",            1.0, 1.0),
    "6": ("High meow",       1.6, 1.0),
    "7": ("Short meow",      1.0, 0.45),
    "8": ("Long meow",       1.0, 2.2),
    "9": ("High long meow",  1.6, 2.2),
    "0": ("High short meow", 1.6, 0.45),
}
MEOW_VOLUME = 0.65   # 0.0 - 1.0

# ===== MOCK motor + buzzer (Windows simulation only) =====
class Motor:
    def __init__(self):
        self.mode = "SIMULATOR - NO HARDWARE"
        self.last_drive = None
        print("Motor backend: SIMULATOR (cannot drive a real robot)")

    def send(self, v, w):
        drive = (round(float(v), 3), round(float(w), 3))
        if drive != self.last_drive:
            print(f"[MOCK MOTOR] linear={drive[0]:+.3f} angular={drive[1]:+.3f}")
            self.last_drive = drive

    def servo(self, sid, angle):
        print(f"[MOCK SERVO] id={sid} angle={int(angle)}")

    def beep(self, on):
        print(f"[MOCK BUZZER] {'ON' if on else 'OFF'}")

# ===== sounds =====
pattern_busy = threading.Event()
player = None

def play_pattern(motor, key):
    if key not in PATTERNS or pattern_busy.is_set():
        return
    def run():
        pattern_busy.set()
        try:
            for on_ms, off_ms in PATTERNS[key][1]:
                motor.beep(True);  time.sleep(on_ms / 1000)
                motor.beep(False); time.sleep(off_ms / 1000)
        finally:
            pattern_busy.clear()
    threading.Thread(target=run, daemon=True).start()

def sound_files():
    if not os.path.isdir(SOUND_DIR):
        return []
    return sorted(f for f in os.listdir(SOUND_DIR) if f.lower().endswith((".wav", ".mp3")))

def audio_device():
    return "Windows laptop speaker"

SAMPLE_RATE = 22050
MEOW_DIR = tempfile.mkdtemp(prefix="m1_meow_")

def _meow_samples(start_hz, end_hz, duration, volume):
    """One cat-like tone: pitch slides down, harmonics, soft attack/fade."""
    count = int(SAMPLE_RATE * duration)
    fade = min(0.08, duration / 3)
    out = bytearray()
    phase = 0.0
    for i in range(count):
        t = i / SAMPLE_RATE
        freq = start_hz + (end_hz - start_hz) * (i / max(1, count - 1))
        phase += 2 * math.pi * freq / SAMPLE_RATE      # smooth pitch slide
        env = max(0.0, min(1.0, t / 0.035, (duration - t) / fade))
        s = (math.sin(phase) + 0.45 * math.sin(2 * phase) + 0.20 * math.sin(3 * phase))
        s *= env * volume / 1.65
        out += int(max(-1.0, min(1.0, s)) * 32767).to_bytes(2, "little", signed=True)
    return out

def make_meow(key):
    """Build 'meow meow' WAV for a variant once, then reuse it."""
    path = os.path.join(MEOW_DIR, f"meow_{key}.wav")
    if not os.path.exists(path):
        _, p, l = MEOWS[key]
        gap = bytes(2 * int(SAMPLE_RATE * 0.12))
        audio = (_meow_samples(520 * p, 330 * p, 0.38 * l, MEOW_VOLUME) + gap +
                 _meow_samples(470 * p, 280 * p, 0.42 * l, MEOW_VOLUME))
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
            w.writeframes(audio)
    return path

def play_meow(key):
    if key in MEOWS:
        play_path(make_meow(key))

def play_file(name):
    if name in sound_files():              # only files inside SOUND_DIR
        play_path(os.path.join(SOUND_DIR, name))

def play_path(path):
    path = str(path)
    if not os.path.isfile(path):
        print("Audio file not found:", path)
        return
    if path.lower().endswith(".wav"):
        try:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            print("[SIM AUDIO] Playing", os.path.basename(path))
        except Exception as e:
            print("[SIM AUDIO] Playback failed:", e)
    else:
        print("[SIM AUDIO] MP3 playback is not supported by this simulator; use WAV")

# ===== shared command arbitration =====
cmd = [0.0, 0.0, False, 0, 0]
last = 0.0
mode = "MANUAL"
follow = {"v": 0.0, "w": 0.0, "action": "WAITING FOR CAMERA", "detail": "", "at": 0.0}
actual = {"v": 0.0, "w": 0.0, "action": "STOP"}
lock = threading.Lock()
center_req = threading.Event()


def simulate_follow(cx, area_ratio):
    if not (0 <= cx <= 1 and 0 <= area_ratio <= 1):
        return 0.0, 0.0, "INVALID TARGET - STOP"
    if area_ratio >= SIM_STOP_AREA_RATIO:
        return 0.0, 0.0, "TOO CLOSE (BOX SIZE) - STOP"
    if cx < FOLLOW_LEFT:
        return 0.0, SIM_TURN_SPEED, "TURN LEFT"
    if cx > FOLLOW_RIGHT:
        return 0.0, -SIM_TURN_SPEED, "TURN RIGHT"
    return SIM_FORWARD_SPEED, 0.0, "FORWARD (SIM ONLY)"


def publish_follow(v, w, action, detail):
    with lock:
        follow.update(v=float(v), w=float(w), action=action, detail=detail,
                      at=time.monotonic())


def set_mode(new_mode):
    global mode, last
    if new_mode not in ("MANUAL", "AUTO", "STOPPED"):
        return False
    with lock:
        mode = new_mode
        cmd[:] = [0.0, 0.0, False, 0, 0]
        last = 0.0
        actual.update(v=0.0, w=0.0, action="STOP")
    print("[SIM MODE]", new_mode)
    return True


def set_keys(keys):
    global last
    with lock:
        if mode == "STOPPED":
            return
        v = LIN * (("w" in keys) - ("s" in keys))
        w = ANG * (("a" in keys) - ("d" in keys))
        pan = ("j" in keys) - ("l" in keys)
        tilt = ("i" in keys) - ("k" in keys)
        if mode == "AUTO":
            v = w = 0.0
        cmd[:] = [v, w, ("h" in keys), pan, tilt]
        last = time.time()


def clamp(x, lo_hi):
    return max(lo_hi[0], min(lo_hi[1], x))


# ===== single webcam capture + YOLO V7.2 overlay =====
class Camera:
    def __init__(self):
        self.jpeg = None
        self.running = True
        self.verified_frames = 0

        if not MODEL_PATH.is_file():
            raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

        self.model = YOLO(str(MODEL_PATH))
        print("YOLO model:", MODEL_PATH)
        print("YOLO classes:", self.model.names)

        self.cap = cv2.VideoCapture(CAM_ID)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open webcam {CAM_ID}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print("Webcam opened:", CAM_ID)
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def loop(self):
        prev_time = time.monotonic()
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                self.verified_frames = 0
                publish_follow(0, 0, "CAMERA FRAME LOST - STOP", "Camera read failed")
                blank = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank, "CAMERA FRAME LOST - STOP", (20, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                self.encode(blank)
                time.sleep(0.1)
                continue

            try:
                result = self.model.predict(
                    source=frame, conf=YOLO_CONF, iou=0.45,
                    imgsz=IMG_SIZE, max_det=10, verbose=False,
                )[0]
            except Exception as e:
                print("YOLO inference error:", e)
                self.verified_frames = 0
                publish_follow(0, 0, "YOLO ERROR - STOP", str(e))
                cv2.putText(frame, "YOLO ERROR - STOP", (16, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                self.encode(frame)
                time.sleep(0.1)
                continue

            h, w = frame.shape[:2]
            candidates = list(result.boxes)
            allowed = [b for b in candidates if float(b.conf[0]) >= TRACK_CONF]
            target = max(allowed, key=lambda b: float(b.conf[0])) if allowed else None

            for b in candidates:
                conf = float(b.conf[0])
                x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
                color = (0, 255, 0) if conf >= GREEN_CONF else (0, 165, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"Dino? {conf:.2f}", (x1, max(18, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

            if target is not None:
                self.verified_frames = min(self.verified_frames + 1, CONFIRM_FRAMES)
                x1, y1, x2, y2 = target.xyxy[0].tolist()
                cx = ((x1 + x2) / 2) / w
                area = max(0.0, x2-x1) * max(0.0, y2-y1) / (w*h)
                conf = float(target.conf[0])
                detail = f"X: {cx:.2f} | Box area: {area:.1%} | Conf: {conf:.2f}"
                if self.verified_frames < CONFIRM_FRAMES:
                    v, turn, action = 0.0, 0.0, "VERIFYING TARGET - STOP"
                else:
                    v, turn, action = simulate_follow(cx, area)
            else:
                self.verified_frames = 0
                v, turn = 0.0, 0.0
                if candidates:
                    action = "LOW CONFIDENCE - STOP"
                    detail = f"Needs at least {TRACK_CONF:.2f}"
                else:
                    action = "NO TARGET - STOP"
                    detail = "No Dino detected this frame"

            publish_follow(v, turn, action, detail)
            now = time.monotonic()
            fps = 1.0 / max(now - prev_time, 1e-6)
            prev_time = now
            with lock:
                active_mode = mode
            cv2.putText(frame, f"PI DRY RUN | MODE: {active_mode} | NO REAL MOTORS",
                        (12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2)
            cv2.putText(frame, action, (12, 52),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.67, (0, 255, 255), 2)
            cv2.putText(frame, f"{detail} | FPS: {fps:.1f}", (12, 78),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 2)
            self.encode(frame)

    def encode(self, frame):
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            self.jpeg = buf.tobytes()

    def close(self):
        self.running = False
        if hasattr(self, "thread"):
            self.thread.join(timeout=2)
        self.cap.release()


def control_loop(motor):
    horn_on = False
    pan, tilt = PAN_CENTER, TILT_CENTER
    motor.servo(PAN_ID, pan)
    motor.servo(TILT_ID, tilt)
    while True:
        with lock:
            if time.time() - last > TIMEOUT:
                cmd[:] = [0.0, 0.0, False, 0, 0]
            manual_v, manual_w, horn, dp, dt = cmd
            active_mode = mode
            if active_mode == "AUTO":
                if time.monotonic() - follow["at"] <= MAX_AUTO_AGE:
                    v, w = follow["v"], follow["w"]
                    motion_action = follow["action"]
                else:
                    v, w = 0.0, 0.0
                    motion_action = "STALE DETECTION - STOP"
            elif active_mode == "MANUAL":
                v, w = manual_v, manual_w
                motion_action = "MANUAL COMMAND"
            else:
                v, w = 0.0, 0.0
                motion_action = "STOP LATCHED"
                horn = False
                dp = dt = 0
            actual.update(v=v, w=w, action=motion_action)
        motor.send(v, w)
        if center_req.is_set() and active_mode != "STOPPED":
            center_req.clear()
            dp = dt = 0
            pan, tilt = PAN_CENTER, TILT_CENTER
            motor.servo(PAN_ID, pan)
            motor.servo(TILT_ID, tilt)
        if dp:
            new = clamp(pan + dp * SERVO_STEP * (-1 if PAN_INVERT else 1), PAN_RANGE)
            if new != pan:
                pan = new
                motor.servo(PAN_ID, pan)
        if dt:
            new = clamp(tilt + dt * SERVO_STEP * (-1 if TILT_INVERT else 1), TILT_RANGE)
            if new != tilt:
                tilt = new
                motor.servo(TILT_ID, tilt)
        if not pattern_busy.is_set() and horn != horn_on:
            motor.beep(horn)
            horn_on = horn
        time.sleep(0.05)


def get_status():
    with lock:
        return {
            "mode": mode,
            "detection": follow["action"],
            "detail": follow["detail"],
            "motor_action": actual["action"],
            "linear": round(actual["v"], 3),
            "angular": round(actual["w"], 3),
        }

# ===== web page =====
def page():
    btn = 'style="font-size:16px;padding:6px 14px;margin:3px"'
    pats = "".join(f'<button {btn} onclick="pat(\'{k}\')">{k}: {n}</button>'
                   for k, (n, _) in PATTERNS.items())
    meows = "".join(f'<button {btn} onclick="meow(\'{k}\')">🐱 {k.upper()}: {n}</button>'
                    for k, (n, _, _) in MEOWS.items())
    files = "".join(f'<button {btn} onclick="snd(\'{quote(f)}\')">🔊 {f}</button>'
                    for f in sound_files()) or f"<i>no files in {SOUND_DIR}</i>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Robot</title></head>
<body style="background:#111;color:#eee;font-family:sans-serif;text-align:center">
<h2 style="color:#8fdfac">RASPBERRY PI DRY RUN — NO REAL ROBOT MOVEMENT</h2>
 <h3>WASD = manual drive · Arrows = simulated camera servo · M, 6-0 = meows · SPACE = LATCH STOP</h3>
 <p><button onclick="setMode('MANUAL')">MANUAL</button> <button onclick="setMode('AUTO')">AUTO FOLLOW</button> <button style="background:#e67c7c" onclick="setMode('STOPPED')">STOP</button></p>
 <p id="drive_state">Mode: MANUAL | Motor: STOP</p>
 <p style="font-size:12px;color:#ffc86e">SIM ONLY: box size is NOT a real distance measurement. No physical robot movement.</p>
<img src="/video" style="max-width:95vw;border:1px solid #444">
<p><button id="hb" style="font-size:20px;padding:8px 24px">📢 Horn (hold)</button></p>
<p>Buzzer: {pats}</p>
<p>Meow: {meows}</p>
<p>Sound files: {files}</p>
<p id="s">keys: -</p>
<script>
const k = new Set();
const hb = document.getElementById("hb");
hb.onmousedown = hb.ontouchstart = () => k.add("h");
hb.onmouseup = hb.onmouseleave = hb.ontouchend = () => k.delete("h");
function pat(p) {{ fetch("/pattern?p=" + p).catch(() => {{}}); }}
function snd(f) {{ fetch("/play?f=" + f).catch(() => {{}}); }}
function meow(m) {{ fetch("/meow?m=" + m).catch(() => {{}}); }}
function setMode(m) {{ k.clear(); fetch("/mode?value=" + encodeURIComponent(m)).catch(() => {{}}); }}
async function refreshStatus() {{
  try {{
    const r = await fetch("/status");
    const x = await r.json();
    document.getElementById("drive_state").textContent =
      "Mode: " + x.mode + " | Motor: " + x.motor_action +
      " | v=" + x.linear.toFixed(2) + " w=" + x.angular.toFixed(2) +
      " | Vision: " + x.detection;
  }} catch(e) {{ document.getElementById("drive_state").textContent = "Status disconnected"; }}
}}
setInterval(refreshStatus, 200);
const AR = {{arrowup: "i", arrowdown: "k", arrowleft: "j", arrowright: "l"}};
document.onkeyup = e => {{ const c = e.key.toLowerCase(); k.delete(AR[c] || c); }};
document.onkeydown = e => {{ const c = e.key.toLowerCase();
  if (AR[c]) {{ e.preventDefault(); k.add(AR[c]); return; }}
  if (c === "c" && !e.repeat) fetch("/center").catch(() => {{}});
  if (c.length === 1 && "wasdh".includes(c)) k.add(c);
  if ("12345".includes(c) && !e.repeat) pat(c);
  if ("m67890".includes(c) && c.length === 1 && !e.repeat) meow(c);
  if (c === " ") {{ e.preventDefault(); setMode("STOPPED"); }} }};
window.onblur = () => k.clear();
setInterval(() => {{ const s = [...k].join("");
  document.getElementById("s").textContent = "keys: " + (s || "-");
  fetch("/cmd?k=" + s).catch(() => {{}}); }}, 100);
</script></body></html>"""

camera = None
motor = None

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            self.reply(200, "text/html; charset=utf-8", page().encode())
        elif u.path == "/cmd":
            set_keys(q.get("k", [""])[0])
            self.reply(200, "text/plain", b"ok")
        elif u.path == "/mode":
            requested = q.get("value", [""])[0]
            if set_mode(requested):
                self.reply(200, "text/plain", b"ok")
            else:
                self.reply(400, "text/plain", b"invalid mode")
        elif u.path == "/status":
            self.reply(200, "application/json", json.dumps(get_status()).encode())
        elif u.path == "/pattern":
            play_pattern(motor, q.get("p", [""])[0])
            self.reply(200, "text/plain", b"ok")
        elif u.path == "/center":
            center_req.set()
            self.reply(200, "text/plain", b"ok")
        elif u.path == "/meow":
            play_meow(q.get("m", [""])[0])
            self.reply(200, "text/plain", b"ok")
        elif u.path == "/play":
            play_file(q.get("f", [""])[0])
            self.reply(200, "text/plain", b"ok")
        elif u.path == "/video":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    f = camera.jpeg
                    if f:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                         + str(len(f)).encode() + b"\r\n\r\n" + f + b"\r\n")
                    time.sleep(1 / 20)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.reply(404, "text/plain", b"not found")

def main():
    global camera, motor
    motor = Motor()
    camera = Camera()
    for k in MEOWS:                      # pre-build meow sounds so they play instantly
        make_meow(k)
    threading.Thread(target=control_loop, args=(motor,), daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    print("Sound output:", audio_device() or "default (no USB speaker found - is the voice module plugged in?)")
    print(f"Sound files in {SOUND_DIR}:", sound_files() or "none")
    print(f"Open http://<ROBOT_IP>:{PORT} in your browser (Ctrl+C to quit)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        motor.send(0, 0)
        motor.beep(False)
        camera.close()
        server.server_close()
        print("Stopped.")

if __name__ == "__main__":
    main()