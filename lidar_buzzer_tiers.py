"""CatRobot LiDAR-only short-stop / long-emergency buzzer (incremental).

Uses existing LiDAR snapshots and original ROS2 buzzer UI API; no new LiDAR
reader or motor/ROS2 publisher. The physical stop remains RealMotor.send gate.
"""
import math
import threading
import time

from lidar_obstacle_alert import _fresh, _obstacle_reason, _can_rearm

EMERGENCY_M = 0.22
LONG_REPEAT_S = 1.5  # Original pattern 3: 800ms ON, then a pause.
RESET_CLEAR_S = 0.9
POLL_S = 0.12
REVERSE_REPEAT_S = 2.1
SOS_FAULT_HOLD_S = 2.5
SOS_REPEAT_S = 12.0


def classify_scan(scan, floor_mode=False, short_range=False):
    """Return one of emergency, stop, clear, fault; never infer camera objects."""
    if not isinstance(scan, dict) or not _fresh(scan):
        return 'fault', str(scan.get('reason', 'NO FRESH SCAN')) if isinstance(scan, dict) else 'NO SCAN'
    reason = str(scan.get('reason', ''))
    hits = scan.get('circle_hits_inside')
    minimum = scan.get('circle_min_m')
    circle_hit = (isinstance(hits, (int, float)) and not isinstance(hits, bool)
                  and math.isfinite(hits) and hits > 0
                  and isinstance(minimum, (int, float)) and not isinstance(minimum, bool)
                  and math.isfinite(minimum) and minimum <= EMERGENCY_M)
    if reason.startswith('360 OBSTACLE:') or (circle_hit and scan.get('clear') is False):
        return 'emergency', reason or f'360 OBSTACLE: {minimum:.2f}m'
    if scan.get('avoid_scan_valid') is False:
        return 'fault', 'DIRECTIONAL LIDAR COVERAGE INCOMPLETE: ' + reason
    other = _obstacle_reason(scan, floor_mode=floor_mode, short_range=short_range)
    if other:
        return 'stop', other
    # The original front/side reader has no REAR stop sector. V1 adds a
    # validated rear sector, so warn on a rear obstacle even if SCAN CLEAR.
    # No new LiDAR reader is created and this does not grant wheel movement.
    if scan.get('avoid_scan_valid') is True:
        rear = scan.get('avoid_rear_m')
        if (isinstance(rear, (int, float)) and not isinstance(rear, bool)
                and math.isfinite(rear) and rear < 0.28):
            return 'stop', f'REAR OBSTACLE: {rear:.2f}m (rear stop 0.28m)'
    if _can_rearm(scan, floor_mode=floor_mode, short_range=short_range):
        return 'clear', reason
    return 'fault', reason or 'UNKNOWN LIDAR STATE'


