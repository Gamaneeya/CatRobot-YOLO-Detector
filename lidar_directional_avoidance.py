"""Optional, bounded CatRobot LiDAR manoeuvre/recovery V2.

NO camera, sound, servo, ROS2, or web UI modifications live here.
All commanded velocities still flow through RealMotor.send and DockerMotor.
A 2D LiDAR 13 cm above the floor cannot detect low objects or blind spots.
No safety claim is made for unattended floor use.
"""
import math
import re

FRONT_STOP_M = 0.28
SIDE_STOP_M = 0.26
REAR_STOP_M = 0.28
EMERGENCY_M = 0.22
# Robot footprint is 28 x 23 cm. With laser approximately 15 cm behind
# front bumper, farthest wheel/body corner is roughly 19 cm from laser.
# 25.5 cm is a conservative *planar test* clearance for the swept corners,
# rather than treating the rear straight-retreat threshold as turning limit.
# Not a certificate of floor-level safety: laser scans at 13 cm height.
SWEEP_M = 0.255
MAX_AGE_S = 0.40
MIN_POINTS_PER_BIN = 2

# Raw laser angles are pre-normalized to vehicle-front 0 degrees.
BINS = {
    'front': ((-40,-20),(-20,0),(0,20),(20,40)),
    'left': ((0,35),(35,70),(70,105)),
    'right': ((-105,-70),(-70,-35),(-35,0)),
    'rear': ((-180,-160),(-160,-140),(140,160),(160,180)),
    'front_left': ((0,20),(20,40)),
    'front_right': ((-40,-20),(-20,0)),
    'flank_left': ((40,70),(70,105)),
    'flank_right': ((-105,-70),(-70,-40)),
}


def _valid_number(x):
    return isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x)


def collect_directional(points):
    """Analyze one entire scan, including rear, *before* old early-return gates."""
    result = {'avoid_scan_valid': False}
    every_good = True
    for sector, bins in BINS.items():
        vals = []
        ready = True
        for low, high in bins:
            distances = [float(d) for a,d in points
                         if _valid_number(a) and _valid_number(d)
                         and low <= float(a) < high and 0.05 <= d <= 12.0]
            if len(distances) < MIN_POINTS_PER_BIN:
                ready = False
            vals.extend(distances)
        result['avoid_' + sector + '_m'] = round(min(vals), 3) if vals and ready else None
        result['avoid_' + sector + '_ready'] = ready
        if sector in ('front','left','right','rear'):
            every_good &= ready
    # A straight escape is permitted only if ALL emergency echoes lie in the
    # opposite end of the robot. 360 degree corner echoes can otherwise be
    # missed by front/side/rear overlapping display sectors.
    close_angles = [float(a) for a,d in points if _valid_number(a) and
                    _valid_number(d) and 0.05 <= d <= EMERGENCY_M]
    result['avoid_emergency_front_only'] = bool(close_angles) and all(abs(a) <= 40 for a in close_angles)
    result['avoid_emergency_rear_only'] = bool(close_angles) and all(abs(a) >= 140 for a in close_angles)
    result['avoid_scan_valid'] = bool(every_good)
    return result


def fresh_complete(scan):
    if not isinstance(scan, dict) or scan.get('avoid_scan_valid') is not True:
        return False
    age = scan.get('scan_age_s')
    if not _valid_number(age) or not 0 <= age <= MAX_AGE_S:
        return False
    reason = str(scan.get('reason', ''))
    if reason.startswith(('STALE', 'WAITING', 'LIDAR ERROR', 'LIDAR PROCESS',
                          'LIDAR NOT', 'CHECKING', 'INSUFFICIENT')):
        return False
    if not all(_valid_number(scan.get('avoid_' + s + '_m')) for s in ('front','left','right','rear')):
        return False
    if not _valid_number(scan.get('circle_min_m')):
        return False
    return True


def mode_ready(scan):
    """Mode entry demands healthy full LiDAR, not an empty path in every direction."""
    return fresh_complete(scan)


