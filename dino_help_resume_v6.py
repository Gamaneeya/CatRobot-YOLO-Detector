"""Opt-in V6 manual-relocation assistance, WHEELS-UP TEST ONLY.

No automated obstacle circumvention, no direct ROS2 calls, no IMU/ground-contact
inference. AUTO remains selected but wheels are commanded zero in WAIT_HELP.
Resuming after 2.5 seconds of fresh 360 LiDAR clearance is only a functional
wheels-up test: it is NOT proof the robot has been put down on the floor.
"""
import math
import re
from lidar_directional_avoidance import fresh_complete, FRONT_STOP_M, SIDE_STOP_M, SWEEP_M, EMERGENCY_M, directional_permission

STOP_AHEAD_M = 0.36  # 2cm earlier AUTO forward lookahead; LiDAR-origin distance.
RESUME_FRONT_FORWARD_M = 0.37  # 1cm forward rearm hysteresis above new 37cm AUTO stop.
CLEAR_FRONT_M = 0.29
CLEAR_REAR_M = 0.29
CLEAR_FLANK_M = 0.26
CLEAR_CIRCLE_M = 0.26
CLEAR_SECONDS = 2.5
CLEAR_DISTINCT_SCANS = 6
SOS_DELAY_SECONDS = 0.55


class HumanHelpV6:
    def __init__(self):
        self.state = 'IDLE'
        self.note = 'follow Dino; V6 assisted demonstration'
        self.since = 0.0
        self.clear_since = None
        self.clear_scans = 0
        self.last_scan_count = None
        self.wait_event = 0
        self._last_diag = -float('inf')

    @property
    def active(self):
        # Deliberately keep the original AUTO control loop checking LiDAR even
        # when YOLO times out. WAIT_HELP always returns 0,0.
        return self.state == 'WAIT_HELP'

    def reset(self):
        self.state = 'IDLE'
        self.note = 'mode changed'
        self.clear_since = None
        self.clear_scans = 0
        self.last_scan_count = None

    def abort(self, now, why):
        self._wait(now, why)

    def _wait(self, now, why):
        if self.state != 'WAIT_HELP':
            self.wait_event += 1
            print('[HELP V6] IDLE -> WAIT_HELP: {}; motor=0; SOS once'.format(why), flush=True)
        self.state = 'WAIT_HELP'
        self.note = str(why)
        self.since = now
        self._clear_reset()

    def _clear_reset(self):
        self.clear_since = None
        self.clear_scans = 0
        self.last_scan_count = None

    def navigation_sos_due(self, now):
        return (self.state == 'WAIT_HELP' and isinstance(now, (int, float)) and
                math.isfinite(now) and now - self.since >= SOS_DELAY_SECONDS)

    @staticmethod
    def _clear_blocker(scan):
        if not fresh_complete(scan):
            return 'LiDAR scan stale/incomplete'
        for field, limit in (
            ('circle_min_m', CLEAR_CIRCLE_M),
            ('avoid_front_m', CLEAR_FRONT_M),
            ('avoid_rear_m', CLEAR_REAR_M),
            ('avoid_flank_left_m', CLEAR_FLANK_M),
            ('avoid_flank_right_m', CLEAR_FLANK_M),
            ('avoid_left_m', CLEAR_FLANK_M),
            ('avoid_right_m', CLEAR_FLANK_M),
        ):
            value = scan.get(field)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                return '{} missing/unverified'.format(field)
            if value < limit:
                return '{}={:.3f}m below {:.3f}m'.format(field, value, limit)
        return None

    @staticmethod
    def _motion_rearm_blocker(scan, v):
        # The requested 29 cm is a stationary rearm clearance threshold, not
        # permission to surge forward. The new 36 cm lookahead that
        # ENTERS WAIT_HELP must not be undercut on the next control cycle.
        if v > 0.005:
            minimum = RESUME_FRONT_FORWARD_M
            if scan['avoid_front_m'] < minimum:
                return 'forward clearance {:.3f}m below {:.3f}m (36cm stop hysteresis)'.format(
                    scan['avoid_front_m'], minimum)
        return None

    def _report_wait(self, now, blocker, scan, dino_recent, v, w):
        if now - self._last_diag >= 2.0:
            print('[HELP WAIT DIAG] reason={} fresh_scans={} elapsed={:.1f}s dino={} '
                  'front={} rear={} flankL={} flankR={} circle={} requested=({:+.3f},{:+.3f})'
                  .format(blocker, self.clear_scans,
                          max(0.0, now - self.clear_since) if self.clear_since is not None else 0.0,
                          bool(dino_recent), scan.get('avoid_front_m'),
                          scan.get('avoid_rear_m'), scan.get('avoid_flank_left_m'),
                          scan.get('avoid_flank_right_m'), scan.get('circle_min_m'), v, w), flush=True)
            self._last_diag = now


    def plan(self, scan, v, w, now, mode, dino_recent):
        if mode != 'AUTO':
            self.reset()
            return v, w
        if not isinstance(now, (int, float)) or not math.isfinite(now):
            return 0.0, 0.0
        if self.state == 'WAIT_HELP':
            blocker = self._clear_blocker(scan)
            if blocker is None:
                blocker = self._motion_rearm_blocker(scan, v)
            if blocker is not None:
                self._clear_reset()
                self._report_wait(now, blocker, scan, dino_recent, v, w)
                return 0.0, 0.0
            count = scan.get('scan_count')
            if not isinstance(count, int) or isinstance(count, bool):
                self._clear_reset()
                self._report_wait(now, 'missing scan counter', scan, dino_recent, v, w)
                return 0.0, 0.0
            if self.last_scan_count is not None and count < self.last_scan_count:
                self._clear_reset()
                self._report_wait(now, 'LiDAR scan counter reset', scan, dino_recent, v, w)
                return 0.0, 0.0
            if count != self.last_scan_count:
                if self.clear_since is None:
                    self.clear_since = now
                    print('[HELP V6] CLEAR CANDIDATE: check new scan data for 2.5 seconds (WHEELS-UP ONLY)',flush=True)
                self.last_scan_count = count
                self.clear_scans += 1
            elapsed = now-self.clear_since if self.clear_since is not None else 0.0
            if elapsed < CLEAR_SECONDS or self.clear_scans < CLEAR_DISTINCT_SCANS:
                self._report_wait(now, 'waiting for fresh full-lane clearance', scan, dino_recent, v, w)
                return 0.0, 0.0
            if not dino_recent:
                self._report_wait(now, 'LiDAR verified; waiting for confirmed Dino', scan, dino_recent, v, w)
                return 0.0, 0.0
            # 29cm front/rear and 26cm side/360 stationary rearm requirements;
            # a forward command also needs >=37cm to avoid immediate reentry
            # into the new 36cm lookahead. All real motor/turn gates apply.
            if abs(v) > 1e-6 or abs(w) > 1e-6:
                denied = directional_permission(scan,v,w,'AUTO',floor_reverse_ok=True,allow_auto_reverse=False)
                if denied is not None:
                    self._report_wait(now, 'requested motion blocked: '+denied, scan, dino_recent, v, w)
                    return 0.0, 0.0
            self.state = 'IDLE'
            self.note = 'fresh directional lane verified; follow Dino again'
            self._clear_reset()
            print('[HELP V6] WAIT_HELP -> IDLE: new scans + directional gate verified; SOS disarmed; follow Dino again', flush=True)
            return 0.0, 0.0  # zero-velocity transition frame.
        if not fresh_complete(scan):
            return 0.0, 0.0
        if not dino_recent:
            return 0.0, 0.0
        # Do not initiate navigation help merely because vision is centered
        # and the robot is stopped at its target (meow arrival case).
        approaching = float(v) > 0.005
        steering = abs(float(w)) > 0.01
        if approaching and scan['avoid_front_m'] < STOP_AHEAD_M:
            self._wait(now, 'front {:.3f}m < {:.2f}m lookahead'.format(scan['avoid_front_m'], STOP_AHEAD_M))
            return 0.0, 0.0
        if steering and (scan['circle_min_m'] <= SWEEP_M or
                         scan['avoid_flank_left_m'] < SIDE_STOP_M or
                         scan['avoid_flank_right_m'] < SIDE_STOP_M):
            self._wait(now, 'turn corridor blocked; no autonomous reverse')
            return 0.0, 0.0
        if (approaching or steering) and scan['circle_min_m'] <= EMERGENCY_M:
            self._wait(now, '22cm emergency; human assistance required')
            return 0.0, 0.0
        return v, w

# CATROBOT_V6_STABILITY_20261109: directional rearm, freshness and verification diagnostics
# CATROBOT_V6_AUTOSOS36_20261109: AUTO approach 36cm, forward rearm 37cm; static HELP 29/26cm and motor gates unchanged

def verified_follow_dino(camera, detail, now, min_conf=0.25, confirmed_frames=2):
    """Require a recent, *same current* YOLO result and two consecutive frames.

    Same confidence policy as the live camera selection. Never fabricate a
    motor command if YOLO's current follow request is zero or absent.
    """
    if camera is None or getattr(camera, '_autocenter_xy', None) is None:
        return False
    stamp = getattr(camera, '_autocenter_seen_at', 0.0)
    if not isinstance(stamp, (int,float)) or not math.isfinite(stamp) or not 0 <= now - stamp <= 0.45:
        return False
    if getattr(camera, 'verified_frames', 0) < confirmed_frames:
        return False
    match = re.search(r'Conf:\s*([0-9.]+)', str(detail))
    if match is None:
        return False
    try:
        conf = float(match.group(1))
    except (ValueError, OverflowError):
        return False
    return math.isfinite(conf) and min_conf <= conf <= 1.0
