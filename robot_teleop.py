#!/usr/bin/env python3
"""
WASD drive + live camera + sounds over WiFi.
Run ON THE ROBOT:   python3 robot_teleop.py
Open ON YOUR PC:    http://<robot-ip>:8080
Needs only OpenCV (no Flask). Robot stops automatically if commands stop arriving.

Sounds:
  H (hold)      = horn on the robot's buzzer
  1-5           = buzzer patterns (edit PATTERNS below to make your own)
  Sound files   = put .wav / .mp3 in ~/sounds on the robot; they show up as buttons
                  (needs a USB/Bluetooth speaker on the robot; mp3 needs: sudo apt install mpg123)
"""
import math, os, subprocess, tempfile, threading, time, wave, cv2
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

# ===== settings =====
PORT     = 8080
CAM_ID   = 0        # try 1 or 2 if no image
LIN      = 0.3      # forward speed (m/s)
ANG      = 1.0      # turn speed (rad/s)
TIMEOUT  = 0.5      # stop if no command for this many seconds
BACKEND  = "auto"   # "auto" | "ros2" | "lib"
BUZZER_TOPIC = "/Buzzer"   # ROS2 buzzer topic (std_msgs/Bool) on Yahboom robots
SOUND_DIR = os.path.expanduser("~/sounds")
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

# ===== motor + buzzer backend =====
class Motor:
    def __init__(self):
        self.mode = None
        if BACKEND in ("auto", "ros2"):
            try:
                import rclpy
                from geometry_msgs.msg import Twist
                from std_msgs.msg import Bool
                rclpy.init()
                self.node = rclpy.create_node("wasd_web")
                self.pub = self.node.create_publisher(Twist, "/cmd_vel", 10)
                self.buzz_pub = self.node.create_publisher(Bool, BUZZER_TOPIC, 10)
                self.Twist, self.Bool = Twist, Bool
                self.mode = "ros2"
            except Exception as e:
                if BACKEND == "ros2":
                    raise
                print("ROS2 not available:", e)
        if self.mode is None:
            from Rosmaster_Lib import Rosmaster
            self.bot = Rosmaster()
            self.bot.create_receive_threading()
            self.mode = "lib"
        print("Motor backend:", self.mode)

    def send(self, v, w):
        if self.mode == "ros2":
            t = self.Twist()
            t.linear.x, t.angular.z = float(v), float(w)
            self.pub.publish(t)
        else:
            self.bot.set_car_motion(v, 0, w)

    def servo(self, sid, angle):
        try:
            if self.mode == "lib":
                self.bot.set_pwm_servo(sid, int(angle))
            # ROS2 mode: gimbal not supported here, set BACKEND = "lib"
        except Exception as e:
            print("Servo error:", e)

    def beep(self, on):
        try:
            if self.mode == "ros2":
                self.buzz_pub.publish(self.Bool(data=bool(on)))
            else:
                self.bot.set_beep(1 if on else 0)   # 1 = continuous, 0 = off
        except Exception as e:
            print("Buzzer error:", e)

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
    """Return ALSA device of the first USB sound card, else None (system default)."""
    if AUDIO_DEV != "auto":
        return AUDIO_DEV
    try:
        out = subprocess.run(["aplay", "-l"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.startswith("card ") and "usb" in line.lower():
                return f"plughw:{line.split()[1].rstrip(':')},0"
    except FileNotFoundError:
        pass
    return None

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
    global player
    name = os.path.basename(path)
    if player and player.poll() is None:
        player.terminate()
    dev = audio_device()
    if name.lower().endswith(".wav"):
        cmd = ["aplay", "-q"] + (["-D", dev] if dev else []) + [path]
    else:
        cmd = ["mpg123", "-q"] + (["-o", "alsa", "-a", dev] if dev else []) + [path]
    print(f"Playing {name} on {dev or 'default device'}")
    try:
        player = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print(f"Install the player first: sudo apt install {'alsa-utils' if cmd[0] == 'aplay' else 'mpg123'}")

# ===== camera =====
class Camera:
    def __init__(self):
        self.jpeg = None
        self.cap = cv2.VideoCapture(CAM_ID)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        if not self.cap.isOpened():
            print(f"WARNING: camera {CAM_ID} not opened (busy or wrong ID)")
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.1)
                continue
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                self.jpeg = buf.tobytes()

# ===== control state + watchdog =====
cmd = [0.0, 0.0, False, 0, 0]   # v, w, horn, pan dir, tilt dir
last = 0.0
center_req = threading.Event()
lock = threading.Lock()

def set_keys(keys):
    global last
    v = LIN * (("w" in keys) - ("s" in keys))
    w = ANG * (("a" in keys) - ("d" in keys))
    pan  = ("j" in keys) - ("l" in keys)   # j = ArrowLeft, l = ArrowRight
    tilt = ("i" in keys) - ("k" in keys)   # i = ArrowUp,   k = ArrowDown
    with lock:
        cmd[:] = [v, w, ("h" in keys), pan, tilt]
        last = time.time()

def clamp(x, lo_hi):
    return max(lo_hi[0], min(lo_hi[1], x))

def control_loop(motor):
    horn_on = False
    pan, tilt = PAN_CENTER, TILT_CENTER
    motor.servo(PAN_ID, pan); motor.servo(TILT_ID, tilt)
    while True:
        with lock:
            if time.time() - last > TIMEOUT:
                cmd[:] = [0.0, 0.0, False, 0, 0]
            v, w, horn, dp, dt = cmd
        motor.send(v, w)
        if center_req.is_set():
            center_req.clear()
            dp = dt = 0
            pan, tilt = PAN_CENTER, TILT_CENTER
            motor.servo(PAN_ID, pan); motor.servo(TILT_ID, tilt)
        if dp:
            new = clamp(pan + dp * SERVO_STEP * (-1 if PAN_INVERT else 1), PAN_RANGE)
            if new != pan:
                pan = new; motor.servo(PAN_ID, pan)
        if dt:
            new = clamp(tilt + dt * SERVO_STEP * (-1 if TILT_INVERT else 1), TILT_RANGE)
            if new != tilt:
                tilt = new; motor.servo(TILT_ID, tilt)
        if not pattern_busy.is_set() and horn != horn_on:   # don't fight a pattern
            motor.beep(horn)
            horn_on = horn
        time.sleep(0.05)

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
<h3>W A S D = drive · Arrows = camera · C = center camera · H = horn · 1-5 = beeps · M, 6-0 = meows · Space = stop</h3>
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
const AR = {{arrowup: "i", arrowdown: "k", arrowleft: "j", arrowright: "l"}};
document.onkeyup = e => {{ const c = e.key.toLowerCase(); k.delete(AR[c] || c); }};
document.onkeydown = e => {{ const c = e.key.toLowerCase();
  if (AR[c]) {{ e.preventDefault(); k.add(AR[c]); return; }}
  if (c === "c" && !e.repeat) fetch("/center").catch(() => {{}});
  if (c.length === 1 && "wasdh".includes(c)) k.add(c);
  if ("12345".includes(c) && !e.repeat) pat(c);
  if ("m67890".includes(c) && c.length === 1 && !e.repeat) meow(c);
  if (c === " ") k.clear(); }};
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
    print(f"Open http://<robot-ip>:{PORT} on your PC  (Ctrl+C to quit)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        motor.send(0, 0)
        motor.beep(False)
        if player and player.poll() is None:
            player.terminate()
        print("Stopped.")

if __name__ == "__main__":
    main()