def directional_permission(scan, v, w, mode, floor_reverse_ok=False, allow_auto_reverse=False):
    """Return None to allow, else fail-closed reason. Zero is always allowed.

    Straight manual retreat can move *away* from an emergency object ahead.
    Manual reverse with steering may be allowed after checking the complete
    turning sweep and clear rear lane. AUTO never reverses.
    """
    if not _valid_number(v) or not _valid_number(w):
        return 'AVOID INVALID VELOCITY'
    if abs(v) < 1e-6 and abs(w) < 1e-6:
        return None
    if not fresh_complete(scan):
        return 'AVOID SCAN NOT VERIFIED'
    front = scan['avoid_front_m']
    rear = scan['avoid_rear_m']
    left = scan['avoid_left_m']
    right = scan['avoid_right_m']
    circle = scan['circle_min_m']
    if mode not in ('MANUAL','AUTO'):
        return 'AVOID INVALID MODE'
    if circle <= EMERGENCY_M:
        if abs(w) > 1e-6:
            return 'AVOID 22CM EMERGENCY: TURN LOCKED'
        if v < -1e-6 and scan.get('avoid_emergency_front_only') is not True:
            return 'AVOID 22CM EMERGENCY: REAR ESCAPE NOT PROVEN'
        if v > 1e-6 and scan.get('avoid_emergency_rear_only') is not True:
            return 'AVOID 22CM EMERGENCY: FRONT ESCAPE NOT PROVEN'
    if mode == 'AUTO' and v < -1e-6:
        if not allow_auto_reverse or not floor_reverse_ok:
            return 'AVOID AUTO REVERSE DISABLED (WHEELS-UP V4 ONLY)'
    if mode == 'MANUAL' and v < -1e-6 and not floor_reverse_ok:
        # This flag is true on wheels-up, or after explicit floor unlock.
        return 'AVOID FLOOR REVERSE LOCKED'
    turning = abs(w) >= 1e-6
    # Raw left/right sectors overlap the front. Straight retreat is permitted
    # away from a frontal emergency only when TRUE side flanks stay clear.
    flank_left = scan.get('avoid_flank_left_m')
    flank_right = scan.get('avoid_flank_right_m')
    if not (_valid_number(flank_left) and _valid_number(flank_right)):
        return 'AVOID FLANK COVERAGE MISSING'
    if flank_left < SIDE_STOP_M or flank_right < SIDE_STOP_M:
        return 'AVOID SIDE FLANK TOO CLOSE'
    if turning:
        # Turning (including a curved follow/reverse arc) sweeps body corners.
        # Require the entire 360-degree laser plane to exceed the estimated
        # body-corner clearance. This is separate from rear *translation* gate.
        if circle <= SWEEP_M:
            return 'AVOID TURN: SWEEP NOT CLEAR'
        if front <= SWEEP_M or rear <= SWEEP_M:
            return 'AVOID TURN: BODY CORNER TOO CLOSE'
        if v > 1e-6 and front < FRONT_STOP_M:
            return 'AVOID ARC FORWARD OBSTACLE'
        if v < -1e-6:
            if rear < REAR_STOP_M:
                return 'AVOID REAR OBSTACLE (REVERSE ARC)'
            if mode != 'MANUAL' and not (mode == 'AUTO' and allow_auto_reverse and floor_reverse_ok):
                return 'AVOID AUTO REVERSE DISABLED'
        return None
    if v > 1e-6 and front < FRONT_STOP_M:
        return 'AVOID FRONT OBSTACLE'
    if v < -1e-6 and rear < REAR_STOP_M:
        return 'AVOID REAR OBSTACLE'
    # Straight motion may move away from an object on the opposite end;
    # side minima must still remain clear (above).
    return None


