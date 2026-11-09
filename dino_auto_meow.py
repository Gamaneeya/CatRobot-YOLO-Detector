"""Six ORIGINAL meow variants, triggered ONLY by recently verified YOLO Dino.

No obstacle sounds. The six bins below follow apparent YOLO box size in pixels
(share of image), NOT metric distance. Refine with camera-range calibration.
"""
import math
import os
import re
import threading
import time

# Apparent target area, not meters. Small Dino -> long/high; large -> short.
AREA_VOICES = (
    (0.012, '9', 'High long meow', 5.2),
    (0.025, '8', 'Long meow', 4.4),
    (0.050, 'm', 'Meow', 3.6),
    (0.085, '6', 'High meow', 3.0),
    (0.140, '7', 'Short meow', 2.4),
    (float('inf'), '0', 'High short meow', 2.0),
)

# Tuned for the observed LIVE Dino box areas (~1.5%-5.4%). These are
# relative image sizes, NOT LiDAR or camera distance in centimeters.
AREA_VOICES_FRONT28 = (
    (0.010, '9', 'High long meow', 5.2),
    (0.020, '8', 'Long meow', 4.4),
    (0.032, 'm', 'Meow', 3.6),
    (0.045, '6', 'High meow', 3.0),
    (0.060, '7', 'Short meow', 2.4),
    (float('inf'), '0', 'High short meow', 2.0),
)

_DETAIL = re.compile(r'Box area:\s*([0-9.]+)%\s*\|\s*Conf:\s*([0-9.]+)')


def dino_voice(detail, min_conf=0.35):
    match = _DETAIL.search(str(detail))
    if match is None:
        return None
    area, conf = float(match.group(1)) / 100.0, float(match.group(2))
    if not (math.isfinite(area) and math.isfinite(conf) and 0 < area < 1
            and min_conf <= conf <= 1):
        return None
    active_profile = (AREA_VOICES_FRONT28 if os.environ.get('CATROBOT_LIDAR_FRONT28_SIDE26', '0') == '1'
                      else AREA_VOICES)
    for limit, key, title, interval in active_profile:
        if area < limit:
            return key, title, interval, area, conf
    return None


