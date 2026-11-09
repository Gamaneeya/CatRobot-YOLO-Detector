"""Announce LiDAR obstacles with the EXISTING buzzer-pattern path (not meow).

No motor commands, serial access, new ROS2 publishers, camera, or LiDAR readers.
Motion blocking remains exclusively in the existing RealMotor LiDAR gate.
"""
import math
import os
import threading
import time


OBSTACLE_PREFIXES = ('FRONT OBSTACLE:', 'LEFT OBSTACLE:',
                     'RIGHT OBSTACLE:', '360 OBSTACLE:')


def _fresh(scan):
    age = scan.get('scan_age_s') if isinstance(scan, dict) else None
    return (isinstance(age, (int, float)) and not isinstance(age, bool)
            and math.isfinite(age) and 0 <= age <= 0.50)


def _floor_limits(short_range):
    # EXACTLY mirror the runner's floor guard for the selected profile.
    if os.environ.get('CATROBOT_LIDAR_FRONT28_SIDE26', '0') == '1':
        return (('front_min_m', 0.28), ('left_min_m', 0.26), ('right_min_m', 0.26))
    if os.environ.get('CATROBOT_LIDAR_FRONT40_SIDE30', '0') == '1':
        return (('front_min_m', 0.40), ('left_min_m', 0.30), ('right_min_m', 0.30))
    if short_range:
        return (('front_min_m', 0.22), ('left_min_m', 0.22), ('right_min_m', 0.22))
    return (('front_min_m', 0.65), ('left_min_m', 0.42), ('right_min_m', 0.42))


def _obstacle_reason(scan, floor_mode=False, short_range=False):
    if not _fresh(scan):
        return None
    reason = str(scan.get('reason', ''))
    if reason.startswith(OBSTACLE_PREFIXES):
        return reason
    if scan.get('clear') is not True:
        return None
    if floor_mode:
        for field, limit in _floor_limits(short_range):
            measured = scan.get(field)
            if (isinstance(measured, (int, float)) and not isinstance(measured, bool)
                    and math.isfinite(measured) and measured < limit):
                return f'{field.upper()} FLOOR OBSTACLE: {measured:.2f}m (<{limit:.2f}m)'
    return None


def _can_rearm(scan, floor_mode=False, short_range=False):
    if not _fresh(scan) or scan.get('clear') is not True:
        return False
    if floor_mode:
        for field, limit in _floor_limits(short_range):
            measured = scan.get(field)
            if not (isinstance(measured, (int, float)) and not isinstance(measured, bool)
                    and math.isfinite(measured) and measured >= limit):
                return False
    return True


def start_obstacle_alert(robot, scan_reader, floor_mode=False, short_range=False):
    """One short double-beep per obstacle event while AUTO or MANUAL.

    Honors the ORIGINAL pattern_busy semaphore to avoid disturbing the user's
    existing H/1-5 buzzer controls. Never plays WAV/MP3 on obstacles.
    """
    if getattr(robot, '_lidar_obstacle_alert_started', False):
        return
    robot._lidar_obstacle_alert_started = True
    robot._lidar_obstacle_alert_active = False

    def worker():
        latched = False
        clear_since = None
        while True:
            time.sleep(0.12)
            cam = getattr(robot, 'camera', None)
            if cam is None or not getattr(cam, 'running', False):
                robot._lidar_obstacle_alert_active = False
                return
            with robot.lock:
                mode = robot.mode
            try:
                scan = scan_reader()
            except Exception as exc:
                scan = {'reason': 'SCAN ERROR: ' + repr(exc)}
            reason = _obstacle_reason(scan, floor_mode, short_range)
            obstacle = reason is not None
            robot._lidar_obstacle_alert_active = obstacle
            if mode not in ('MANUAL', 'AUTO'):
                latched = False
                clear_since = None
                continue
            if obstacle:
                clear_since = None
                if latched:
                    continue
                if getattr(robot, 'pattern_busy', None) is None:
                    print('[OBSTACLE BUZZER] No original buzzer pattern guard; STOP remains active', flush=True)
                    continue
                if robot.pattern_busy.is_set():
                    continue  # retry when current original user beep completes
                try:
                    # Existing pattern key 2 = short double beep, via original
                    # /Buzzer -> Docker driver. No additional ROS2 publisher.
                    robot.play_pattern(robot.motor, '2')
                    latched = True
                    print('[OBSTACLE BUZZER] ' + mode + ': ' + reason + ' -> pattern 2', flush=True)
                except Exception as exc:
                    print('[OBSTACLE BUZZER ERROR]', repr(exc), flush=True)
                continue
            if _can_rearm(scan, floor_mode, short_range):
                if clear_since is None:
                    clear_since = time.monotonic()
                elif time.monotonic() - clear_since >= 0.9:
                    latched = False
            else:
                clear_since = None

    threading.Thread(target=worker, daemon=True, name='lidar-obstacle-buzzer').start()
    print('[OBSTACLE BUZZER] READY: LiDAR obstacle -> original buzzer pattern 2; NEVER meow.wav', flush=True)

# CATROBOT_BUZZER_FRONT40_20261109: installed
# CATROBOT_LIDAR_22CM_OBSTACLE_MEOW_20261109: installed (legacy upgrade provenance)
# CATROBOT_LIDAR_360_INDEPENDENT_GUARD_20261109: installed

# CATROBOT_FRONT28_SIDE26_MEOW_TUNE_20261109: installed
