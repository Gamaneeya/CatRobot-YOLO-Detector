"""Wheels-up-only V5 recovery on top of the existing bounded V4 planner.

Keeps the existing V4 safety gates and restores motion only in verified free
space. One initial low-speed reverse, one bounded alternate backtrack, then
halt. No map, odometry or ability to see low obstacles below the LiDAR plane.
"""

import math
from dino_avoidance_v4 import SafeRecoveryV4
from lidar_directional_avoidance import fresh_complete, EMERGENCY_M, SIDE_STOP_M, SWEEP_M


class SafeRecoveryV5(SafeRecoveryV4):
    def __init__(self):
        super().__init__()
        self.retry_count = 0
        self.retry_until = 0.0
        self.clear_since = None
        self._last_status = None

    def _go(self, new, now, why):
        if self.state != new:
            print('[AVOIDANCE V5] {} -> {}: {}'.format(self.state, new, why), flush=True)
        self.state, self.since, self.note = new, now, why

    def reset(self):
        super().reset()
        self.retry_count = 0
        self.retry_until = 0.0
        self.clear_since = None

    def _healthy(self, scan):
        return fresh_complete(scan) and scan['circle_min_m'] > EMERGENCY_M

    def _room_to_resume(self, scan):
        return (self._healthy(scan) and scan['avoid_front_m'] >= 0.43 and
                scan['avoid_rear_m'] >= 0.32 and
                scan['avoid_flank_left_m'] >= SIDE_STOP_M + 0.03 and
                scan['avoid_flank_right_m'] >= SIDE_STOP_M + 0.03 and
                scan['circle_min_m'] >= 0.32)

    def plan(self, scan, v, w, now, mode, dino_recent):
        if mode != 'AUTO':
            self.reset()
            return v, w
        if not isinstance(now, (int, float)) or not math.isfinite(now):
            return 0.0, 0.0
        # Do not reactivate after a sensor fault or 22cm emergency. Such
        # faults require the human to select a new mode after resolving them.
        if self.state == 'HALT':
            retryable = self.note in (
                'bypass lane blocked',
                'no verified corridor after outward turn',
                'turn-back sweep obstructed',
            )
            if retryable and self._room_to_resume(scan) and dino_recent:
                if self.clear_since is None:
                    self.clear_since = now
                elif now - self.clear_since >= 1.2:
                    self._go('IDLE', now, 'verified clear for 1.2s; follow can resume')
                    self.last_finished = now
                    self.retry_count = 0
                    self.clear_since = None
                return 0.0, 0.0
            self.clear_since = None
            if (retryable and self.retry_count < 1 and self._healthy(scan)
                    and now - self.since >= 0.4 and
                    now - self.started < 17.0 and
                    self._reverse(scan) and self._sweep(scan)):
                self.retry_count += 1
                self.sign *= -1.0
                self._go('BACKTRACK', now, 'reversing a short distance; retry other side once')
            return 0.0, 0.0

        if self.state in ('INITIAL_BACKUP', 'BACKTRACK'):
            if not self._healthy(scan) or not self._reverse(scan):
                self.abort(now, 'reverse path unsafe; operator required')
                return 0.0, 0.0
            duration = 0.6 if self.state == 'INITIAL_BACKUP' else 0.7
            if now - self.since < duration:
                return -0.020, 0.0
            if self._sweep(scan):
                self._go('TURN_OUT', now, 'backup complete; verified turning sweep')
                return 0.0, 0.0
            if now - self.since < 1.2:
                return -0.020, 0.0
            self.abort(now, 'still no turning room after guarded backup')
            return 0.0, 0.0

        # V4 chooses TURN_OUT straightaway if a sweep is possible. In a
        # cramped front approach, a short reverse creates room first, but only
        # when rear/flanks are verified clear. Never reverse at <=22 cm.
        if (self.state == 'PAUSE' and now - self.since >= 0.4 and
                self.retry_count == 0 and self._healthy(scan) and
                scan['avoid_front_m'] <= 0.34 and self._reverse(scan)):
            self._go('INITIAL_BACKUP', now, 'front close; guarded straight reverse first')
            return 0.0, 0.0
        return super().plan(scan, v, w, now, mode, dino_recent)
