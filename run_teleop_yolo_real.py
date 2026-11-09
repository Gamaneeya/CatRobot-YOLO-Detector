#!/usr/bin/env python3
"""Run the EXISTING robot_teleop_yolo_robot UI/camera/YOLO on real ROSMASTER M1.

Keeps the original web UI, keyboard events and sound callbacks unchanged.
Bridges motor, buzzer AND two-axis camera servo to ROS2 inside Docker,
uses the ORIGINAL friend teleop audio, and keeps LiDAR gating and main-thread YOLO.

Requires alongside it: robot_teleop_yolo_robot.py, dino_motion.py,
tmini_plus_lidar.py, models/best.pt.
"""

import argparse
import math
import os
import signal
import socket
import threading
import time
from lidar_directional_avoidance import (
    AvoidanceController, directional_permission, mode_ready, verified_dino,
)


def main():
    p = argparse.ArgumentParser(description='Real robot, original YOLO teleop web')
    p.add_argument('--mode', required=True, choices=('wheels-up', 'floor'))
    p.add_argument('--container', default='affectionate_lamport')
    p.add_argument('--ros-domain-id', type=int, default=62)
    p.add_argument('--lidar-port', default='/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0')
    p.add_argument('--front-angle', type=float, default=0.0)
    p.add_argument('--imgsz', type=int, default=320, choices=(320, 416, 640))
    p.add_argument('--confirm-wheels-up', action='store_true')
    p.add_argument('--confirm-wheels-tested', action='store_true')
    p.add_argument('--confirm-lidar-calibrated', action='store_true')
    p.add_argument('--confirm-emergency-stop', action='store_true')
    args = p.parse_args()
    lidar_22cm = os.environ.get('CATROBOT_LIDAR_22CM_TEST', '0') == '1'
    lidar_front40 = os.environ.get('CATROBOT_LIDAR_FRONT40_SIDE30', '0') == '1'
    lidar_front28 = os.environ.get('CATROBOT_LIDAR_FRONT28_SIDE26', '0') == '1'
    avoidance_on = os.environ.get('CATROBOT_AVOIDANCE_V1', '0') == '1'
    avoidance_v3 = os.environ.get('CATROBOT_AVOIDANCE_V3', '0') == '1'
    avoidance_v4 = os.environ.get('CATROBOT_AVOIDANCE_V4', '0') == '1'
    avoidance_v5 = os.environ.get('CATROBOT_AVOIDANCE_V5', '0') == '1'
    avoidance_v6 = os.environ.get('CATROBOT_AVOIDANCE_V6', '0') == '1'
    human_help = os.environ.get('CATROBOT_V6_ASSISTED_HELP', '0') == '1'
    speed_trial = os.environ.get('CATROBOT_SPEED_TRIAL', '0') == '1'
    stable_speed_08 = os.environ.get('CATROBOT_STABLE_SPEED_08', '0') == '1'
    bench_speed_015 = os.environ.get('CATROBOT_BENCH_SPEED_015', '0') == '1'
    orange_follow = os.environ.get('CATROBOT_ORANGE_FOLLOW_TRIAL', '0') == '1'
    close_meow_v4 = os.environ.get('CATROBOT_DINO_CLOSE_MEOW', '0') == '1'
    camera_stable = os.environ.get('CATROBOT_DINO_CAMERA_STABLE', '0') == '1'
    if avoidance_v5 and not avoidance_on:
        p.error('V5 requires CATROBOT_AVOIDANCE_V1=1')
    if (bench_speed_015 or orange_follow) and (not human_help or args.mode != 'wheels-up'):
        p.error('ORANGE FOLLOW and BENCH 0.15 are WHEELS-UP Assisted V6 ONLY')
    if bench_speed_015 and (stable_speed_08 or speed_trial):
        p.error('BENCH 0.15 conflicts with SPEED_08 or SPEED_TRIAL; use only one setting')
    if stable_speed_08 and (not human_help or args.mode != 'wheels-up' or speed_trial):
        p.error('STABLE_SPEED_08 requires assisted V6 in wheels-up mode, without SPEED_TRIAL')
    if human_help and (not avoidance_v6 or args.mode != 'wheels-up'):
        p.error('Assisted help requires V6 and wheels-up: no floor placement sensor exists')
    if avoidance_v6 and (not avoidance_on or not avoidance_v5 or args.mode != 'wheels-up'):
        p.error('V6 requires V1=1, V5=1 and WHEELS-UP; no floor navigation approval')
    if avoidance_v5 and args.mode != 'wheels-up':
        p.error('V5 remains WHEELS-UP ONLY')
    if speed_trial and (not avoidance_v5 or args.mode != 'wheels-up'):
        p.error('SPEED_TRIAL requires V5 and WHEELS-UP; never on floor')
    if avoidance_v5 and avoidance_v3:
        p.error('Choose V5 without V3')
    if avoidance_v4 and not avoidance_on:
        p.error('V4 requires CATROBOT_AVOIDANCE_V1=1 and 360 scan guard')
    if avoidance_v4 and args.mode != 'wheels-up':
        p.error('V4 is WHEELS-UP ONLY; floor navigation not validated')
    if avoidance_v3 and not avoidance_on:
        p.error('V3 requires CATROBOT_AVOIDANCE_V1=1 (keep existing motor safety)')
    if avoidance_v3 and args.mode != 'wheels-up':
        p.error('V3 is WHEELS-UP ONLY until live hardware checks are completed')
    if camera_stable and args.imgsz < 416:
        p.error('Camera stable trial requires --imgsz 416 or 640')
    avoidance_floor = os.environ.get('CATROBOT_AVOIDANCE_FLOOR_TESTED', '0') == '1'
    if avoidance_on and not (lidar_front28 and os.environ.get('CATROBOT_LIDAR_360_RADIUS_TEST', '0') == '1'):
        p.error('AVOIDANCE requires FRONT28_SIDE26=1 and 360_RADIUS_TEST=1')
    if avoidance_on and args.mode == 'floor' and not avoidance_floor:
        p.error('AVOIDANCE floor is LOCKED until wheel-up, rear sector and braking tests pass; do not set FLOOR_TESTED before physical verification')
    avoidance_engine = AvoidanceController() if avoidance_on else None
    if avoidance_v3:
        from dino_avoidance_v3 import BoundedAvoidanceV3
        avoidance_engine = BoundedAvoidanceV3()
    if avoidance_v4:
        from dino_avoidance_v4 import SafeRecoveryV4
        avoidance_engine = SafeRecoveryV4()
    if avoidance_v5:
        from dino_avoidance_v5 import SafeRecoveryV5
        avoidance_engine = SafeRecoveryV5()
    if avoidance_v6:
        from dino_avoidance_v6 import SafeRecoveryV6
        avoidance_engine = SafeRecoveryV6()
    if human_help:
        from dino_help_resume_v6 import HumanHelpV6
        avoidance_engine = HumanHelpV6()
    if lidar_front28 and (lidar_front40 or lidar_22cm):
        p.error('Choose ONE LiDAR profile: FRONT28_SIDE26, FRONT40_SIDE30, or 22CM_TEST')
    if lidar_front28 and os.environ.get('CATROBOT_LIDAR_360_RADIUS_TEST', '0') != '1':
        p.error('FRONT28_SIDE26 requires existing 360-degree 22cm emergency guard enabled')
    if lidar_front28 and args.mode == 'floor' and os.environ.get('CATROBOT_FRONT28_FLOOR_TEST_UNDERSTOOD', '0') != '1':
        p.error('Front28/Side26 FLOOR requires verified wheels-up and braking/scan tests first; CATROBOT_FRONT28_FLOOR_TEST_UNDERSTOOD=1 only after physical tests')
    if lidar_front40 and lidar_22cm:
        p.error('Choose ONE LiDAR profile: FRONT40_SIDE30 or 22CM_TEST')
    if lidar_front40 and args.mode == 'floor' and os.environ.get('CATROBOT_FRONT40_FLOOR_TEST_UNDERSTOOD', '0') != '1':
        p.error('Front 40cm / side 30cm FLOOR profile requires verified wheels-up, scan coverage and braking tests; acknowledge with CATROBOT_FRONT40_FLOOR_TEST_UNDERSTOOD=1')
    # A 22cm LiDAR reading may mean only 7cm to the nearest physical bumper.
    if lidar_22cm and args.mode == 'floor' and os.environ.get('CATROBOT_22CM_FLOOR_TEST_UNDERSTOOD', '0') != '1':
        p.error('Experimental 22cm floor stop requires completed wheel-up and braking tests; '
                'CATROBOT_22CM_FLOOR_TEST_UNDERSTOOD=1 acknowledges them.')
    print('[LIDAR TARGET] ' + ('FRONT 0.28m SIDE 0.26m' if lidar_front28 else ('FRONT 0.40m SIDE 0.30m' if lidar_front40 else ('EXPERIMENTAL 0.22m' if lidar_22cm else 'ORIGINAL LiDAR thresholds'))), flush=True)

    if args.mode == 'wheels-up' and not (args.confirm_wheels_up and args.confirm_emergency_stop):
        p.error('Lift all wheels and prepare physical power cutoff first.')
    if args.mode == 'floor' and not (
        args.confirm_wheels_tested and args.confirm_lidar_calibrated and args.confirm_emergency_stop
    ):
        p.error('Floor mode needs verified wheel stop, LiDAR calibration and power cutoff.')

    # Check old server before any ROS2 motor publisher or LiDAR reader starts.
    with socket.socket() as check:
        check.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            check.bind(('0.0.0.0', 8080))
        except OSError as exc:
            p.error(f'Port 8080 is busy. Stop the old CatRobot instance: {exc}')

    # These are the original application functions, web, keys, meows and box logic.
    import robot_teleop_yolo_robot as robot
    import robot_teleop as friend_teleop
    # Restore the sound behavior of the ORIGINAL friend's robot_teleop.py:
    # USB audio-card auto selection and ~/sounds WAV/MP3 button list.
    robot.make_meow = friend_teleop.make_meow
    robot.play_meow = friend_teleop.play_meow
    robot.play_file = friend_teleop.play_file
    robot.sound_files = friend_teleop.sound_files
    robot.audio_device = friend_teleop.audio_device
    # The Docker startup script initializes S1=90, S2=35. Do not abruptly
    # send 90/90 to the camera when the app starts. First verify movement
    # within conservative test ranges; expand only after physical calibration.
    robot.PAN_CENTER = 90
    robot.TILT_CENTER = 35
    robot.PAN_RANGE = (65, 115)
    robot.TILT_RANGE = (25, 65)
    from dino_motion import DockerMotor, IsolatedLidar
    import cv2
    import numpy as np
    import torch

    # Identical single-thread inference approach that passed 12/12 frames on Pi.
    torch.set_num_threads(1)
    cv2.setNumThreads(1)
    robot.IMG_SIZE = args.imgsz
    robot.SIM_FORWARD_SPEED = 0.150 if bench_speed_015 else (0.080 if stable_speed_08 else (0.085 if speed_trial else 0.070))
    if bench_speed_015:
        robot.LIN = 0.150
        print('[BENCH SPEED] WHEELS-UP ONLY: AUTO=0.150 m/s MANUAL=0.150 m/s; NEVER FLOOR', flush=True)
    if stable_speed_08:
        robot.LIN = 0.080
        print('[STABLE SPEED] WHEELS-UP ONLY: AUTO=0.080 m/s MANUAL=0.080 m/s (NOT 0.8 m/s)',flush=True)
    if speed_trial:
        robot.LIN = 0.080
        print('[SPEED TRIAL] WHEELS-UP ONLY: AUTO 0.085 m/s, MANUAL 0.080 m/s; no floor approval', flush=True)
    robot.SIM_TURN_SPEED = 0.19
    robot.FOLLOW_LEFT = 0.43
    robot.FOLLOW_RIGHT = 0.57
    robot.ENABLE_REAL_MOTOR = True
    robot.ENABLE_AUTO_FOLLOW = True
    robot.MANUAL_LIDAR_REQUIRED = True

    # Keep the ORIGINAL web page, including every old button and WASD.
    # Only add an explicit STOP request when the browser loses focus.
    original_page = robot.page

    def safe_original_page():
        html = original_page()
        old = 'window.onblur = () => k.clear();'
        new = ("window.onblur = () => { k.clear(); setMode('STOPPED'); };"
               "document.addEventListener('visibilitychange', () => {"
               "if(document.visibilityState !== 'visible'){k.clear();setMode('STOPPED');}"
               "});")
        if old not in html:
            raise RuntimeError('Original browser controls changed; STOP-on-blur patch cannot be verified')
        html = html.replace(old, new, 1)
        # Add an explicit read-only reason why MANUAL motion is blocked.
        marker = '<p id="notice" style="color:#ffc86e"></p>'
        if marker in html:
            html = html.replace(marker, marker + '<p id="drive_gate" style="color:#ffc86e;font-size:14px"></p>', 1)
            js_marker = '            (x.lidar_ready ? "READY" : "NOT READY");'
            if js_marker in html:
                html = html.replace(js_marker, js_marker +
                    '\n        document.getElementById("drive_gate").textContent = '
                    '"WASD gate: " + (x.manual_block_reason || "UNKNOWN");', 1)
            else:
                raise RuntimeError('Cannot find original LiDAR status display for diagnostic label')
        else:
            raise RuntimeError('Cannot find original notification label')
        return html.replace('Arrows = Camera Servo (Disabled)', 'Arrows = REAL Camera Servo (S1/S2)')

    robot.page = safe_original_page

    print('[VISION] Loading existing best.pt in MAIN thread', flush=True)
    model = robot.YOLO(str(robot.MODEL_PATH))
    if model.names != {0: 'green_dino'}:
        raise RuntimeError(f'Unexpected detection classes: {model.names!r}')
    model.predict(np.zeros((480, 640, 3), dtype=np.uint8), imgsz=args.imgsz, verbose=False)
    print('[VISION] YOLO warm-up OK', flush=True)

    class MainThreadCamera(robot.Camera):
        def __init__(self):
            self.jpeg = None
            self.running = True
            self.verified_frames = 0
            self.model = model
            self.cap = cv2.VideoCapture(robot.CAM_ID, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                raise RuntimeError('USB camera /dev/video0 did not open')
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print('[CAMERA] Existing YOLO camera loop will run in MAIN thread', flush=True)

    lidar = None
    backend = None
    server = None
    control_thread = None

    def get_scan():
        if lidar is None:
            return {'clear': False, 'reason': 'LIDAR NOT STARTED'}
        try:
            return lidar.snapshot()
        except Exception as exc:
            return {'clear': False, 'reason': f'LIDAR ERROR: {exc}'}

    def clear_for_mode():
        scan = get_scan()
        if avoidance_on:
            # Healthy LiDAR is required to enter MANUAL/AUTO. Obstacles do
            # not forbid MODE selection; RealMotor.send checks direction.
            return mode_ready(scan)
        if not scan.get('clear'):
            return False
        if args.mode == 'floor':
            # Additional floor guard, regardless of the user's wheel-up settings.
            for field, minimum in (
                ('front_min_m', 0.28 if lidar_front28 else (0.40 if lidar_front40 else (0.22 if lidar_22cm else 0.65))),
                ('left_min_m', 0.26 if lidar_front28 else (0.30 if lidar_front40 else (0.22 if lidar_22cm else 0.42))),
                ('right_min_m', 0.26 if lidar_front28 else (0.30 if lidar_front40 else (0.22 if lidar_22cm else 0.42))),
            ):
                value = scan.get(field)
                if value is None or value < minimum:
                    return False
        return True

    robot.lidar_clear_for_motion = clear_for_mode

    class RealMotor:
        def __init__(self, motor_backend):
            self.backend = motor_backend
            self.io_lock = threading.RLock()
            self.last_drive = None
            self.pan = robot.PAN_CENTER
            self.tilt = robot.TILT_CENTER
            self._servo_warning = False
            self.last_block_reason = 'MODE STOPPED'
            self.last_zero_diag_at = -float('inf')

        def send(self, v, w, expected_mode=None):
            requested_v, requested_w = float(v), float(w)
            with self.io_lock:
                with robot.lock:
                    mode = robot.mode
                    now = time.monotonic()
                    heartbeat = now - robot.last <= robot.TIMEOUT
                    detection_fresh = now - robot.follow['at'] <= robot.MAX_AUTO_AGE
                    # Preserve every existing safety gate; expose rejection cause.
                    reason = None
                    if not robot.ENABLE_REAL_MOTOR:
                        reason = 'MOTOR DISABLED'
                    elif mode == 'STOPPED':
                        reason = 'MODE STOPPED (press MANUAL for WASD)'
                    elif mode not in ('MANUAL', 'AUTO'):
                        reason = 'INVALID MODE'
                    elif not heartbeat:
                        reason = 'WEB HEARTBEAT LOST (focus browser)'
                    elif expected_mode is not None and expected_mode != mode:
                        reason = 'MODE CHANGED'
                    elif not self.backend.ready:
                        reason = 'ROS2 MOTOR BRIDGE OFFLINE'
                    elif mode == 'AUTO' and not robot.ENABLE_AUTO_FOLLOW:
                        reason = 'AUTO DISABLED'
                    elif mode == 'AUTO' and not detection_fresh and not (avoidance_on and avoidance_engine.active):
                        reason = 'YOLO DETECTION STALE'
                    elif args.mode == 'floor' and v < 0 and not (avoidance_on and avoidance_floor and mode == 'MANUAL'):
                        reason = 'REVERSE DISABLED ON FLOOR'

                if reason is None and avoidance_on:
                    scan = get_scan()
                    if mode == 'AUTO':
                        if human_help:
                            from dino_help_resume_v6 import verified_follow_dino
                            dino_seen = verified_follow_dino(robot.camera, robot.follow.get('detail',''), now,
                                                             min_conf=robot.TRACK_CONF,
                                                             confirmed_frames=robot.CONFIRM_FRAMES)
                        else:
                            dino_seen = (verified_dino(robot.camera, robot.follow.get('detail', ''), now)
                                         and getattr(robot.camera, 'verified_frames', 0) >= robot.CONFIRM_FRAMES)
                        v, w = avoidance_engine.plan(scan, v, w, now, mode, dino_seen)
                    elif mode == 'MANUAL':
                        avoidance_engine.reset()
                    blocked = directional_permission(
                        scan, v, w, mode,
                        floor_reverse_ok=(args.mode == 'wheels-up' or avoidance_floor),
                        allow_auto_reverse=((avoidance_v4 or avoidance_v5) and args.mode == 'wheels-up'),
                    )
                    if blocked is not None:
                        reason = blocked
                        if mode == 'AUTO' and avoidance_engine.active:
                            avoidance_engine.abort(now, blocked)
                elif reason is None and not clear_for_mode():
                    reason = 'LIDAR GATE BLOCKED'
                if avoidance_v6:
                    # Read-only state for the existing Buzzer and close-Dino sound workers.
                    # Never overrides or bypasses directional_permission.
                    robot._catrobot_avoidance_state = avoidance_engine.state
                    robot._catrobot_nav_stuck = (mode == 'AUTO' and
                        reason in (None, 'YOLO DETECTION STALE') and
                        avoidance_engine.navigation_sos_due(now))
                    robot._catrobot_nav_stuck_reason = (avoidance_engine.note
                        if robot._catrobot_nav_stuck else '')
                if reason != self.last_block_reason:
                    print('[DRIVE GATE]', reason or 'READY', flush=True)
                    self.last_block_reason = reason
                if reason is not None:
                    v = w = 0.0
                elif avoidance_on and mode == 'MANUAL' and v < 0.0 and abs(w) > 1e-6:
                    # V2 bounded rear arc, after full directional gate approval.
                    v = max(-0.025, v)
                    w = max(-0.075, min(0.075, w))
                if not (math.isfinite(float(v)) and math.isfinite(float(w))):
                    v = w = 0.0
                max_linear = (0.150 if bench_speed_015 else
                              0.080 if stable_speed_08 else
                              (0.085 if mode == 'AUTO' else 0.080) if speed_trial else
                              (0.070 if mode == 'AUTO' else 0.055))
                v = max(-max_linear, min(max_linear, float(v)))
                w = max(-0.19, min(0.19, float(w)))

                if mode == 'AUTO' and v == 0.0 and w == 0.0 and now - self.last_zero_diag_at >= 1.0:
                    with robot.lock:
                        auto_action = str(robot.follow.get('action', 'UNKNOWN'))
                        age = now - robot.follow.get('at', now)
                    verify_diag = ('DINO NOT CONFIRMED (TRACK_CONF / CONFIRM_FRAMES / target age)'
                                   if human_help and reason is None and not locals().get('dino_seen',False)
                                   and (abs(requested_v)>0.005 or abs(requested_w)>0.005) else '-')
                    print('[AUTO ZERO DIAG] input=({:+.3f},{:+.3f}) action={} age={:.2f}s gate={} avoidance={}:{} verifier={}'
                          .format(requested_v, requested_w, auto_action, age,
                                  reason or 'READY',
                                  avoidance_engine.state if avoidance_on else 'OFF',
                                  avoidance_engine.note if avoidance_on else '-', verify_diag), flush=True)
                    self.last_zero_diag_at = now
                if not self.backend.ready:
                    raise RuntimeError('ROS2 MOTOR BRIDGE OFFLINE')
                if v == 0.0 and w == 0.0:
                    self.backend.stop()
                else:
                    self.backend.velocity(v, w)
                robot._catrobot_last_v = v
                robot._catrobot_last_w = w

                drive = (round(v, 3), round(w, 3))
                if drive != self.last_drive:
                    print(f'[REAL MOTOR] mode={mode} v={v:+.3f} w={w:+.3f}', flush=True)
                    self.last_drive = drive
                return v, w

        def beep(self, on):
            self.backend.beep(bool(on))

        def servo(self, sid, angle):
            # Keep original Arrow keys/C logic, but bridge to REAL /Servo.
            # The driver expects BOTH s1/s2 on each message, not id+angle.
            with self.io_lock:
                if sid == robot.PAN_ID:
                    angle = max(robot.PAN_RANGE[0], min(robot.PAN_RANGE[1], int(angle)))
                    if angle == self.pan:
                        return
                    next_pan, next_tilt = angle, self.tilt
                elif sid == robot.TILT_ID:
                    angle = max(robot.TILT_RANGE[0], min(robot.TILT_RANGE[1], int(angle)))
                    if angle == self.tilt:
                        return
                    next_pan, next_tilt = self.pan, angle
                else:
                    print('[SERVO] Unknown servo ID:', sid, flush=True)
                    return
                if self.backend.servo(next_pan, next_tilt):
                    self.pan, self.tilt = next_pan, next_tilt
                    print(f'[REAL SERVO] pan={self.pan} tilt={self.tilt}', flush=True)

        def close(self):
            try:
                self.backend.stop()
                self.backend.beep(False)
            except Exception:
                pass
            self.backend.close()

    try:
        robot.camera = MainThreadCamera()
        def request_shutdown(signum, frame):
            robot.camera.running = False
        signal.signal(signal.SIGTERM, request_shutdown)
        signal.signal(signal.SIGHUP, request_shutdown)
        # Establish the ROS2 motor bridge before starting the YDLidar SDK.
        # The bridge publishes only zero velocity until the web controller
        # explicitly receives a MANUAL/AUTO command and all safety gates pass.
        print('[MOTOR] Connecting ROS2 bridge before LiDAR startup', flush=True)
        backend = DockerMotor(args.container, args.ros_domain_id,
                              max_linear=0.150 if bench_speed_015 else 0.085)
        print('[MOTOR] ROS2 bridge connected; starting LiDAR', flush=True)
        lidar = IsolatedLidar(args.lidar_port, args.front_angle)
        robot.motor = RealMotor(backend)
        robot._catrobot_last_v = 0.0
        robot._catrobot_last_w = 0.0
        robot._catrobot_nav_stuck = False
        robot._catrobot_nav_stuck_reason = ''
        robot._catrobot_avoidance_state = 'IDLE'
        if avoidance_on:
            original_set_mode = robot.set_mode
            def set_mode_avoiding(new_mode):
                ok, message = original_set_mode(new_mode)
                if ok and new_mode != 'AUTO':
                    avoidance_engine.reset()
                return ok, message
            robot.set_mode = set_mode_avoiding
            print('[AVOIDANCE] V6 ASSISTED HELP: ONE SOS, NO REVERSE, CLEAR SCAN -> FOLLOW (WHEELS-UP ONLY)'
                  if human_help else
                  '[AVOIDANCE] V6 PERSISTENT DINO GOAL + SAFE PATH STUCK SOS (WHEELS-UP ONLY)'
                  if avoidance_v6 else
                  '[AVOIDANCE] V5 GUARDED BACKUP+ONE ALTERNATE+REACQUIRE (WHEELS-UP ONLY)'
                  if avoidance_v5 else
                  '[AVOIDANCE] V4 GUARDED REVERSE+TURN+BYPASS+REACQUIRE (WHEELS-UP ONLY)'
                  if avoidance_v4 else
                  '[AVOIDANCE] V3 BOUNDED LOOKAHEAD+SIDESTEP+REACQUIRE (WHEELS-UP ONLY)'
                  if avoidance_v3 else
                  '[AVOIDANCE] V2: guarded MANUAL S+A/S+D and bounded AUTO turn/probe',
                  flush=True)

        # Original HTML/JS stays untouched: WASD, Arrows, C, H, 1-5, M/6-0,
        # mode buttons, original bounding boxes.
        for key in robot.MEOWS:
            robot.make_meow(key)

        original_status = robot.get_status

        def status_with_real_lidar():
            status = original_status()
            scan = get_scan()
            status.update({
                'lidar_reason': scan.get('reason'),
                'lidar_front_m': scan.get('front_min_m'),
                'lidar_left_m': scan.get('left_min_m'),
                'lidar_right_m': scan.get('right_min_m'),
                'lidar_rear_m': scan.get('avoid_rear_m'),
                'avoidance_state': avoidance_engine.state if avoidance_on else 'OFF',
                'avoidance_note': avoidance_engine.note if avoidance_on else 'OFF',
                'navigation_stuck_sos': bool(getattr(robot, '_catrobot_nav_stuck', False)),
                'motor_ready': bool(backend and backend.ready),
                'manual_block_reason': (
                    robot.motor.last_block_reason if robot.motor is not None else 'MOTOR NOT INITIALIZED'
                ),
            })
            return status

        robot.get_status = status_with_real_lidar
        from catrobot_vision_diagnostics import install_diagnostics
        install_diagnostics(robot, run_mode=args.mode)
        if close_meow_v4:
            try:
                near_area = max(0.04, min(0.25, float(os.environ.get('CATROBOT_DINO_CLOSE_BOX_AREA', '0.08'))))
            except ValueError:
                near_area = 0.08
            robot.SIM_STOP_AREA_RATIO = min(robot.SIM_STOP_AREA_RATIO, near_area)
            print('[DINO CLOSE] visual box stop area={:.1%}; centered+stable+stopped -> ~/sounds/meow.wav'.format(near_area), flush=True)

        control_thread = threading.Thread(
            target=robot.control_loop, args=(robot.motor,), daemon=True
        )
        control_thread.start()

        server = robot.ThreadingHTTPServer(('0.0.0.0', robot.PORT), robot.Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()

        print('[WEB] Original teleop UI + real YOLO: http://192.168.1.11:8080', flush=True)
        print('[WEB] Focus the browser for WASD. Press MANUAL or AUTO there.', flush=True)
        print('[MOTOR] REAL ROS2, initially STOPPED', flush=True)
        print('[SERVO] Arrows move S1/S2; C centers to 90/35; no startup movement', flush=True)
        print('[AUDIO] Friend original device:', friend_teleop.audio_device(), flush=True)

        # The key change versus the failed CameraProxy: inference stays in MAIN.
        from dino_auto_meow import start_auto_meow
        start_auto_meow(robot, get_scan)
        from dino_auto_center import start_auto_center
        start_auto_center(robot, wheels_up_mode=(args.mode == 'wheels-up'))
        # User-selected responsive Dino threshold; run-time globals in existing camera loop.
        robot.YOLO_CONF = 0.05
        robot.TRACK_CONF = (0.10 if orange_follow else 0.25) if human_help else (0.10 if camera_stable else 0.05)
        robot.CONFIRM_FRAMES = (1 if orange_follow else 2) if human_help else (2 if camera_stable else 1)
        if orange_follow:
            print('[ORANGE FOLLOW] user-selected prior settings: TRACK >= 0.10 and CONFIRM_FRAMES=1; LiDAR/STOP unchanged', flush=True)
        print('[DINO CAMERA] IMG_SIZE={} YOLO={} TRACK={} CONFIRM_FRAMES={} | model unchanged'.format(
            args.imgsz, robot.YOLO_CONF, robot.TRACK_CONF, robot.CONFIRM_FRAMES), flush=True)
        if camera_stable:
            print('[DINO CAMERA] STABLE TRIAL ONLY; may miss lower-confidence distant Dino', flush=True)
        from lidar_buzzer_tiers import start_obstacle_alert
        start_obstacle_alert(robot, get_scan, floor_mode=(args.mode == 'floor'), short_range=lidar_22cm)
        robot.camera.loop()

    except KeyboardInterrupt:
        print('[EXIT] Keyboard interrupt', flush=True)
    finally:
        print('[EXIT] Stop before closing ROS2 bridge', flush=True)
        try:
            robot.set_mode('STOPPED')
        except Exception as exc:
            print('[STOP WARNING]', exc, flush=True)
        if robot.camera is not None:
            robot.camera.running = False
        if server is not None:
            server.shutdown()
            server.server_close()
        if robot.camera is not None:
            robot.camera.close()
        if robot.motor is not None:
            robot.motor.close()
        elif backend is not None:
            backend.close()
        if lidar is not None:
            lidar.close()
        print('[EXIT] Shutdown complete. Verify physical wheels are stopped.', flush=True)


if __name__ == '__main__':
    main()

# DINO_UPGRADE_20261108: installed

# CATROBOT_CAMERA_FIRST_V2_20261108: installed

# CATROBOT_LIDAR_22CM_OBSTACLE_MEOW_20261109: installed

# CATROBOT_BUZZER_FRONT40_20261109: installed

# CATROBOT_FRONT28_SIDE26_MEOW_TUNE_20261109: installed

# CATROBOT_BUZZER_22CM_LONG_20261109: installed

# CATROBOT_AVOIDANCE_V1_20261109: installed

# CATROBOT_DINO_RANGE_V4_2_TIER_COMPAT_20261109: installed

# CATROBOT_AVOIDANCE_V3_PI_COMPAT_20261109: installed

# CATROBOT_AVOIDANCE_V4_PI_SAFERECOVERY_20261109: installed

# CATROBOT_V5_FOLLOW_RECOVERY_SPEED_DIAG: installed

# CATROBOT_V6_STUCK_SOS_PERSISTENT_DINO: installed

# CATROBOT_V6_ASSISTED_HELP_WHEELS_UP_20261109: installed

# CATROBOT_V6_STABILITY_SPEED08_20261109: installed

# CATROBOT_V6_CONF010_1FRAME_BENCH015_20261109: installed
