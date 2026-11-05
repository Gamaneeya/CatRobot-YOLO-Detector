
#!/usr/bin/env python3

import html
import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
import wave

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import cv2
import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "best.pt"

ENABLE_REAL_MOTOR = False
ENABLE_AUTO_FOLLOW = False
MANUAL_LIDAR_REQUIRED = False

YOLO_CONF = 0.10
TRACK_CONF = 0.60
GREEN_CONF = 0.60
CONFIRM_FRAMES = 3
IMG_SIZE = 640

FOLLOW_LEFT = 0.42
FOLLOW_RIGHT = 0.58
SIM_STOP_AREA_RATIO = 0.22
SIM_FORWARD_SPEED = 0.08
SIM_TURN_SPEED = 0.25
MAX_AUTO_AGE = 0.50

PORT = 8080
CAM_ID = 0
LIN = 0.08
ANG = 0.25
TIMEOUT = 0.50

SOUND_DIR = str(ROOT / "sounds")
AUDIO_DEV = "default"

PAN_ID = 1
TILT_ID = 2
PAN_RANGE = (0, 180)
TILT_RANGE = (40, 140)
PAN_CENTER = 90
TILT_CENTER = 90
SERVO_STEP = 3
PAN_INVERT = False
TILT_INVERT = False

PATTERNS = {
    "1": ("Short beep", [(100, 0)]),
    "2": ("Double beep", [(100, 100), (100, 0)]),
    "3": ("Long beep", [(800, 0)]),
    "4": ("Reverse", [(300, 300)] * 3),
    "5": ("SOS", [(100, 100)] * 3 + [(400, 100)] * 3 + [(100, 100)] * 3)
}

MEOWS = {
    "m": ("Meow", 1.0, 1.0),
    "6": ("High meow", 1.6, 1.0),
    "7": ("Short meow", 1.0, 0.45),
    "8": ("Long meow", 1.0, 2.2),
    "9": ("High long meow", 1.6, 2.2),
    "0": ("High short meow", 1.6, 0.45)
}

MEOW_VOLUME = 0.65
SAMPLE_RATE = 22050
MEOW_DIR = tempfile.mkdtemp(prefix="m1_meow_")

cmd = [0.0, 0.0, False, 0, 0]
last = 0.0
mode = "STOPPED"

follow = {
    "v": 0.0,
    "w": 0.0,
    "action": "WAITING FOR CAMERA",
    "detail": "",
    "at": 0.0
}

actual = {
    "v": 0.0,
    "w": 0.0,
    "action": "STOP"
}

lock = threading.Lock()
center_req = threading.Event()
pattern_busy = threading.Event()

camera = None
motor = None


def lidar_clear_for_motion():
    return False


class Motor:
    def __init__(self):
        from Rosmaster_Lib import Rosmaster

        self.bot = Rosmaster()
        self.bot.create_receive_threading()
        self.io_lock = threading.Lock()
        self.last_drive = None

        with self.io_lock:
            self.bot.set_car_motion(0, 0, 0)

        print("Motor backend: ROSMASTER")
        print("Real motor enabled:", ENABLE_REAL_MOTOR)
        print("Auto follow enabled:", ENABLE_AUTO_FOLLOW)
        print("LiDAR safety: NOT INTEGRATED")

    def send(self, v, w, expected_mode=None):
        v = max(-0.08, min(0.08, float(v)))
        w = max(-0.25, min(0.25, float(w)))

        with self.io_lock:
            with lock:
                active_mode = mode
                now = time.monotonic()

                heartbeat_ok = now - last <= TIMEOUT
                detection_ok = (
                    now - follow["at"] <= MAX_AUTO_AGE
                )

                allowed = (
                    ENABLE_REAL_MOTOR
                    and active_mode in ("MANUAL", "AUTO")
                    and heartbeat_ok
                    and (
                        expected_mode is None
                        or expected_mode == active_mode
                    )
                )

                if allowed and active_mode == "AUTO":
                    allowed = (
                        ENABLE_AUTO_FOLLOW
                        and detection_ok
                        and lidar_clear_for_motion()
                    )

                elif (
                    allowed
                    and active_mode == "MANUAL"
                    and MANUAL_LIDAR_REQUIRED
                ):
                    allowed = lidar_clear_for_motion()

                if not allowed:
                    v = 0.0
                    w = 0.0

                self.bot.set_car_motion(v, 0, w)

        drive = (round(v, 3), round(w, 3))

        if drive != self.last_drive:
            print(
                f"[ROSMASTER MOTOR] "
                f"linear={v:+.3f} angular={w:+.3f}"
            )
            self.last_drive = drive

        return v, w

    def servo(self, sid, angle):
        print(
            f"[SERVO DISABLED] id={sid} angle={angle}"
        )

    def beep(self, on):
        self.bot.set_beep(1 if on else 0)


