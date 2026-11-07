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


def main():
    p = argparse.ArgumentParser(description='Real robot, original YOLO teleop web')
    p.add_argument('--mode', required=True, choices=('wheels-up', 'floor'))
    p.add_argument('--container', default='affectionate_lamport')
    p.add_argument('--ros-domain-id', type=int, default=62)
    p.add_argument('--lidar-port', default='/dev/ttyUSB1')
    p.add_argument('--front-angle', type=float, default=0.0)
    p.add_argument('--imgsz', type=int, default=320, choices=(320, 416, 640))
    p.add_argument('--confirm-wheels-up', action='store_true')
    p.add_argument('--confirm-wheels-tested', action='store_true')
    p.add_argument('--confirm-lidar-calibrated', action='store_true')
    p.add_argument('--confirm-emergency-stop', action='store_true')
    args = p.parse_args()

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
    robot.SIM_FORWARD_SPEED = 0.055
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
        if not scan.get('clear'):
            return False
        if args.mode == 'floor':
            # Additional floor guard, regardless of the user's wheel-up settings.
            for field, minimum in (
                ('front_min_m', 0.65),
                ('left_min_m', 0.42),
                ('right_min_m', 0.42),
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

        def send(self, v, w, expected_mode=None):
            with self.io_lock:
                with robot.lock:
                    mode = robot.mode
                    now = time.monotonic()
                    heartbeat = now - robot.last <= robot.TIMEOUT
                    detection_fresh = now - robot.follow['at'] <= robot.MAX_AUTO_AGE
                    allowed = (
                        robot.ENABLE_REAL_MOTOR
                        and mode in ('MANUAL', 'AUTO')
                        and heartbeat
                        and (expected_mode is None or expected_mode == mode)
                        and self.backend.ready
                    )
                    if mode == 'AUTO':
                        allowed = allowed and robot.ENABLE_AUTO_FOLLOW and detection_fresh
                    # Backward motion has not been cleared for FLOOR operation.
                    if args.mode == 'floor' and v < 0:
                        allowed = False

                if allowed:
                    allowed = clear_for_mode()
                if not allowed:
                    v = w = 0.0
                if not (math.isfinite(float(v)) and math.isfinite(float(w))):
                    v = w = 0.0
                v = max(-0.055, min(0.055, float(v)))
                w = max(-0.19, min(0.19, float(w)))

                if not self.backend.ready:
                    raise RuntimeError('ROS2 MOTOR BRIDGE OFFLINE')
                if v == 0.0 and w == 0.0:
                    self.backend.stop()
                else:
                    self.backend.velocity(v, w)

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
        lidar = IsolatedLidar(args.lidar_port, args.front_angle)
        backend = DockerMotor(args.container, args.ros_domain_id)
        robot.motor = RealMotor(backend)

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
                'motor_ready': bool(backend and backend.ready),
            })
            return status

        robot.get_status = status_with_real_lidar

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
