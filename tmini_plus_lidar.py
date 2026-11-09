
import math
import os
from lidar_360_guard import evaluate_circle
from lidar_directional_avoidance import collect_directional
import threading
import time


SECTOR_BINS = {
    "front": [(-40, -20), (-20, 0), (0, 20), (20, 40)],
    "left": [(0, 35), (35, 70), (70, 105)],
    "right": [(-105, -70), (-70, -35), (-35, 0)]
}

# Keep the actual Pi settings when experimental 22cm is OFF.
# LiDAR distance is from its measuring origin, not the bumper surface.
_EXPERIMENTAL_22CM = os.environ.get('CATROBOT_LIDAR_22CM_TEST', '0') == '1'
# Opt-in obstacle-distance profile. Unlike 360 radius 0.22m this is
# a forward/side sector guard. Camera may see Dino even when LiDAR blocks it.
_FRONT40_SIDE30 = os.environ.get('CATROBOT_LIDAR_FRONT40_SIDE30', '0') == '1'
_FRONT28_SIDE26 = os.environ.get('CATROBOT_LIDAR_FRONT28_SIDE26', '0') == '1'
FRONT_STOP_M = 0.28 if _FRONT28_SIDE26 else (0.40 if _FRONT40_SIDE30 else 0.22 if _EXPERIMENTAL_22CM else 0.40)
SIDE_STOP_M = 0.26 if _FRONT28_SIDE26 else (0.30 if _FRONT40_SIDE30 else 0.22 if _EXPERIMENTAL_22CM else 0.30)
MAX_SCAN_AGE_S = 0.50
MIN_POINTS_PER_BIN = 2
MIN_VALID_RANGE_M = 0.05
MAX_VALID_RANGE_M = 12.0


def normalize_angle(angle):
    return (angle + 180.0) % 360.0 - 180.0


