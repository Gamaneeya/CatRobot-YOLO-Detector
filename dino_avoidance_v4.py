"""Conservative, time-bounded 2D LiDAR avoidance and Dino reacquisition.

Experimental wheels-up only. No map, odometry, floor clearance or knowledge
whether a LiDAR return comes from Dino. NEVER publish directly to motors.
Every command is re-checked by the existing directional_permission gate.
"""
import math
from lidar_directional_avoidance import (fresh_complete, EMERGENCY_M,
                                         FRONT_STOP_M, SIDE_STOP_M, REAR_STOP_M,
                                         SWEEP_M)

LOOKAHEAD_M = 0.34
TOTAL_BUDGET_S = 27.0
MAX_BACKUP_S = 2.0
MAX_TURN_S = 2.3
MAX_PASS_S = 5.0
MAX_SEARCH_S = 3.5
MAX_ATTEMPTS = 1


class SafeRecoveryV4:
    def __init__(self):
        self.state = 'IDLE'
        self.note = 'ready'
        self.since = 0.0
        self.started = 0.0
        self.sign = 1.0
        self.attempts = 0
        self.last_finished = -float('inf')
        self._return_turn = False

    @property
    def active(self):
        return self.state not in ('IDLE', 'HALT')

    def _go(self, new, now, why):
        if self.state != new:
            print('[AVOIDANCE V4] {} -> {}: {}'.format(self.state, new, why), flush=True)
        self.state, self.since, self.note = new, now, why

    def reset(self):
        self.state = 'IDLE'
        self.note = 'mode reset'
        self.since = 0.0
        self.started = 0.0
        self.attempts = 0
        self._return_turn = False

    def abort(self, now, why):
        self._go('HALT', now, why)

    @staticmethod
    def _flanks(scan):
        return scan['avoid_flank_left_m'] >= SIDE_STOP_M and scan['avoid_flank_right_m'] >= SIDE_STOP_M

    def _sweep(self, scan):
        return (self._flanks(scan) and scan['circle_min_m'] > SWEEP_M
                and scan['avoid_front_m'] > SWEEP_M and scan['avoid_rear_m'] > SWEEP_M)

    def _reverse(self, scan):
        return (self._flanks(scan) and scan['avoid_rear_m'] > REAR_STOP_M + .025
                and scan['circle_min_m'] > EMERGENCY_M)

    def _forward(self, scan):
        return (self._flanks(scan) and scan['avoid_front_m'] > FRONT_STOP_M + .035
                and scan['circle_min_m'] > EMERGENCY_M)

    def plan(self, scan, v, w, now, mode, dino_recent):
        if mode != 'AUTO':
            self.reset()
            return v, w
        if not isinstance(now, (float,int)) or not math.isfinite(now):
            return 0.0, 0.0
        if not fresh_complete(scan):
            if self.active:
                self.abort(now, 'LiDAR stale or missing sector: stop')
            return 0.0, 0.0
        if scan['circle_min_m'] <= EMERGENCY_M:
            if self.active:
                self.abort(now, '22cm emergency: no automatic turning/reverse')
            return 0.0, 0.0
        if self.state == 'HALT':
            return 0.0, 0.0  # explicit mode switch resets HALT; no automatic retry loop
        if self.active and now - self.started > TOTAL_BUDGET_S:
            self.abort(now, 'total avoidance time exceeded')
            return 0.0, 0.0

        if self.state == 'IDLE':
            if not dino_recent or v <= 0.005 or now - self.last_finished < 3.0:
                return v, w
            if scan['avoid_front_m'] > LOOKAHEAD_M:
                return v, w
            self.started = now
            self.attempts += 1
            self.sign = 1.0 if scan['avoid_flank_left_m'] >= scan['avoid_flank_right_m'] else -1.0
            if self._sweep(scan):
                self._go('PAUSE', now, 'front in lookahead; choose guarded turn')
            elif self._reverse(scan):
                self._go('PAUSE', now, 'front in lookahead; make room by reversing straight')
            else:
                self.abort(now, 'no safe turning sweep or rear escape; operator must reposition')
            return 0.0, 0.0

        if self.state == 'PAUSE':
            if now-self.since < 0.40:
                return 0.0,0.0
            if (self._sweep(scan) and self._reverse(scan)
                    and scan['avoid_front_m'] <= FRONT_STOP_M + 0.020):
                self._go('REVERSE_ARC', now, 'guarded backward curve to create turning room')
            elif self._sweep(scan):
                self._go('TURN_OUT', now, 'clear sweep verified')
            elif self._reverse(scan):
                self._go('BACK_OUT', now, 'straight rear escape verified')
            else:
                self.abort(now, 'no escape after pause')
            return 0.0,0.0

        if self.state == 'REVERSE_ARC':
            if not self._sweep(scan) or not self._reverse(scan):
                self.abort(now, 'rear arc swept space closed')
                return 0.0,0.0
            if now-self.since >= 0.8:
                self._go('TURN_OUT', now, 'guarded reverse arc complete')
                return 0.0,0.0
            return -0.018,self.sign*0.045

        if self.state == 'BACK_OUT':
            if self._sweep(scan):
                self._go('TURN_OUT', now, 'room to turn recovered')
                return 0.0,0.0
            if not self._reverse(scan):
                self.abort(now, 'reverse path closed')
                return 0.0,0.0
            if now-self.since >= MAX_BACKUP_S:
                self.abort(now, 'reverse time budget exhausted; still no sweep')
                return 0.0,0.0
            return -0.020,0.0

        if self.state == 'TURN_OUT':
            if not self._sweep(scan):
                self.abort(now, 'turning sweep no longer clear')
                return 0.0,0.0
            if now-self.since >= MAX_TURN_S:
                self._go('ASSESS', now, 'outward turn complete')
                return 0.0,0.0
            return 0.0,self.sign*0.090

        if self.state == 'ASSESS':
            if self._forward(scan):
                self._go('PASS', now, 'forward corridor verified')
            else:
                self.abort(now, 'no verified corridor after outward turn')
            return 0.0,0.0

        if self.state == 'PASS':
            if not self._forward(scan):
                self.abort(now, 'bypass lane blocked')
                return 0.0,0.0
            if now-self.since >= MAX_PASS_S:
                self._go('TURN_BACK', now, 'limited forward bypass complete')
                return 0.0,0.0
            return 0.028,0.0

        if self.state == 'TURN_BACK':
            if not self._sweep(scan):
                self.abort(now, 'turn-back sweep obstructed')
                return 0.0,0.0
            if now-self.since >= MAX_TURN_S:
                self._go('REACQUIRE', now, 'look for Dino with camera still active')
                return 0.0,0.0
            return 0.0,-self.sign*0.090

        if self.state == 'REACQUIRE':
            if dino_recent and self._forward(scan):
                self._go('IDLE', now, 'Dino reacquired and forward path open; Arc Follow resumes')
                self.last_finished = now
                return 0.0,0.0
            if not self._sweep(scan):
                self.abort(now, 'no safe room to search')
                return 0.0,0.0
            if now-self.since >= MAX_SEARCH_S:
                self.abort(now, 'Dino not reacquired; operator required')
                return 0.0,0.0
            return 0.0, (self.sign if now-self.since < MAX_SEARCH_S/2 else -self.sign)*0.055

        self.abort(now, 'unknown avoidance state')
        return 0.0,0.0
