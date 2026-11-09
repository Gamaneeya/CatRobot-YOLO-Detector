"""ROSMASTER M1 Dino tracking V3: optional parallel camera/drive follow.

Original camera-first mode is preserved unless CATROBOT_MOVE_WHILE_CENTERING=1.
Single original RealMotor.send/servo path; no new ROS2/USB/serial writers.
"""
import math
import os
import threading
import time

# Positions are normalized to frame width/height; the actual optical image centre
# is (0.5, 0.5), NOT merely the horizontal image centre.
CENTER_ENTER_X = 0.055
CENTER_ENTER_Y = 0.065
CENTER_EXIT_X = 0.085
CENTER_EXIT_Y = 0.095
PAN_NEUTRAL_TOL_DEG = 4
PAN_STEP_DEG = 2
TILT_STEP_DEG = 2
SERVO_PERIOD_S = 0.18
DETECTION_MAX_AGE_S = 0.45
SERVO_SETTLE_S = 0.22
BASE_ALIGN_SPEED = 0.10
MAX_SPEED_DELTA_PER_FRAME = 0.020
MAX_TURN_DELTA_PER_FRAME = 0.055

# V3 parallel mode. These never replace the existing LiDAR/web/motor safety.
PARALLEL_X_FORWARD_LIMIT = 0.33
PARALLEL_Y_FORWARD_LIMIT = 0.30
PARALLEL_PAN_FORWARD_LIMIT_DEG = 20.0
PARALLEL_MAX_YAW = 0.12
PARALLEL_STEER_PAN_PER_X = 10.0


def _sign(name, default):
    value = os.environ.get(name, default)
    if value not in ('1', '-1'):
        raise RuntimeError(name + ' must be 1 or -1')
    return int(value)


def _slew(previous, target, max_step):
    if not math.isfinite(target) or target == 0.0:
        return 0.0  # Emergency/stale/obstacle stop is NEVER ramped.
    if previous * target < 0:
        return 0.0  # Do not instantly reverse angular direction.
    return max(previous - max_step, min(previous + max_step, target))



def _v6_close_hold(cam, area, cx, cy, stamp, threshold):
    """Image-only arrival latch. Motor/LiDAR checks remain in RealMotor.send.

    Stop forward motion as soon as the Dino appears large; do not resume until
    four DISTINCT fresh YOLO frames show its box is clearly smaller. Do NOT
    interpret visual box area as a metric range measurement.
    """
    if not (math.isfinite(area) and 0.0 < threshold < 1.0 and math.isfinite(stamp)):
        return True, 'PARALLEL: INVALID ARRIVAL MEASUREMENT - STOP'
    latched = bool(getattr(cam, '_v6_close_hold', False))
    if area >= threshold:
        cam._v6_close_hold = True
        cam._v6_departure_frames = 0
        cam._v6_departure_stamp = -1.0
        centered = abs(cx - 0.5) <= CENTER_EXIT_X and abs(cy - 0.5) <= CENTER_EXIT_Y
        return True, ('PARALLEL: ARRIVED CLOSE + CENTERED - STOP FOR meow.wav'
                      if centered else 'PARALLEL: CLOSE BOX, CAMERA ALIGN ONLY - STOP')
    if latched:
        if area <= threshold * 0.68:
            if stamp != getattr(cam, '_v6_departure_stamp', -1.0):
                cam._v6_departure_stamp = stamp
                cam._v6_departure_frames = min(4, getattr(cam, '_v6_departure_frames', 0) + 1)
            if cam._v6_departure_frames >= 4:
                cam._v6_close_hold = False
                cam._v6_departure_frames = 0
                cam._v6_departure_stamp = -1.0
                print('[DINO ARRIVAL V6] Dino box smaller for 4 fresh frames; FOLLOW may resume', flush=True)
                return False, 'PARALLEL: DINO MOVED AWAY - FOLLOW'
        else:
            cam._v6_departure_frames = 0
            cam._v6_departure_stamp = -1.0
        return True, 'PARALLEL: ARRIVAL HOLD; WAIT CONFIRMED SMALLER DINO BOX'
    return False, 'PARALLEL: FOLLOW DINO'