def start_auto_meow(robot, scan_reader):
    if getattr(robot, '_dino_auto_meow_started', False):
        return
    robot._dino_auto_meow_started = True

    def worker():
        last_play = time.monotonic()
        last_frame_stamp = -1.0
        consecutive = 0
        active = False
        near_frames = 0
        near_last_frame = -1.0
        near_latched = False
        departure_frames = 0
        last_departure_frame = -1.0
        near_last_active = 0.0
        close_meow = os.environ.get('CATROBOT_DINO_CLOSE_MEOW', '0') == '1'
        if close_meow:
            print('[DINO ARRIVAL] close meow enabled; only a confirmed smaller box will rearm', flush=True)
        try:
            close_area = max(0.04, min(0.25, float(os.environ.get('CATROBOT_DINO_CLOSE_BOX_AREA', '0.08'))))
        except ValueError:
            close_area = 0.08
        if os.environ.get('CATROBOT_AVOIDANCE_V7', '0') == '1':
            close_area = max(0.04, min(0.09, float(os.environ.get('CATROBOT_DINO_CLOSE_BOX_AREA', '0.045'))))
        missing_file_warned = False
        try:
            min_conf = float(os.environ.get('CATROBOT_DINO_MEOW_MIN_CONF', '0.35'))
        except ValueError:
            min_conf = 0.35
        min_conf = max(0.35, min(1.0, min_conf))
        while True:
            time.sleep(0.20)
            cam = getattr(robot, 'camera', None)
            if cam is None or not getattr(cam, 'running', False):
                return
            with robot.lock:
                enabled = robot.mode == 'AUTO'
                stamp = float(robot.follow.get('at', 0.0))
                recent = 0 <= time.monotonic() - stamp <= robot.MAX_AUTO_AGE
                detail = str(robot.follow.get('detail', ''))
                verified = getattr(cam, 'verified_frames', 0) >= robot.CONFIRM_FRAMES
            # Stop all automated cat sounds when LiDAR is reporting an obstacle,
            # stale/missing data, or the web is not in AUTO.
            try:
                scan = scan_reader()
            except Exception:
                scan = {}
            scan_ok = scan.get('clear') is True and isinstance(scan.get('scan_age_s'), (int, float)) and 0 <= scan['scan_age_s'] <= 0.5
            blocked = getattr(robot, '_lidar_obstacle_alert_active', False) or not scan_ok
            candidate_raw = dino_voice(detail, max(min_conf, 0.50)) if enabled and recent and verified else None
            xy = getattr(cam, '_autocenter_xy', None)
            # Arrival hysteresis: a momentary missed frame, buzzer, or camera
            # occlusion must NOT re-trigger the arrival sound. Rearm only after
            # four distinct, fresh YOLO boxes visibly shrink from the close size.
            # Rearm using the already selected Dino tracking confidence (0.10/1 frame),
            # while PLAYING meow.wav itself still requires >=0.50, 3 frames and a full stop.
            departure_box = (dino_voice(detail, getattr(robot, 'TRACK_CONF', 0.10))
                             if enabled and recent and verified else None)
            departure = (close_meow and near_latched and enabled and recent and
                         departure_box is not None and departure_box[3] <= 0.68 * close_area)
            if departure:
                if stamp != last_departure_frame:
                    departure_frames = min(departure_frames + 1, 4)
                    last_departure_frame = stamp
                if departure_frames >= 4:
                    near_latched = False
                    near_frames = 0
                    departure_frames = 0
                    robot._catrobot_arrival_latched = False
                    print('[DINO ARRIVAL] Dino visibly moved away; AUTO can pursue and meow next arrival', flush=True)
            else:
                departure_frames = 0
                last_departure_frame = -1.0
            near = (close_meow and candidate_raw is not None and xy is not None and
                    len(xy) == 2 and abs(xy[0] - 0.5) <= 0.085 and
                    abs(xy[1] - 0.5) <= 0.095 and
                    candidate_raw[3] >= close_area and
                    isinstance(getattr(cam, '_autocenter_seen_at', None), (int, float)) and
                    0 <= time.monotonic() - cam._autocenter_seen_at <= 0.45 and
                    getattr(robot, '_catrobot_last_v', 0.0) == 0.0 and
                    getattr(robot, '_catrobot_last_w', 0.0) == 0.0 and
                    isinstance(scan.get('circle_min_m'), (int,float)) and
                    math.isfinite(scan['circle_min_m']) and
                    scan['circle_min_m'] > 0.22 and
                    isinstance(scan.get('scan_age_s'), (int,float)) and
                    0 <= scan['scan_age_s'] <= 0.40 and
                    not robot.pattern_busy.is_set() and
                    not getattr(robot, '_catrobot_nav_stuck', False) and
                    getattr(robot, '_catrobot_avoidance_state', 'IDLE') in ('IDLE', 'OFF'))
            if near:
                if stamp != near_last_frame:
                    near_frames = min(near_frames + 1, 3)
                    near_last_frame = stamp
                near_last_active = time.monotonic()
                if near_frames >= 3:
                    # Suppress the six variant thread during the close sound.
                    # This does not alter Buzzer priority, LiDAR, or motor gate.
                    if not near_latched:
                        files = robot.sound_files()
                        if 'meow.wav' in files:
                            robot.play_file('meow.wav')
                            print('[DINO CLOSE MEOW] centered Dino + stopped + fresh LiDAR; meow.wav requested', flush=True)
                        elif not missing_file_warned:
                            print('[DINO CLOSE MEOW] Missing ~/sounds/meow.wav; original meows retained', flush=True)
                            missing_file_warned = True
                        near_latched = True
                        robot._catrobot_arrival_latched = True
                    active = False
                    consecutive = 0
                    last_frame_stamp = -1.0
                    continue
            else:
                near_frames = 0
                near_last_frame = -1.0
                # Do not clear an arrival event just because the target was
                # briefly occluded, motion gate stopped, or SOS sounded.
                pass
            if close_meow and enabled and getattr(cam, '_v6_close_hold', False):
                # Close arrival is handled only by meow.wav (if all confirmation,
                # centering, LiDAR and stopped-motor checks pass). No repeated
                # variant sounds while waiting to rearm or center at the goal.
                active = False
                consecutive = 0
                last_frame_stamp = -1.0
                continue
            candidate = dino_voice(detail, min_conf) if enabled and recent and verified and not blocked else None
            if candidate is None:
                consecutive = 0
                active = False
                last_frame_stamp = -1.0
                continue
            # Require 2 *distinct* recent YOLO updates for the audio. This is
            # separate from the unchanged motion tracking confidence threshold.
            if stamp != last_frame_stamp:
                consecutive = min(consecutive + 1, 2)
                last_frame_stamp = stamp
            if consecutive < 2:
                continue
            voice, name, interval, area, conf = candidate
            if not active:
                last_play = time.monotonic()
                active = True
            if time.monotonic() - last_play >= interval:
                try:
                    robot.play_meow(voice)
                    print(f'[DINO MEOW] YOLO Dino conf={conf:.2f} box_area={area:.1%} '
                          f'type={name} key={voice} (visual size, NOT measured distance)', flush=True)
                except Exception as exc:
                    print('[DINO MEOW ERROR]', repr(exc), flush=True)
                last_play = time.monotonic()

    threading.Thread(target=worker, daemon=True, name='dino-only-six-meows').start()
    print('[DINO MEOW] Six original meow variants: verified YOLO Dino only; never LiDAR obstacle', flush=True)

# CATROBOT_BUZZER_FRONT40_20261109: installed
# CATROBOT_LIDAR_22CM_OBSTACLE_MEOW_20261109: installed (legacy upgrade provenance)

# CATROBOT_FRONT28_SIDE26_MEOW_TUNE_20261109: installed

# CATROBOT_DINO_CLOSE_MEOW_V4_20261109: installed

# CATROBOT_V6_MEOW_ARRIVAL_NOT_STUCK: installed

# CATROBOT_V7_ARRIVAL_HYSTERESIS: installed

# CATROBOT_V6_FLOW25_ARRIVAL_20261109: once-per-close-event sound; 4 fresh smaller-box frames rearm; six originals preserved