def play_pattern(motor_instance, key):
    if key not in PATTERNS or pattern_busy.is_set():
        return

    def run():
        pattern_busy.set()

        try:
            for on_ms, off_ms in PATTERNS[key][1]:
                motor_instance.beep(True)
                time.sleep(on_ms / 1000)
                motor_instance.beep(False)
                time.sleep(off_ms / 1000)
        finally:
            motor_instance.beep(False)
            pattern_busy.clear()

    threading.Thread(target=run, daemon=True).start()


def sound_files():
    if not os.path.isdir(SOUND_DIR):
        return []

    return sorted(
        f for f in os.listdir(SOUND_DIR)
        if f.lower().endswith((".wav", ".mp3"))
    )


def audio_device():
    return AUDIO_DEV


def _meow_samples(start_hz, end_hz, duration, volume):
    count = int(SAMPLE_RATE * duration)
    fade = min(0.08, duration / 3)
    out = bytearray()
    phase = 0.0

    for i in range(count):
        t = i / SAMPLE_RATE

        freq = start_hz + (
            end_hz - start_hz
        ) * (i / max(1, count - 1))

        phase += 2 * math.pi * freq / SAMPLE_RATE

        env = max(
            0.0,
            min(
                1.0,
                t / 0.035,
                (duration - t) / fade
            )
        )

        sample = (
            math.sin(phase)
            + 0.45 * math.sin(2 * phase)
            + 0.20 * math.sin(3 * phase)
        )

        sample *= env * volume / 1.65

        out += int(
            max(-1.0, min(1.0, sample)) * 32767
        ).to_bytes(2, "little", signed=True)

    return out


