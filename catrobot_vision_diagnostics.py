"""Read-only observations of the existing camera/model and status callbacks.

No motor, buzzer, sound, mode, servo, LiDAR reader or worker thread is created.
The original prediction arguments, results and follow commands pass through.
"""
import base64
import json
import math
import os
import threading
import time
from urllib.parse import urlsplit

VERSION = '4.2-pi-tier-compatible'


def finite(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def profile_metadata(run_mode):
    enabled = lambda key: os.environ.get(key, '0') == '1'
    if enabled('CATROBOT_LIDAR_FRONT28_SIDE26'):
        name, front, side = 'FRONT28_SIDE26', .28, .26
    elif enabled('CATROBOT_LIDAR_FRONT40_SIDE30'):
        name, front, side = 'FRONT40_SIDE30', .40, .30
    elif enabled('CATROBOT_LIDAR_22CM_TEST'):
        name, front, side = '22CM_TEST', .22, .22
    else:
        name, front, side = 'DEFAULT', .40, .30
        if run_mode == 'floor':
            front, side = .65, .42
    return dict(name=name, front_stop_m=front, side_stop_m=side,
                emergency_m=.22 if enabled('CATROBOT_LIDAR_360_RADIUS_TEST') else None,
                run_mode=run_mode, motor_policy_changed=False,
                obstacle_module='lidar_buzzer_tiers',
                optional_avoidance=enabled('CATROBOT_AVOIDANCE_V1'),
                rear_stop_m=.28 if enabled('CATROBOT_AVOIDANCE_V1') else None,
                note='Existing Pi policy, unchanged; nearest LiDAR echo is not Dino depth')


class VisionMonitor:
    def __init__(self, robot):
        self.robot = robot
        self.lock = threading.RLock()
        self.seq = 0
        self.raw = None
        self.pending = {}
        self.observation = {}
        self.last_status = {}

    def begin(self, frame, now):
        raw = frame.copy() if hasattr(frame, 'copy') else None
        with self.lock:
            self.seq += 1
            self.raw = raw
            self.pending = dict(frame_seq=self.seq, frame_at=now,
                                inference_imgsz=self.robot.IMG_SIZE)

    def predicted(self, results, now):
        with self.lock:
            self.pending['inference_ms'] = 1000 * (now - self.pending['frame_at'])
            self.pending.update(confidence=None, bbox=None, area_ratio=None,
                                box_width_px=None, box_height_px=None)
            result = results[0]
            h, w = self.raw.shape[:2]
            self.pending.update(frame_width=w, frame_height=h)
            candidates = [b for b in result.boxes if int(b.cls[0]) == 0]
            if candidates:
                box = max(candidates, key=lambda b: float(b.conf[0]))
                xy = [float(x) for x in box.xyxy[0].tolist()]
                confidence = float(box.conf[0])
                if not all(finite(value) for value in xy + [confidence]):
                    return
                width = max(0., xy[2] - xy[0])
                height = max(0., xy[3] - xy[1])
                self.pending.update(confidence=confidence, bbox=xy,
                                    box_width_px=width, box_height_px=height,
                                    area_ratio=width * height / (w * h))

    def failed(self, error):
        with self.lock:
            self.pending.update(confidence=None, bbox=None, area_ratio=None,
                                inference_error=str(error))
            self.observation = dict(self.pending, healthy=False,
                                    accepted_by_original=False, action='YOLO ERROR')

    def published(self, action, detail, now):
        with self.lock:
            p = dict(self.pending)
            at = p.get('frame_at')
            fresh = finite(at) and 0 <= now - at <= self.robot.MAX_AUTO_AGE
            error = any(word in str(action) for word in ('CAMERA LOST', 'CAMERA ERROR', 'YOLO ERROR'))
            conf = p.get('confidence')
            accepted = (not error and fresh and 'Conf:' in str(detail)
                        and finite(conf) and conf >= self.robot.TRACK_CONF
                        and self.robot.camera.verified_frames >= self.robot.CONFIRM_FRAMES)
            p.update(healthy=bool(not error and fresh), accepted_by_original=bool(accepted),
                     action=str(action), detail=str(detail), track_conf=self.robot.TRACK_CONF,
                     preview_conf=self.robot.YOLO_CONF, confirm_frames=self.robot.CONFIRM_FRAMES,
                     box_stop_area=self.robot.SIM_STOP_AREA_RATIO)
            if error:
                p.update(confidence=None, bbox=None, area_ratio=None)
            self.observation = p

    def snapshot(self):
        with self.lock:
            result = dict(self.observation)
        at = result.get('frame_at')
        age = time.monotonic() - at if finite(at) else None
        result['frame_age_ms'] = age * 1000 if finite(age) and age >= 0 else None
        result['frame_fresh'] = bool(finite(age) and 0 <= age <= self.robot.MAX_AUTO_AGE)
        result['healthy'] = bool(result.get('healthy') and result['frame_fresh'])
        result['age_basis'] = 'since predict began; not a hardware camera capture timestamp'
        result['motion_policy_changed'] = False
        return result


class ObservedModel:
    def __init__(self, model, monitor):
        self.model, self.monitor = model, monitor
        self.owner = None
        self.owner_lock = threading.Lock()

    def __getattr__(self, name):
        return getattr(self.model, name)

    def predict(self, *args, **kwargs):
        ident = threading.get_ident()
        with self.owner_lock:
            if self.owner is None:
                self.owner = ident
            if self.owner != ident:
                raise RuntimeError('Keep YOLO inference in its original camera thread')
        frame = kwargs.get('source', args[0] if args else None)
        try:
            self.monitor.begin(frame, time.monotonic())
        except Exception:
            pass
        try:
            results = self.model.predict(*args, **kwargs)
        except Exception as exc:
            self.monitor.failed(exc)
            raise
        try:
            self.monitor.predicted(results, time.monotonic())
        except Exception:
            pass
        return results


def install_diagnostics(robot, run_mode='wheels-up'):
    if getattr(robot, '_vision_range_diagnostics', None) is not None:
        return robot._vision_range_diagnostics
    monitor = VisionMonitor(robot)
    robot._vision_range_diagnostics = monitor
    robot.camera.model = ObservedModel(robot.camera.model, monitor)
    original_publish = robot.publish_follow

    def publish(*args, **kwargs):
        result = original_publish(*args, **kwargs)
        try:
            action = kwargs.get('action', args[2] if len(args) > 2 else '')
            detail = kwargs.get('detail', args[3] if len(args) > 3 else '')
            monitor.published(action, detail, time.monotonic())
        except Exception:
            pass
        return result

    robot.publish_follow = publish
    original_status = robot.get_status

    def status():
        current = dict(original_status())
        with monitor.lock:
            monitor.last_status = dict(current)
        current.update(dino=monitor.snapshot(), range_diagnostics_version=VERSION,
                       range_profile=profile_metadata(run_mode))
        return current

    robot.get_status = status
    original_encode = robot.camera.encode

    def encode(frame):
        try:
            import cv2
            p = monitor.snapshot()
            conf, area, ms = p.get('confidence'), p.get('area_ratio'), p.get('inference_ms')
            c = f'{conf:.3f}' if finite(conf) else '--'
            a = f'{100*area:.1f}%' if finite(area) else '--'
            latency = f'{ms:.0f}ms' if finite(ms) else '--'
            text = (f'YOLO {robot.IMG_SIZE} | infer {latency} | conf {c} | box {a}'
                    f' | stop {100*robot.SIM_STOP_AREA_RATIO:.0f}%')
            with monitor.lock:
                lidar_status = dict(monitor.last_status)
            def metres(key):
                value = lidar_status.get(key)
                return f'{value:.2f}m' if finite(value) else '--'
            gate = getattr(robot.motor, 'last_block_reason', None) or 'READY'
            rows = [text, f'Existing gate: {str(gate)[:62]}',
                    f'LiDAR F {metres("lidar_front_m")} L {metres("lidar_left_m")} '
                    f'R {metres("lidar_right_m")} | not Dino depth']
            for y, row in zip((104, 124, 144), rows):
                cv2.putText(frame, row, (12, y), cv2.FONT_HERSHEY_SIMPLEX,
                            .42, (255, 230, 150), 1)
        except Exception:
            pass
        return original_encode(frame)

    robot.camera.encode = encode
    original_handler = robot.Handler

    class Handler(original_handler):
        def do_GET(self):
            if urlsplit(self.path).path != '/dino/raw':
                return super().do_GET()
            with monitor.lock:
                frame = monitor.raw.copy() if monitor.raw is not None else None
                meta = dict(monitor.pending)
            if frame is None:
                return self.reply(503, 'text/plain', b'Waiting for raw camera frame')
            import cv2
            ok, data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not ok:
                return self.reply(503, 'text/plain', b'Raw JPEG encoding failed')
            meta['jpeg_base64'] = base64.b64encode(data.tobytes()).decode('ascii')
            return self.reply(200, 'application/json', json.dumps(meta).encode('utf-8'))

    robot.Handler = Handler
    print('[DINO RANGE V4.2] read-only diagnostics active; current LiDAR, tier buzzer, '
          'six Dino voices, modes and motion settings preserved', flush=True)
    return monitor