def choose_motion(robot, cam, pan, original_follow, area, allow_base, base_sign,
                  previous_v=0.0, previous_w=0.0):
    """Side-effect-free drive suggestion; real LiDAR and web gates remain downstream."""
    now = time.monotonic()
    xy = getattr(cam, '_autocenter_xy', None)
    stamp = getattr(cam, '_autocenter_seen_at', 0.0)
    if xy is None or stamp <= 0 or stamp > now or now-stamp > DETECTION_MAX_AGE_S:
        cam._dino_centered_latch = False
        return 0.0, 0.0, 'DINO NOT FRESH - STOP'
    cx, cy = xy
    if not all(math.isfinite(z) for z in (cx, cy, area)) or not (0 <= cx <= 1 and 0 <= cy <= 1):
        cam._dino_centered_latch = False
        return 0.0, 0.0, 'INVALID DINO LOCATION - STOP'
    if area >= robot.SIM_STOP_AREA_RATIO:
        return 0.0, 0.0, 'BOX SIZE LIMIT - STOP'
    if not allow_base:
        return 0.0, 0.0, 'SERVO ONLY - WHEELS LOCKED'
    # Both axes must be centered before ANY wheel motion. Hysteresis avoids
    # oscillating stop/forward due to one-pixel prediction jitter.
    centered = bool(getattr(cam, '_dino_centered_latch', False))
    xlim = CENTER_EXIT_X if centered else CENTER_ENTER_X
    ylim = CENTER_EXIT_Y if centered else CENTER_ENTER_Y
    if abs(cx-0.5) > xlim or abs(cy-0.5) > ylim:
        cam._dino_centered_latch = False
        return 0.0, 0.0, 'CENTERING PAN AND TILT - STOP'
    cam._dino_centered_latch = True
    if now - getattr(cam, '_autocenter_last_servo_at', -100) < SERVO_SETTLE_S:
        return 0.0, 0.0, 'WAIT CAMERA TO SETTLE - STOP'

    # A pointed camera can be looking sideways even when the Dino is centered.
    # Yaw the base to bring camera pan back towards its neutral position.
    delta_pan = float(pan) - float(robot.PAN_CENTER)
    if abs(delta_pan) > PAN_NEUTRAL_TOL_DEG:
        w = math.copysign(BASE_ALIGN_SPEED, delta_pan) * base_sign
        return 0.0, _slew(previous_w, w, MAX_TURN_DELTA_PER_FRAME), 'ALIGNING BASE TO CAMERA'

    # Camera is looking straight ahead and target is centered in X AND Y.
    v, _, action = original_follow(cx, area)
    if v <= 0:
        return 0.0, 0.0, action
    return _slew(previous_v, v, MAX_SPEED_DELTA_PER_FRAME), 0.0, 'CAMERA CENTERED - FOLLOW FORWARD'