class AvoidanceController:
    """Bounded turn, then short forward probe, then reacquire Dino.

    No pose estimation, mapping or full obstacle-circumnavigation guarantee.
    Stops/locks out after one failed attempt, requiring a mode reset.
    """
    def __init__(self):
        self.state = 'IDLE'
        self.note = 'not started'
        self.started = 0.0
        self.since = 0.0
        self.turn_sign = 0.0
        self.attempts = 0

    @property
    def active(self):
        return self.state not in ('IDLE', 'HALT')

    def _state(self, state, now, note):
        if state != self.state:
            print('[AVOIDANCE] {} -> {}: {}'.format(self.state,state,note), flush=True)
        self.state, self.since, self.note = state, now, note

    def reset(self):
        self.state = 'IDLE'
        self.note = 'mode changed'
        self.attempts = 0

    def abort(self, now, note):
        self._state('HALT', now, note)

    def plan(self, scan, v, w, now, mode, dino_recent):
        if mode != 'AUTO':
            self.reset()
            return v, w
        if self.state == 'HALT':
            return 0.0, 0.0
        if not fresh_complete(scan):
            if self.active:
                self.abort(now, 'LiDAR data not fully verified')
            return 0.0, 0.0
        front = scan['avoid_front_m']
        rear = scan['avoid_rear_m']
        left = scan['avoid_left_m']
        right = scan['avoid_right_m']
        emergency = scan['circle_min_m'] <= EMERGENCY_M
        if emergency:
            if self.active:
                self.abort(now, '22cm emergency: no automatic escape')
            return 0.0, 0.0
        if self.state == 'IDLE':
            if v <= 0.005 or front >= FRONT_STOP_M or not dino_recent:
                return v, w
            if (scan['circle_min_m'] <= SWEEP_M or
                    scan['avoid_flank_left_m'] < SIDE_STOP_M or
                    scan['avoid_flank_right_m'] < SIDE_STOP_M):
                self.abort(now, 'No verified room for a turning sweep')
                return 0.0, 0.0
            self.started = now
            self.attempts = 1
            # Positive yaw is conventional ROS2 CCW (left).
            self.turn_sign = 1.0 if left >= right else -1.0
            self._state('PAUSE', now, 'front obstacle, choose {} turn'.format('left' if self.turn_sign>0 else 'right'))
            return 0.0,0.0
        if now - self.started > 7.0:
            self.abort(now, 'time budget exhausted')
            return 0.0,0.0
        if self.state == 'PAUSE':
            if now - self.since >= 0.30:
                self._state('TURN', now, 'short, limited in-place turn')
            return 0.0,0.0
        if self.state == 'TURN':
            if (scan['circle_min_m'] <= SWEEP_M or
                    scan['avoid_flank_left_m'] < SIDE_STOP_M or
                    scan['avoid_flank_right_m'] < SIDE_STOP_M):
                self.abort(now, 'rotation sweep unsafe')
                return 0.0,0.0
            if now - self.since >= 1.8:
                self._state('ASSESS', now, 'turn complete: test route')
                return 0.0,0.0
            return 0.0, self.turn_sign * 0.10
        if self.state == 'ASSESS':
            if front >= FRONT_STOP_M + 0.02 and left >= SIDE_STOP_M + 0.01 and right >= SIDE_STOP_M + 0.01:
                self._state('PROBE', now, 'short straight path verified')
                return 0.0,0.0
            self.abort(now, 'route not sufficiently open after turn')
            return 0.0,0.0
        if self.state == 'PROBE':
            if front < FRONT_STOP_M + 0.02 or left < SIDE_STOP_M + 0.01 or right < SIDE_STOP_M + 0.01:
                self.abort(now, 'probe lane closed')
                return 0.0,0.0
            if now - self.since >= 1.50:
                self._state('REACQUIRE', now, 'probe complete: look for Dino')
                return 0.0,0.0
            return 0.035,0.0
        if self.state == 'REACQUIRE':
            if dino_recent and front >= FRONT_STOP_M + 0.02:
                self._state('IDLE', now, 'Dino visible again: Arc Follow resumes')
                return 0.0,0.0
            if now - self.since >= 1.2:
                self.abort(now, 'Dino not reacquired: stop for operator')
                return 0.0,0.0
            if (scan['circle_min_m'] <= SWEEP_M or
                    scan['avoid_flank_left_m'] < SIDE_STOP_M or
                    scan['avoid_flank_right_m'] < SIDE_STOP_M):
                self.abort(now, 'search turning space not verified')
                return 0.0,0.0
            # Slow, time-limited heading search only. No blind drive forward.
            return 0.0, self.turn_sign * 0.06
        self.abort(now, 'unknown avoidance state')
        return 0.0,0.0


def verified_dino(camera, detail, now):
    """Require recent, reasonable-confidence YOLO Dino before autonomous maneuver."""
    if camera is None or getattr(camera, '_autocenter_xy', None) is None:
        return False
    stamp = getattr(camera, '_autocenter_seen_at', 0.0)
    if not _valid_number(stamp) or not 0 <= now - stamp <= 0.65:
        return False
    match = re.search(r'Conf:\s*([0-9.]+)', str(detail))
    if not match:
        return False
    try:
        confidence = float(match.group(1))
    except (ValueError, TypeError, OverflowError):
        return False
    return _valid_number(confidence) and confidence >= 0.35

# CATROBOT_AVOIDANCE_V2_20261109: installed
# CATROBOT_AVOIDANCE_V4_AUTO_REVERSE_WHEELS_UP: installed