class TminiPlusReader:
    def __init__(self, port, front_angle_deg=0.0):
        self.port = port
        self.front_angle_deg = float(front_angle_deg)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._points = []
        self._last_scan = 0.0
        self._error = "NOT STARTED"
        self._scan_count = 0

    def start(self):
        if self._thread is not None:
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="tmini-plus-reader"
        )
        self._thread.start()

    def _accept_scan(self, points):
        clean = []

        for angle, distance in points:
            try:
                angle = float(angle)
                distance = float(distance)
            except (ValueError, TypeError):
                continue

            if not (
                math.isfinite(angle)
                and math.isfinite(distance)
            ):
                continue

            if not (
                MIN_VALID_RANGE_M
                <= distance
                <= MAX_VALID_RANGE_M
            ):
                continue

            relative_angle = normalize_angle(
                angle - self.front_angle_deg
            )
            clean.append((relative_angle, distance))

        with self._lock:
            self._points = clean
            self._last_scan = time.monotonic()
            self._scan_count += 1
            self._error = None

    def _run(self):
        laser = None
        activated = False

        try:
            import ydlidar

            ydlidar.os_init()

            laser = ydlidar.CYdLidar()

            laser.setlidaropt(
                ydlidar.LidarPropSerialPort,
                self.port
            )
            laser.setlidaropt(
                ydlidar.LidarPropSerialBaudrate,
                230400
            )
            laser.setlidaropt(
                ydlidar.LidarPropLidarType,
                ydlidar.TYPE_TRIANGLE
            )
            laser.setlidaropt(
                ydlidar.LidarPropDeviceType,
                ydlidar.YDLIDAR_TYPE_SERIAL
            )
            laser.setlidaropt(
                ydlidar.LidarPropScanFrequency,
                10.0
            )
            laser.setlidaropt(
                ydlidar.LidarPropSampleRate,
                4
            )
            laser.setlidaropt(
                ydlidar.LidarPropSingleChannel,
                False
            )
            laser.setlidaropt(
                ydlidar.LidarPropMaxAngle,
                180.0
            )
            laser.setlidaropt(
                ydlidar.LidarPropMinAngle,
                -180.0
            )
            laser.setlidaropt(
                ydlidar.LidarPropMaxRange,
                16.0
            )
            laser.setlidaropt(
                ydlidar.LidarPropMinRange,
                0.02
            )
            laser.setlidaropt(
                ydlidar.LidarPropIntenstiy,
                True
            )

            if not laser.initialize():
                raise RuntimeError(
                    "T-MINI Plus initialize failed"
                )

            if not laser.turnOn():
                raise RuntimeError(
                    "T-MINI Plus turnOn failed"
                )

            activated = True

            with self._lock:
                self._error = None

            print("[TMINI] Scanning:", self.port)

            while (
                not self._stop.is_set()
                and ydlidar.os_isOk()
            ):
                scan = ydlidar.LaserScan()

                if not laser.doProcessSimple(scan):
                    time.sleep(0.05)
                    continue

                points = []

                for point in scan.points:
                    angle_deg = math.degrees(
                        float(point.angle)
                    )
                    distance_m = float(point.range)

                    points.append((
                        angle_deg,
                        distance_m
                    ))

                self._accept_scan(points)

        except Exception as exc:
            print("[TMINI ERROR]", exc)

            with self._lock:
                self._error = str(exc)
                self._last_scan = 0.0

        finally:
            if laser is not None:
                if activated:
                    try:
                        laser.turnOff()
                    except Exception as exc:
                        print("[TMINI TURN OFF]", exc)

                try:
                    laser.disconnecting()
                except Exception as exc:
                    print("[TMINI DISCONNECT]", exc)

            with self._lock:
                self._error = (
                    self._error
                    or "LIDAR READER STOPPED"
                )
                self._last_scan = 0.0

    def snapshot(self):
        with self._lock:
            points = list(self._points)
            last_scan = self._last_scan
            error = self._error
            count = self._scan_count

        if last_scan <= 0:
            return {
                "clear": False,
                "reason": error or "WAITING FOR SCAN",
                "scan_age_s": None,
                "scan_count": count,
                "valid_points": len(points),
                "front_min_m": None,
                "left_min_m": None,
                "right_min_m": None
            }

        age = time.monotonic() - last_scan

        result = {
            "clear": False,
            "reason": "CHECKING SCAN",
            "scan_age_s": round(age, 3),
            "scan_count": count,
            "valid_points": len(points),
            "front_min_m": None,
            "left_min_m": None,
            "right_min_m": None
        }

        if error is not None:
            result["reason"] = error
            return result

        if age > MAX_SCAN_AGE_S:
            result["reason"] = "STALE LIDAR DATA"
            return result

        # Independent 360-degree directional geometry: evaluate all sectors
        # BEFORE the existing circle/front/side early-return safety gates.
        # Existing original LiDAR gating below remains unchanged when optional
        # avoidance is disabled.
        if os.environ.get('CATROBOT_AVOIDANCE_V1', '0') == '1':
            result.update(collect_directional(points))

        # Optional 360-degree proximity from the laser origin, independent of YOLO.
        # This only reads existing scan echoes; the old missing/stale-data and
        # front/side gates below remain authoritative for all wheel commands.
        if os.environ.get('CATROBOT_LIDAR_360_RADIUS_TEST', '0') == '1':
            circle = evaluate_circle(points, radius_m=0.22)
            result.update(circle)
            if os.environ.get('CATROBOT_LIDAR_360_DEBUG', '0') == '1':
                now = time.monotonic()
                if now - getattr(self, '_circle_debug_at', 0.0) >= 0.8:
                    print('[LIDAR 360] min={}m angle={}deg hits={} radius=0.22m '
                          'valid_points={}'.format(circle['circle_min_m'],
                          circle['circle_min_angle_deg'],
                          circle['circle_hits_inside'], len(points)), flush=True)
                    self._circle_debug_at = now
            if circle['circle_obstacle']:
                result['reason'] = '360 OBSTACLE: {:.2f}m angle={:.0f}deg'.format(
                    circle['circle_min_m'], circle['circle_min_angle_deg'])
                return result

        for sector, bins in SECTOR_BINS.items():
            sector_distances = []

            for low, high in bins:
                distances = [
                    distance
                    for angle, distance in points
                    if low <= angle < high
                ]

                if len(distances) < MIN_POINTS_PER_BIN:
                    result["reason"] = (
                        f"INSUFFICIENT {sector.upper()} DATA"
                    )
                    return result

                sector_distances.extend(distances)

            nearest = min(sector_distances)

            result[f"{sector}_min_m"] = round(
                nearest, 3
            )

            required_distance = (
                FRONT_STOP_M
                if sector == "front"
                else SIDE_STOP_M
            )

            if nearest < required_distance:
                result["reason"] = (
                    f"{sector.upper()} OBSTACLE: "
                    f"{nearest:.2f}m"
                )
                return result

        result["clear"] = True
        result["reason"] = "SCAN CLEAR"
        return result

    def is_clear(self):
        return self.snapshot()["clear"]

    def close(self):
        self._stop.set()

        if self._thread is not None:
            self._thread.join(timeout=3.0)

# CATROBOT_LIDAR_22CM_OBSTACLE_MEOW_20261109: installed

# CATROBOT_LIDAR_360_INDEPENDENT_GUARD_20261109: installed

# CATROBOT_BUZZER_FRONT40_20261109: installed

# CATROBOT_FRONT28_SIDE26_MEOW_TUNE_20261109: installed

# CATROBOT_AVOIDANCE_V1_20261109: installed
