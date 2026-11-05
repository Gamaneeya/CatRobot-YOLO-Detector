
import math
import threading
import time


SECTOR_BINS = {
    "front": [(-40, -20), (-20, 0), (0, 20), (20, 40)],
    "left": [(0, 35), (35, 70), (70, 105)],
    "right": [(-105, -70), (-70, -35), (-35, 0)]
}

FRONT_STOP_M = 0.70
SIDE_STOP_M = 0.60
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