def choose_parallel_motion(robot, cam, pan, tilt, area, allow_base, base_sign,
                           pan_sign, tilt_sign, previous_v=0.0, previous_w=0.0):
    """Blend forward + yaw while servo worker independently centers X and Y.

    Outputs are suggestions only: the existing motor.send performs LiDAR,
    heartbeat, mode and ROS2 checks before publishing to the wheel driver.
    """
    now = time.monotonic()
    xy = getattr(cam, '_autocenter_xy', None)
    stamp = getattr(cam, '_autocenter_seen_at', 0.0)
    if xy is None or stamp <= 0 or stamp > now or now - stamp > DETECTION_MAX_AGE_S:
        return 0.0, 0.0, 'PARALLEL: DINO NOT FRESH - STOP'
    cx, cy = xy
    if (not all(math.isfinite(z) for z in (cx, cy, area, float(pan), float(tilt)))
            or not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 <= area <= 1)):
        return 0.0, 0.0, 'PARALLEL: INVALID TARGET - STOP'
    if (os.environ.get('CATROBOT_V6_ASSISTED_HELP') == '1' and
            os.environ.get('CATROBOT_DINO_CLOSE_MEOW') == '1'):
        hold, hold_action = _v6_close_hold(cam, area, cx, cy, stamp, robot.SIM_STOP_AREA_RATIO)
        if hold:
            return 0.0, 0.0, hold_action
    if area >= robot.SIM_STOP_AREA_RATIO:
        return 0.0, 0.0, 'PARALLEL: BOX SIZE LIMIT - STOP'
    if not allow_base:
        return 0.0, 0.0, 'PARALLEL: SERVO ONLY - WHEELS LOCKED'

    xerr = cx - 0.5
    yerr = cy - 0.5
    pan_offset = float(pan) - float(robot.PAN_CENTER)

    # The servo worker's pan direction is already calibrated using pan_sign.
    # Steer body toward the pan offset, with a small image-error feed-forward,
    # so the robot does not have to wait for perfect camera centering.
    estimated_offset = pan_offset + pan_sign * xerr * PARALLEL_STEER_PAN_PER_X
    if abs(estimated_offset) < 2.0:
        target_w = 0.0
    else:
        turn_size = min(PARALLEL_MAX_YAW, 0.022 + 0.004 * abs(estimated_offset))
        target_w = math.copysign(turn_size, estimated_offset * base_sign)

    # ARC FOLLOW: do not force a turn-in-place just because the Dino is off-centre.
    # The camera worker keeps centering X/Y independently while both wheel
    # velocities can be nonzero. Hard stops remain for lost/stale detections,
    # oversized boxes, tilt physical limits, and the downstream LiDAR/web gate.

    # If camera has physically reached its tilt bound while still looking far
    # from the Dino vertically, do NOT proceed forward without visual centering.
    if abs(yerr) > CENTER_EXIT_Y:
        requested_step = tilt_sign * (1 if yerr > 0 else -1) * TILT_STEP_DEG
        desired_tilt = float(tilt) + requested_step
        if not robot.TILT_RANGE[0] <= desired_tilt <= robot.TILT_RANGE[1]:
            return 0.0, 0.0, 'PARALLEL: TILT PHYSICAL LIMIT - STOP'

    # Reduce approach speed while turning/centering; never use box area as an
    # invented metric distance. The original box hard-stop still applies.
    # Slow down for a tighter arc, but keep a positive forward target when
    # the Dino is near an image edge. The image itself has no metric depth.
    alignment_fraction = max(abs(xerr) / 0.50,
                             abs(yerr) / 0.50,
                             abs(pan_offset) / max(1.0, float(robot.PAN_RANGE[1] - robot.PAN_CENTER)))
    alignment_factor = max(0.50, 1.0 - 0.50 * min(1.0, alignment_fraction))
    stop_area = float(robot.SIM_STOP_AREA_RATIO)
    if area <= stop_area * 0.55:
        area_factor = 1.0
    else:
        area_factor = max(0.20, (stop_area - area) / (stop_area * 0.45))
    target_v = max(0.0, float(robot.SIM_FORWARD_SPEED)) * alignment_factor * area_factor
    v = _slew(previous_v, target_v, MAX_SPEED_DELTA_PER_FRAME)
    w = _slew(previous_w, target_w, MAX_TURN_DELTA_PER_FRAME)
    return v, w, 'ARC: DRIVE + TURN + CAMERA CENTERING'