def make_meow(key):
    path = os.path.join(
        MEOW_DIR,
        f"meow_{key}.wav"
    )

    if not os.path.exists(path):
        _, pitch, length = MEOWS[key]

        gap = bytes(
            2 * int(SAMPLE_RATE * 0.12)
        )

        audio = (
            _meow_samples(
                520 * pitch,
                330 * pitch,
                0.38 * length,
                MEOW_VOLUME
            )
            + gap
            + _meow_samples(
                470 * pitch,
                280 * pitch,
                0.42 * length,
                MEOW_VOLUME
            )
        )

        with wave.open(path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(audio)

    return path


def play_path(path):
    path = str(path)

    if not os.path.isfile(path):
        print("Audio file not found:", path)
        return

    if path.lower().endswith(".wav"):
        if not shutil.which("aplay"):
            print("Audio error: aplay not installed")
            return

        command = ["aplay", "-q"]

        if AUDIO_DEV != "default":
            command += ["-D", AUDIO_DEV]

        command.append(path)

    elif path.lower().endswith(".mp3"):
        if not shutil.which("mpg123"):
            print("Audio error: mpg123 not installed")
            return

        command = ["mpg123", "-q", path]

    else:
        return

    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print("[PI AUDIO] Playing:", os.path.basename(path))

    except Exception as exc:
        print("[PI AUDIO ERROR]", exc)


def play_meow(key):
    if key in MEOWS:
        play_path(make_meow(key))


def play_file(name):
    if name in sound_files():
        play_path(os.path.join(SOUND_DIR, name))


def simulate_follow(cx, area_ratio):
    if not (
        math.isfinite(cx)
        and math.isfinite(area_ratio)
        and 0 <= cx <= 1
        and 0 <= area_ratio <= 1
    ):
        return 0.0, 0.0, "INVALID TARGET - STOP"

    if area_ratio >= SIM_STOP_AREA_RATIO:
        return 0.0, 0.0, "BOX SIZE LIMIT - STOP"

    if cx < FOLLOW_LEFT:
        return 0.0, SIM_TURN_SPEED, "TURN LEFT"

    if cx > FOLLOW_RIGHT:
        return 0.0, -SIM_TURN_SPEED, "TURN RIGHT"

    return SIM_FORWARD_SPEED, 0.0, "FORWARD REQUESTED"


def publish_follow(v, w, action, detail):
    with lock:
        follow.update(
            v=float(v),
            w=float(w),
            action=action,
            detail=detail,
            at=time.monotonic()
        )


def set_mode(new_mode):
    global mode, last

    if new_mode not in ("MANUAL", "AUTO", "STOPPED"):
        return False, "INVALID MODE"

    if new_mode == "AUTO":
        if not ENABLE_REAL_MOTOR:
            return False, "AUTO BLOCKED: MOTOR LOCKED"

        if not ENABLE_AUTO_FOLLOW:
            return False, "AUTO BLOCKED: NOT ENABLED"

        if not lidar_clear_for_motion():
            return False, "AUTO BLOCKED: LIDAR NOT READY"

    if (
        new_mode == "MANUAL"
        and MANUAL_LIDAR_REQUIRED
        and not lidar_clear_for_motion()
    ):
        return False, "MANUAL BLOCKED: LIDAR NOT READY"

    with lock:
        mode = new_mode
        cmd[:] = [0.0, 0.0, False, 0, 0]
        last = 0.0

        actual.update(
            v=0.0,
            w=0.0,
            action="STOP"
        )

    if new_mode == "STOPPED" and motor is not None:
        motor.send(0.0, 0.0)

    print("[MODE]", new_mode)

    return True, "OK"


def set_keys(keys):
    global last

    with lock:
        if mode == "STOPPED":
            return

        v = LIN * (
            ("w" in keys) - ("s" in keys)
        )

        w = ANG * (
            ("a" in keys) - ("d" in keys)
        )

        pan = (
            ("j" in keys) - ("l" in keys)
        )

        tilt = (
            ("i" in keys) - ("k" in keys)
        )

        if mode == "AUTO":
            v = 0.0
            w = 0.0

        cmd[:] = [
            v,
            w,
            "h" in keys,
            pan,
            tilt
        ]

        last = time.monotonic()


def clamp(value, bounds):
    return max(
        bounds[0],
        min(bounds[1], value)
    )


class Camera:
    def __init__(self):
        self.jpeg = None
        self.running = True
        self.verified_frames = 0

        if not MODEL_PATH.is_file():
            raise FileNotFoundError(
                f"Model not found: {MODEL_PATH}"
            )

        self.model = YOLO(str(MODEL_PATH))

        print("YOLO model:", MODEL_PATH)
        print("YOLO classes:", self.model.names)

        if self.model.names != {0: "green_dino"}:
            raise RuntimeError(
                "Unexpected YOLO classes"
            )

        self.cap = cv2.VideoCapture(CAM_ID)

        if not self.cap.isOpened():
            raise RuntimeError(
                f"Cannot open camera {CAM_ID}"
            )

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print("Camera opened:", CAM_ID)

        self.thread = threading.Thread(
            target=self.loop,
            daemon=True
        )

        self.thread.start()

    def loop(self):
        prev_time = time.monotonic()

        while self.running:
            try:
                ok, frame = self.cap.read()

                if not ok or frame is None:
                    self.verified_frames = 0

                    publish_follow(
                        0, 0,
                        "CAMERA LOST - STOP",
                        "Camera read failed"
                    )

                    blank = np.zeros(
                        (480, 640, 3),
                        dtype=np.uint8
                    )

                    cv2.putText(
                        blank,
                        "CAMERA LOST - STOP",
                        (20, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (255, 255, 255),
                        2
                    )

                    self.encode(blank)
                    time.sleep(0.1)
                    continue

                try:
                    result = self.model.predict(
                        source=frame,
                        conf=YOLO_CONF,
                        iou=0.45,
                        imgsz=IMG_SIZE,
                        max_det=10,
                        verbose=False
                    )[0]

                except Exception as exc:
                    print("YOLO inference error:", exc)

                    self.verified_frames = 0

                    publish_follow(
                        0, 0,
                        "YOLO ERROR - STOP",
                        str(exc)
                    )

                    self.encode(frame)
                    time.sleep(0.1)
                    continue

                height, width = frame.shape[:2]

                candidates = list(result.boxes)

                allowed = [
                    box for box in candidates
                    if (
                        int(box.cls[0]) == 0
                        and float(box.conf[0]) >= TRACK_CONF
                    )
                ]

                target = (
                    max(
                        allowed,
                        key=lambda box: float(box.conf[0])
                    )
                    if allowed
                    else None
                )

                for box in candidates:
                    confidence = float(box.conf[0])

                    x1, y1, x2, y2 = map(
                        int,
                        box.xyxy[0].tolist()
                    )

                    color = (
                        (0, 255, 0)
                        if confidence >= GREEN_CONF
                        else (0, 165, 255)
                    )

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        color,
                        2
                    )

                    cv2.putText(
                        frame,
                        f"Dino? {confidence:.2f}",
                        (x1, max(18, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        color,
                        2
                    )

                if target is not None:
                    self.verified_frames = min(
                        self.verified_frames + 1,
                        CONFIRM_FRAMES
                    )

                    x1, y1, x2, y2 = (
                        target.xyxy[0].tolist()
                    )

                    cx = ((x1 + x2) / 2) / width

                    area = (
                        max(0.0, x2 - x1)
                        * max(0.0, y2 - y1)
                        / (width * height)
                    )

                    confidence = float(
                        target.conf[0]
                    )

                    detail = (
                        f"X: {cx:.2f} | "
                        f"Box area: {area:.1%} | "
                        f"Conf: {confidence:.2f}"
                    )

                    if self.verified_frames < CONFIRM_FRAMES:
                        v, turn, action = (
                            0.0,
                            0.0,
                            "VERIFYING TARGET - STOP"
                        )
                    else:
                        v, turn, action = simulate_follow(
                            cx,
                            area
                        )

                else:
                    self.verified_frames = 0
                    v = 0.0
                    turn = 0.0

                    if candidates:
                        action = "LOW CONFIDENCE - STOP"
                        detail = (
                            f"Needs confidence "
                            f">= {TRACK_CONF:.2f}"
                        )
                    else:
                        action = "NO TARGET - STOP"
                        detail = "No Dino detected"

                publish_follow(
                    v,
                    turn,
                    action,
                    detail
                )

                now = time.monotonic()

                fps = 1.0 / max(
                    now - prev_time,
                    1e-6
                )

                prev_time = now

                with lock:
                    active_mode = mode

                cv2.putText(
                    frame,
                    f"ROSMASTER M1 | MODE: {active_mode}",
                    (12, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    (255, 255, 255),
                    2
                )

                cv2.putText(
                    frame,
                    action,
                    (12, 52),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.67,
                    (0, 255, 255),
                    2
                )

                cv2.putText(
                    frame,
                    f"{detail} | FPS: {fps:.1f}",
                    (12, 78),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (255, 255, 255),
                    2
                )

                self.encode(frame)

            except Exception as exc:
                print("[CAMERA LOOP ERROR]", exc)

                self.verified_frames = 0

                publish_follow(
                    0, 0,
                    "CAMERA ERROR - STOP",
                    str(exc)
                )

                time.sleep(0.1)

    def encode(self, frame):
        ok, buffer = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, 70]
        )

        if ok:
            self.jpeg = buffer.tobytes()

    def close(self):
        self.running = False

        if hasattr(self, "thread"):
            self.thread.join(timeout=2)

        self.cap.release()


def control_loop(motor_instance):
    global mode

    horn_on = False
    pan = PAN_CENTER
    tilt = TILT_CENTER

    motor_instance.servo(PAN_ID, pan)
    motor_instance.servo(TILT_ID, tilt)

    while True:
        try:
            with lock:
                heartbeat_ok = (
                    time.monotonic() - last <= TIMEOUT
                )

                if not heartbeat_ok:
                    cmd[:] = [
                        0.0, 0.0, False, 0, 0
                    ]

                manual_v, manual_w, horn, dp, dt = cmd
                active_mode = mode

                if active_mode == "AUTO":
                    if not heartbeat_ok:
                        v = 0.0
                        w = 0.0
                        action = "WEB LOST - STOP"

                    elif (
                        time.monotonic() - follow["at"]
                        > MAX_AUTO_AGE
                    ):
                        v = 0.0
                        w = 0.0
                        action = "STALE DETECTION - STOP"

                    else:
                        v = follow["v"]
                        w = follow["w"]
                        action = follow["action"]

                elif active_mode == "MANUAL":
                    v = manual_v
                    w = manual_w
                    action = (
                        "MANUAL COMMAND"
                        if heartbeat_ok
                        else "WEB LOST - STOP"
                    )

                else:
                    v = 0.0
                    w = 0.0
                    action = "STOP LATCHED"
                    horn = False
                    dp = 0
                    dt = 0

            actual_v, actual_w = motor_instance.send(
                v,
                w,
                expected_mode=active_mode
            )

            if not ENABLE_REAL_MOTOR:
                action = "MOTOR LOCKED - STOP"

            elif active_mode == "AUTO":
                if (
                    not ENABLE_AUTO_FOLLOW
                    or not lidar_clear_for_motion()
                ):
                    action = "AUTO SAFETY BLOCK - STOP"

            elif (
                active_mode == "MANUAL"
                and MANUAL_LIDAR_REQUIRED
                and not lidar_clear_for_motion()
            ):
                action = "MANUAL LIDAR BLOCK - STOP"

            with lock:
                if mode == "STOPPED":
                    actual.update(
                        v=0.0,
                        w=0.0,
                        action="STOP LATCHED"
                    )
                else:
                    actual.update(
                        v=actual_v,
                        w=actual_w,
                        action=action
                    )

            if (
                center_req.is_set()
                and active_mode != "STOPPED"
            ):
                center_req.clear()

                dp = 0
                dt = 0
                pan = PAN_CENTER
                tilt = TILT_CENTER

                motor_instance.servo(PAN_ID, pan)
                motor_instance.servo(TILT_ID, tilt)

            if dp:
                new_pan = clamp(
                    pan
                    + dp
                    * SERVO_STEP
                    * (-1 if PAN_INVERT else 1),
                    PAN_RANGE
                )

                if new_pan != pan:
                    pan = new_pan
                    motor_instance.servo(
                        PAN_ID,
                        pan
                    )

            if dt:
                new_tilt = clamp(
                    tilt
                    + dt
                    * SERVO_STEP
                    * (-1 if TILT_INVERT else 1),
                    TILT_RANGE
                )

                if new_tilt != tilt:
                    tilt = new_tilt
                    motor_instance.servo(
                        TILT_ID,
                        tilt
                    )

            if (
                not pattern_busy.is_set()
                and horn != horn_on
            ):
                motor_instance.beep(horn)
                horn_on = horn

        except Exception as exc:
            print("[CONTROL ERROR]", exc)

            with lock:
                mode = "STOPPED"

                actual.update(
                    v=0.0,
                    w=0.0,
                    action="CONTROL ERROR - STOP"
                )

            try:
                motor_instance.send(0.0, 0.0)
            except Exception as stop_error:
                print(
                    "[MOTOR STOP FAILED]",
                    stop_error
                )

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
            "motor_enabled": ENABLE_REAL_MOTOR,
            "auto_enabled": ENABLE_AUTO_FOLLOW,
            "lidar_ready": lidar_clear_for_motion()
        }


def page():
    button_style = (
        'style="font-size:16px;'
        'padding:6px 14px;margin:3px"'
    )

    patterns = "".join(
        f'<button {button_style} '
        f'onclick="pat(\'{key}\')">'
        f'{key}: {name}</button>'
        for key, (name, _) in PATTERNS.items()
    )

    meows = "".join(
        f'<button {button_style} '
        f'onclick="meow(\'{key}\')">'
        f'🐱 {key.upper()}: {name}</button>'
        for key, (name, _, _) in MEOWS.items()
    )

    files = "".join(
        f'<button {button_style} '
        f'onclick="snd(\'{quote(name, safe="")}\')">'
        f'🔊 {html.escape(name)}</button>'
        for name in sound_files()
    )

    if not files:
        files = "<i>No sound files found</i>"

    content = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ROSMASTER M1 - Green Dino</title>
</head>

<body style="background:#111;color:#eee;font-family:sans-serif;text-align:center">

<h2 style="color:#8fdfac">
ROSMASTER M1 — YOLO GREEN DINO V7.2
</h2>

<h3>
WASD = Manual Drive |
Arrows = Camera Servo (Disabled) |
M, 6-0 = Meows |
SPACE = STOP
</h3>

<p style="color:#ffc86e">
REAL MOTOR LOCKED BY DEFAULT.
AUTO FOLLOW REQUIRES VERIFIED LiDAR SAFETY.
</p>

<img src="/video" style="max-width:95vw;border:1px solid #444">

<p>
<button onclick="setMode('MANUAL')">MANUAL</button>
<button onclick="setMode('AUTO')">AUTO FOLLOW</button>
<button style="background:#e67c7c" onclick="setMode('STOPPED')">STOP</button>
</p>

<p id="drive_state">Mode: STOPPED | Motor: STOP</p>
<p id="notice" style="color:#ffc86e"></p>

<p style="font-size:12px;color:#ffc86e">
Bounding box size is NOT a physical distance sensor.
</p>

<p>
<button id="hb" style="font-size:20px;padding:8px 24px">
📢 Horn (hold)
</button>
</p>

<p>Buzzer: __PATTERNS__</p>
<p>Meow: __MEOWS__</p>
<p>Sound files: __FILES__</p>

<p id="s">keys: -</p>

<script>
const k = new Set();
const hb = document.getElementById("hb");

hb.onmousedown = hb.ontouchstart = () => k.add("h");

hb.onmouseup = hb.onmouseleave = hb.ontouchend =
    () => k.delete("h");

function pat(p) {
    fetch("/pattern?p=" + p).catch(() => {});
}

function snd(f) {
    fetch("/play?f=" + f).catch(() => {});
}

function meow(m) {
    fetch("/meow?m=" + m).catch(() => {});
}

async function setMode(m) {
    k.clear();

    try {
        const response = await fetch(
            "/mode?value=" + encodeURIComponent(m)
        );

        const message = await response.text();

        document.getElementById("notice").textContent =
            response.ok ? "" : message;

    } catch (e) {
        document.getElementById("notice").textContent =
            "Connection failed";
    }
}

async function refreshStatus() {
    try {
        const response = await fetch("/status");
        const x = await response.json();

        document.getElementById("drive_state").textContent =
            "Mode: " + x.mode +
            " | Motor: " + x.motor_action +
            " | v=" + x.linear.toFixed(2) +
            " w=" + x.angular.toFixed(2) +
            " | Vision: " + x.detection +
            " | Real Motor: " +
            (x.motor_enabled ? "ENABLED" : "LOCKED") +
            " | LiDAR: " +
            (x.lidar_ready ? "READY" : "NOT READY");

    } catch (e) {
        document.getElementById("drive_state").textContent =
            "Status disconnected";
    }
}

setInterval(refreshStatus, 200);

const AR = {
    arrowup: "i",
    arrowdown: "k",
    arrowleft: "j",
    arrowright: "l"
};

document.onkeyup = e => {
    const c = e.key.toLowerCase();
    k.delete(AR[c] || c);
};

document.onkeydown = e => {
    const c = e.key.toLowerCase();

    if (AR[c]) {
        e.preventDefault();
        k.add(AR[c]);
        return;
    }

    if (c === "c" && !e.repeat) {
        fetch("/center").catch(() => {});
    }

    if (c.length === 1 && "wasdh".includes(c)) {
        k.add(c);
    }

    if ("12345".includes(c) && !e.repeat) {
        pat(c);
    }

    if ("m67890".includes(c) && !e.repeat) {
        meow(c);
    }

    if (c === " ") {
        e.preventDefault();
        setMode("STOPPED");
    }
};

window.onblur = () => k.clear();

setInterval(() => {
    const s = [...k].join("");

    document.getElementById("s").textContent =
        "keys: " + (s || "-");

    fetch("/cmd?k=" + s).catch(() => {});
}, 100);
</script>
</body>
</html>
"""

    return (
        content
        .replace("__PATTERNS__", patterns)
        .replace("__MEOWS__", meows)
        .replace("__FILES__", files)
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, content_type, body):
        self.send_response(status)
        self.send_header(
            "Content-Type",
            content_type
        )
        self.send_header(
            "Content-Length",
            str(len(body))
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        request = urlparse(self.path)
        query = parse_qs(request.query)

        if request.path == "/":
            self.reply(
                200,
                "text/html; charset=utf-8",
                page().encode("utf-8")
            )

        elif request.path == "/cmd":
            set_keys(query.get("k", [""])[0])

            self.reply(
                200,
                "text/plain",
                b"ok"
            )

        elif request.path == "/mode":
            requested = query.get("value", [""])[0]

            success, message = set_mode(requested)

            self.reply(
                200 if success else 409,
                "text/plain; charset=utf-8",
                message.encode("utf-8")
            )

        elif request.path == "/status":
            self.reply(
                200,
                "application/json",
                json.dumps(get_status()).encode()
            )

        elif request.path == "/pattern":
            play_pattern(
                motor,
                query.get("p", [""])[0]
            )

            self.reply(
                200,
                "text/plain",
                b"ok"
            )

        elif request.path == "/center":
            center_req.set()

            self.reply(
                200,
                "text/plain",
                b"ok"
            )

        elif request.path == "/meow":
            play_meow(
                query.get("m", [""])[0]
            )

            self.reply(
                200,
                "text/plain",
                b"ok"
            )

        elif request.path == "/play":
            play_file(
                query.get("f", [""])[0]
            )

            self.reply(
                200,
                "text/plain",
                b"ok"
            )

        elif request.path == "/video":
            self.send_response(200)

            self.send_header(
                "Content-Type",
                "multipart/x-mixed-replace; boundary=frame"
            )

            self.end_headers()

            try:
                while True:
                    frame = camera.jpeg

                    if frame:
                        self.wfile.write(
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"Content-Length: "
                            + str(len(frame)).encode()
                            + b"\r\n\r\n"
                            + frame
                            + b"\r\n"
                        )

                    time.sleep(1 / 20)

            except (
                BrokenPipeError,
                ConnectionResetError
            ):
                pass

        else:
            self.reply(
                404,
                "text/plain",
                b"not found"
            )


def main():
    global camera, motor

    server = None

    try:
        motor = Motor()
        camera = Camera()

        for key in MEOWS:
            make_meow(key)

        threading.Thread(
            target=control_loop,
            args=(motor,),
            daemon=True
        ).start()

        server = ThreadingHTTPServer(
            ("0.0.0.0", PORT),
            Handler
        )

        server.daemon_threads = True

        print("Sound device:", audio_device())
        print("Sound files:", sound_files() or "none")
        print("Real motor enabled:", ENABLE_REAL_MOTOR)
        print("Auto enabled:", ENABLE_AUTO_FOLLOW)
        print("LiDAR safety ready:", lidar_clear_for_motion())

        print(
            f"Open http://ROBOT_IP:{PORT} "
            "on your trusted local network"
        )

        server.serve_forever()

    except KeyboardInterrupt:
        print("Keyboard interrupt")

    finally:
        if motor is not None:
            try:
                set_mode("STOPPED")
                motor.send(0.0, 0.0)
                motor.beep(False)
            except Exception as exc:
                print("Motor shutdown error:", exc)

        if camera is not None:
            camera.close()

        if server is not None:
            server.server_close()

        print("Stopped.")


if __name__ == "__main__":
    main()
