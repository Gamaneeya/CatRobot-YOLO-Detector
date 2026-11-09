"""V6 opt-in, wheel-up-only planner; directional LiDAR gate still owns safety.

Never publishes directly to motors. State machine proposes v/w only, and
RealMotor.send calls directional_permission() before forwarding to ROS2.
No SLAM, odometry, floor-level collision detection, or guaranteed path.
"""
import math

from dino_avoidance_v5 import SafeRecoveryV5
from lidar_directional_avoidance import (
    EMERGENCY_M, FRONT_STOP_M, SIDE_STOP_M, SWEEP_M, fresh_complete,
)

TURN_W = 0.14
TURN_SEC = 3.0
REVERSE_V = -0.030
REVERSE_SEC = 1.05
PASS_V = 0.035
PASS_SEC = 4.0
STUCK_HOLD_SEC = 2.5
GOAL_MEMORY_SEC = 12.0


class SafeRecoveryV6(SafeRecoveryV5):
    def __init__(self):
        super().__init__()
        self.goal_seen_at = -float('inf')
        self.turned_from = None
        self.pass_from = None
        self.stuck_alerted = False

    def reset(self):
        super().reset()
        self.goal_seen_at = -float('inf')
        self.turned_from = None
        self.pass_from = None
        self.stuck_alerted = False

    def _go(self, new, now, why):
        previous = self.state
        if previous != new:
            print('[AVOIDANCE V6] {} -> {}: {}'.format(previous, new, why), flush=True)
        # Avoid V4/V5 output duplicates while retaining their state semantics.
        self.state, self.since, self.note = new, now, why
        if new == 'TURN_OUT' and previous != new:
            self.turned_from = None
        if new == 'PASS' and previous != new:
            self.pass_from = None
        if new == 'IDLE' and previous != new:
            self.stuck_alerted = False

    @staticmethod
    def _signature(scan):
        fields = ('avoid_front_m', 'avoid_rear_m',
                  'avoid_flank_left_m', 'avoid_flank_right_m',
                  'circle_min_m', 'circle_min_angle_deg')
        values = []
        for name in fields:
            val = scan.get(name)
            values.append(float(val) if isinstance(val, (int, float)) and
                          not isinstance(val, bool) and math.isfinite(val) else None)
        return tuple(values)

    @staticmethod
    def _geometry_changed(before, after):
        if before is None or after is None:
            return False
        for idx, (a, b) in enumerate(zip(before, after)):
            if a is None or b is None:
                continue
            difference = abs(a-b)
            if idx == 5:
                continue  # nearest-hit angle alone is not pose/motion proof
            if difference >= 0.025:
                return True
        return False

    def _room_to_resume(self, scan):
        """Hold through a scan-stable, directionally verified lane.

        Directional permission is checked again by RealMotor for actual v/w.
        """
        return (fresh_complete(scan) and scan['circle_min_m'] > SWEEP_M + .025
                and scan['avoid_front_m'] >= FRONT_STOP_M + .08
                and scan['avoid_rear_m'] >= SWEEP_M + .025
                and scan['avoid_flank_left_m'] >= SIDE_STOP_M + .025
                and scan['avoid_flank_right_m'] >= SIDE_STOP_M + .025)

    def navigation_sos_due(self, now):
        """SOS means attempted navigation is stuck, NOT LiDAR failure."""
        return (self.state == 'HALT'
                and isinstance(now, (int, float)) and math.isfinite(now)
                and now - self.since >= STUCK_HOLD_SEC
                and 0 <= now - self.goal_seen_at <= GOAL_MEMORY_SEC
                and not self.note.startswith(('22cm emergency', 'LiDAR stale',
                                              'LiDAR data', 'AVOID SCAN'))
                and not self.note.startswith(('AVOID 22CM', 'AVOID SCAN')))

    def plan(self, scan, v, w, now, mode, dino_recent):
        if mode != 'AUTO':
            self.reset()
            return v, w
        if not isinstance(now, (int, float)) or not math.isfinite(now):
            return 0.0, 0.0
        if dino_recent:
            self.goal_seen_at = now
        if not fresh_complete(scan):
            if self.active:
                self.abort(now, 'LiDAR stale or missing sector: stop')
            return 0.0, 0.0
        if scan['circle_min_m'] <= EMERGENCY_M:
            if self.active:
                self.abort(now, '22cm emergency: no automatic turning/reverse')
            return 0.0, 0.0

        # Hold the V5 alternate-search limit: a single attempt left and right.
        # Persistent no-corridor situations must STOP and request human help.
        if self.state == 'HALT':
            # Auto-resume after a stable, fully verified safe lane. This is
            # separate from route retries and NEVER clears emergency or
            # sensor-fault HALT without an operator mode reset.
            hard_latch = self.note.startswith((
                '22cm emergency', 'LiDAR stale', 'LiDAR data',
                'AVOID 22CM', 'AVOID SCAN'))
            if not hard_latch and dino_recent and self._room_to_resume(scan):
                if self.clear_since is None:
                    self.clear_since = now
                elif now-self.clear_since >= 1.2:
                    self._go('IDLE', now, 'verified lane clear; follow Dino again')
                    self.last_finished = now
                    self.retry_count = 0
                    self.clear_since = None
                return 0.0, 0.0
            self.clear_since = None
            # V5 only treats a few HALT notes as retryable. A V6 measured
            # no-progress stop is also eligible for the *one* alternate, but
            # never if LiDAR cannot prove safe rear translation + corner sweep.
            extra_retryable = self.note in (
                'no measurable scan change after turning; wheels-up cannot prove route',
                'no measured scan progress through bypass lane',
            )
            if (extra_retryable and self.retry_count < 1 and self._healthy(scan)
                    and self._reverse(scan) and self._sweep(scan)
                    and now-self.since >= 0.4 and now-self.started < 17.0):
                self.retry_count += 1
                self.sign *= -1.0
                self._go('BACKTRACK', now, 'no measured progress; try opposite side once')
                self.stuck_alerted = False
                return 0.0, 0.0
            before = self.state
            ans = super().plan(scan, v, w, now, mode, dino_recent)
            if self.state == 'HALT' and self.navigation_sos_due(now) and not self.stuck_alerted:
                print('[AVOIDANCE V6] NAVIGATION STUCK: {} | SOS requested; '
                      'LiDAR remains healthy but no verified route'.format(self.note), flush=True)
                self.stuck_alerted = True
            elif self.state != before:
                self.stuck_alerted = False
            return ans

        if self.active and now-self.started > 27.0:
            self.abort(now, 'avoidance time budget exceeded; operator required')
            return 0.0, 0.0

        if self.state in ('INITIAL_BACKUP', 'BACKTRACK'):
            if not self._healthy(scan) or not self._reverse(scan):
                self.abort(now, 'reverse path unsafe; operator required')
                return 0.0, 0.0
            if now-self.since < REVERSE_SEC:
                return REVERSE_V, 0.0
            if self._sweep(scan):
                self._go('TURN_OUT', now, 'guarded backup complete; check rotation geometry')
                return 0.0, 0.0
            if now-self.since < 1.5:
                return REVERSE_V, 0.0
            self.abort(now, 'no turning room after guarded backup')
            return 0.0, 0.0

        if self.state == 'TURN_OUT':
            if not self._healthy(scan) or not self._sweep(scan):
                self.abort(now, 'turning sweep no longer safe')
                return 0.0, 0.0
            if self.turned_from is None:
                self.turned_from = self._signature(scan)
            if now-self.since < TURN_SEC:
                return 0.0, self.sign*TURN_W
            if not self._geometry_changed(self.turned_from, self._signature(scan)):
                self.abort(now, 'no measurable scan change after turning; wheels-up cannot prove route')
                return 0.0, 0.0
            self._go('ASSESS', now, 'outward turn changed scan geometry; assess corridor')
            return 0.0, 0.0

        if self.state == 'PASS':
            if not self._healthy(scan) or not self._forward(scan):
                self.abort(now, 'bypass lane blocked')
                return 0.0, 0.0
            if self.pass_from is None:
                self.pass_from = self._signature(scan)
            if now-self.since < PASS_SEC:
                return PASS_V, 0.0
            if scan['avoid_front_m'] < 0.60 and not self._geometry_changed(self.pass_from, self._signature(scan)):
                self.abort(now, 'no measured scan progress through bypass lane')
                return 0.0, 0.0
            self._go('TURN_BACK', now, 'bounded bypass complete; turn toward Dino')
            return 0.0, 0.0

        if self.state == 'TURN_BACK':
            if not self._healthy(scan) or not self._sweep(scan):
                self.abort(now, 'turn-back sweep obstructed')
                return 0.0, 0.0
            if now-self.since < TURN_SEC:
                return 0.0, -self.sign*TURN_W
            self._go('REACQUIRE', now, 'turn back complete; keep camera tracking Dino')
            return 0.0, 0.0

        ans = super().plan(scan, v, w, now, mode, dino_recent)
        if self.state == 'HALT' and self.navigation_sos_due(now) and not self.stuck_alerted:
            print('[AVOIDANCE V6] NAVIGATION STUCK: {}'.format(self.note), flush=True)
            self.stuck_alerted = True
        if self.state == 'IDLE':
            # No terminal success latch. The original YOLO Arc Follow stays
            # live, and can pursue Dino again if its visual box shrinks.
            self.stuck_alerted = False
        return ans

# CATROBOT_V6_STUCK_SOS_PERSISTENT_DINO: installed