def start_auto_center(robot, wheels_up_mode=False):
    if os.environ.get('CATROBOT_AUTO_CENTER', '0') != '1':
        print('[AUTO CENTER] DISABLED (old controls unchanged)', flush=True)
        return
    if getattr(robot, '_dino_autocenter_running', False):
        return
    if robot.motor is None or robot.camera is None or not callable(getattr(robot.motor, 'servo', None)):
        raise RuntimeError('AUTO CENTER requires the existing RealMotor.servo and live camera')

    allow_base = os.environ.get('CATROBOT_CENTER_BASE', '0') == '1'
    move_parallel = os.environ.get('CATROBOT_MOVE_WHILE_CENTERING', '0') == '1'
    # Pre-calibration base rotation is intentionally limited to wheels-up.
    if allow_base and not wheels_up_mode and os.environ.get('CATROBOT_FLOOR_FOLLOW_UNLOCKED', '0') != '1':
        raise RuntimeError('BASE ALIGN floor mode is locked. Calibrate on wheels-up first, then explicitly unlock.')
    pan_sign = _sign('CATROBOT_PAN_RIGHT_SIGN', '1')
    tilt_sign = _sign('CATROBOT_TILT_DOWN_SIGN', '1')
    base_sign = _sign('CATROBOT_BASE_SIGN', '-1')
    robot._dino_autocenter_running = True

    existing_follow = robot.simulate_follow
    existing_send = robot.motor.send
    drive_state = {'v': 0.0, 'w': 0.0, 'report': 0.0}
    gate = {'mode': None, 'time': time.monotonic()}

    def guarded_send(v, w, expected_mode=None):
        with robot.lock:
            current_mode = robot.mode
            detection_at = robot.follow['at']
        if gate['mode'] != current_mode:
            gate['mode'] = current_mode
            gate['time'] = time.monotonic()
            drive_state['v'] = drive_state['w'] = 0.0
        if current_mode == 'AUTO' and (not allow_base or detection_at <= gate['time']):
            v = w = 0.0
        return existing_send(v, w, expected_mode=expected_mode)

    robot.motor.send = guarded_send

    def camera_first_follow(cx, area):
        with robot.lock:
            active_mode = robot.mode
        if active_mode != 'AUTO':
            robot.camera._dino_centered_latch = False
            robot.camera._v6_close_hold = False
            robot.camera._v6_departure_frames = 0
            robot.camera._v6_departure_stamp = -1.0
            drive_state['v'] = drive_state['w'] = 0.0
            return existing_follow(cx, area)
        cam = robot.camera
        if move_parallel and not getattr(getattr(robot.motor, 'backend', None), 'servo_ready', False):
            v, w, action = 0.0, 0.0, 'PARALLEL: SERVO BRIDGE NOT READY - STOP'
        elif move_parallel:
            v, w, action = choose_parallel_motion(
                robot, cam, robot.motor.pan, robot.motor.tilt, area,
                allow_base, base_sign, pan_sign, tilt_sign,
                drive_state['v'], drive_state['w'])
        else:
            v, w, action = choose_motion(
                robot, cam, robot.motor.pan, existing_follow, area,
                allow_base, base_sign, drive_state['v'], drive_state['w'])
        drive_state['v'], drive_state['w'] = v, w
        if time.monotonic() - drive_state['report'] > 0.85:
            xy = getattr(cam, '_autocenter_xy', None)
            print(f'[AUTO CENTER] {action} | xy={xy} pan={robot.motor.pan} '
                  f'tilt={robot.motor.tilt} v={v:+.3f} w={w:+.3f}', flush=True)
            drive_state['report'] = time.monotonic()
        return v, w, action

    robot.simulate_follow = camera_first_follow

    def servo_worker():
        last_served_frame = 0.0
        while getattr(robot.camera, 'running', False):
            time.sleep(SERVO_PERIOD_S)
            cam = robot.camera
            stamp = getattr(cam, '_autocenter_seen_at', 0.0)
            xy = getattr(cam, '_autocenter_xy', None)
            now = time.monotonic()
            if xy is None or stamp <= last_served_frame or stamp > now or now-stamp > DETECTION_MAX_AGE_S:
                continue
            last_served_frame = stamp
            cx, cy = xy
            if not (math.isfinite(cx) and math.isfinite(cy)):
                continue
            try:
                # Existing io_lock is an RLock on real ROSMASTER M1.
                with robot.motor.io_lock:
                    with robot.lock:
                        if robot.mode != 'AUTO':
                            continue
                        if time.monotonic() - getattr(cam, '_autocenter_seen_at', 0.0) > DETECTION_MAX_AGE_S:
                            continue
                        pan = int(robot.motor.pan)
                        tilt = int(robot.motor.tilt)
                    # Don't repeatedly send servo instructions for stale YOLO frames.
                    if abs(cx - 0.5) > CENTER_ENTER_X:
                        desired = pan + pan_sign * (1 if cx > 0.5 else -1) * PAN_STEP_DEG
                        desired = max(robot.PAN_RANGE[0], min(robot.PAN_RANGE[1], desired))
                        if desired != pan:
                            robot.motor.servo(robot.PAN_ID, desired)
                            cam._autocenter_last_servo_at = time.monotonic()
                    if abs(cy - 0.5) > CENTER_ENTER_Y:
                        desired = tilt + tilt_sign * (1 if cy > 0.5 else -1) * TILT_STEP_DEG
                        desired = max(robot.TILT_RANGE[0], min(robot.TILT_RANGE[1], desired))
                        if desired != tilt:
                            robot.motor.servo(robot.TILT_ID, desired)
                            cam._autocenter_last_servo_at = time.monotonic()
            except Exception as exc:
                print('[AUTO CENTER SERVO ERROR]', repr(exc), flush=True)

    threading.Thread(target=servo_worker, name='dino-auto-pan-tilt', daemon=True).start()
    if move_parallel:
        print('[AUTO CENTER] V3 ARC DRIVE + TURN + CAMERA ACTIVE; '
              'LiDAR and web heartbeat gates unchanged', flush=True)
    print('[AUTO CENTER] SERVO ACTIVE | PAN + TILT -> optical center (0.5, 0.5) | '
          + ('BASE ENABLED - CHECK SAFETY' if allow_base else 'SERVO ONLY, ALL WHEELS LOCKED'), flush=True)

# CATROBOT_PARALLEL_FOLLOW_V3_20261108: installed

# CATROBOT_ARC_FOLLOW_V3_FIX_20261108: installed

# CATROBOT_V6_FLOW25_ARRIVAL_20261109: image-area arrival latch 4 fresh far-box frames; original Servo and motion gate kept