def start_obstacle_alert(robot, scan_reader, floor_mode=False, short_range=False):
    """Warn at existing stop thresholds; long beep at <=22cm on any LiDAR ray.

    No change to the motor permission logic: stops are still issued only through
    RealMotor.send via the original fail-closed LiDAR gate. Does not play meows.
    """
    if getattr(robot, '_lidar_obstacle_alert_started', False):
        return
    if getattr(robot, 'pattern_busy', None) is None:
        raise RuntimeError('Original buzzer pattern_busy event missing')
    if getattr(robot, 'PATTERNS', {}).get('3', (None, None))[1] != [(800, 0)]:
        raise RuntimeError('Original long-beep pattern 3 differs; not starting alert')
    if '2' not in getattr(robot, 'PATTERNS', {}):
        raise RuntimeError('Original double-beep pattern 2 missing')
    for key in ('4','5'):
        if key not in getattr(robot, 'PATTERNS', {}):
            raise RuntimeError('Original reverse/SOS buzzer pattern '+key+' missing')
    robot._lidar_obstacle_alert_started = True
    robot._lidar_obstacle_alert_active = False

    def worker():
        short_latched = False
        clear_since = None
        last_long = -float('inf')
        last_reverse = -float('inf')
        last_sos = -float('inf')
        nav_sos_latched = False
        fault_since = None
        try:
            while True:
                time.sleep(POLL_S)
                cam = getattr(robot, 'camera', None)
                if cam is None or not getattr(cam, 'running', False):
                    return
                with robot.lock:
                    mode = robot.mode
                try:
                    scan = scan_reader()
                except Exception as exc:
                    scan = {'reason': 'LIDAR SNAPSHOT ERROR: ' + repr(exc), 'clear': False}
                state, reason = classify_scan(scan, floor_mode, short_range)
                # A rear-only short warning must not permanently silence
                # the six Dino meows while the camera sees the toy ahead.
                # Forward/side obstacles and any 22cm emergency still
                # suppress automatic Dino audio during the obstacle event.
                rear_only = state == 'stop' and reason.startswith('REAR OBSTACLE:')
                robot._lidar_obstacle_alert_active = state in ('stop', 'emergency') and not rear_only
                if mode not in ('AUTO', 'MANUAL'):
                    short_latched = False
                    clear_since = None
                    last_long = -float('inf')
                    continue
                now = time.monotonic()
                # Genuine sensor faults, not an ordinary obstacle stop, can
                # produce SOS after a persistent hold. Do not SOS during startup.
                unhealthy = (state == 'fault' and isinstance(scan, dict) and
                             not (mode == 'AUTO' and getattr(robot, '_catrobot_avoidance_state', '') == 'WAIT_HELP') and
                             (not _fresh(scan) or scan.get('avoid_scan_valid') is False))
                if unhealthy:
                    if fault_since is None:
                        fault_since = now
                    if (now - fault_since >= SOS_FAULT_HOLD_S and
                            now - last_sos >= SOS_REPEAT_S and
                            not robot.pattern_busy.is_set()):
                        try:
                            robot.play_pattern(robot.motor, '5')
                            last_sos = now
                            print('[LIDAR BUZZER SOS] persistent LiDAR fault: ' + reason +
                                  ' -> original pattern 5', flush=True)
                        except Exception as exc:
                            print('[LIDAR SOS ERROR]', repr(exc), flush=True)
                else:
                    fault_since = None
                # Assisted-Human mode: SOS ONCE for each WAIT_HELP event.
                # Suppress overlapping short/long/reverse alerts in WAIT_HELP;
                # motor fail-safe still operates independently.
                nav_waiting = (mode == 'AUTO' and
                               getattr(robot, '_catrobot_avoidance_state', '') == 'WAIT_HELP')
                if not nav_waiting:
                    nav_sos_latched = False
                if nav_waiting:
                    clear_since = None
                    short_latched = True
                    if (getattr(robot, '_catrobot_nav_stuck', False) and
                            not nav_sos_latched and not robot.pattern_busy.is_set()):
                        try:
                            robot.play_pattern(robot.motor, '5')
                            last_sos = now
                            nav_sos_latched = True
                            print('[HELP V6 SOS] one pattern 5 for help request: ' +
                                  str(getattr(robot, '_catrobot_nav_stuck_reason', 'blocked')),
                                  flush=True)
                        except Exception as exc:
                            print('[HELP V6 SOS ERROR]', repr(exc), flush=True)
                    continue
                # SOS for a proven blocked *navigation plan*, not a failed LiDAR.
                # All motion was already stopped by the planner/RealMotor gate.
                # Emergency <22 cm keeps the long-beep priority; genuine sensor
                # faults keep the original independent SOS path above.
                nav_stuck = (mode == 'AUTO' and
                             getattr(robot, '_catrobot_nav_stuck', False) and
                             state not in ('emergency', 'fault'))
                if nav_stuck:
                    clear_since = None
                    short_latched = True
                    if (now - last_sos >= SOS_REPEAT_S and
                            not robot.pattern_busy.is_set()):
                        try:
                            robot.play_pattern(robot.motor, '5')
                            last_sos = now
                            print('[NAVIGATION SOS] no verified route to Dino after safe retries: ' +
                                  str(getattr(robot, '_catrobot_nav_stuck_reason', 'blocked')) +
                                  ' -> original pattern 5', flush=True)
                        except Exception as exc:
                            print('[NAVIGATION SOS ERROR]', repr(exc), flush=True)
                    continue
                moving_reverse = (isinstance(getattr(robot, '_catrobot_last_v', None), (int, float))
                                  and getattr(robot, '_catrobot_last_v', 0.0) < -0.001)
                if state == 'emergency':
                    short_latched = True
                    clear_since = None
                    if (now - last_long >= LONG_REPEAT_S and
                            not robot.pattern_busy.is_set()):
                        try:
                            robot.play_pattern(robot.motor, '3')
                            last_long = now
                            print('[OBSTACLE BUZZER LONG] ' + mode + ': ' +
                                  reason + ' -> pattern 3 (800ms, repeats while emergency)', flush=True)
                        except Exception as exc:
                            print('[OBSTACLE BUZZER ERROR]', repr(exc), flush=True)
                    continue
                if state == 'stop':
                    clear_since = None
                    if not short_latched and not robot.pattern_busy.is_set():
                        try:
                            robot.play_pattern(robot.motor, '2')
                            short_latched = True
                            print('[OBSTACLE BUZZER SHORT] ' + mode + ': ' + reason +
                                  ' -> pattern 2 (double beep)', flush=True)
                        except Exception as exc:
                            print('[OBSTACLE BUZZER ERROR]', repr(exc), flush=True)
                    # Reverse alarm is allowed after the initial obstacle beep
                    # only when the ACTUAL wheel command is negative.
                    if (moving_reverse and short_latched and now - last_reverse >= REVERSE_REPEAT_S
                            and not robot.pattern_busy.is_set()):
                        robot.play_pattern(robot.motor, '4')
                        last_reverse = now
                        print('[REVERSE BUZZER] driving backward -> original pattern 4', flush=True)
                    continue
                if state == 'clear':
                    if (moving_reverse and now - last_reverse >= REVERSE_REPEAT_S
                            and not robot.pattern_busy.is_set()):
                        robot.play_pattern(robot.motor, '4')
                        last_reverse = now
                        print('[REVERSE BUZZER] driving backward -> original pattern 4', flush=True)
                    if clear_since is None:
                        clear_since = now
                    elif now - clear_since >= RESET_CLEAR_S:
                        short_latched = False
                        last_long = -float('inf')
                else:
                    # Missing/stale/insufficient data are not treated as clear.
                    clear_since = None
        finally:
            robot._lidar_obstacle_alert_active = False

    threading.Thread(target=worker, daemon=True, name='lidar-buzzer-22cm-tiers').start()
    print('[OBSTACLE BUZZER] READY: STOP thresholds -> pattern 2; <=0.22m 360 -> '
          'repeating long pattern 3; reverse pattern 4; persistent LiDAR fault or blocked navigation SOS pattern 5; motor gate unchanged', flush=True)

# CATROBOT_AVOIDANCE_V2_REAR_BUZZER_20261109: installed

# CATROBOT_AVOIDANCE_V4_REVERSE_SOS_BUZZER: installed

# CATROBOT_V6_NAVIGATION_STUCK_SOS: installed

# CATROBOT_V6_ASSISTED_ONE_NAV_SOS_WHEELS_UP_20261109: installed
