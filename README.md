# CatRobot V6 — Final Startup, Docker Checks & AUTO Flow

**Reference version:** V6 Flow25 + Dino Arrival/Resume + HELP29/26 + **AUTO SOS36 / Safe Rearm37** (the latest configuration reported as tested on the robot).

**Hardware and software:** ROSMASTER M1 with Raspberry Pi 5 · YDLIDAR T-MINI Plus · camera and pan/tilt servos · custom YOLO model `models/best.pt` · ROS 2 Humble motor driver running in Docker · web-based teleoperation.

This is an **operating and verification guide for an existing installation**, not a patch installer or a fresh-device deployment script. Do not reinstall patches after every reboot. A newly provisioned Raspberry Pi also needs the appropriate ROS 2/Docker, YDLIDAR SDK, hardware, and audio setup.

**Rules:** Do not continue after a `FAIL` until its cause is resolved. Never run two robot control programs or two ROS 2 motor drivers at the same time.

> **Safety — wheels-up testing only:** The run command below uses `--mode wheels-up` and an experimental speed cap of **0.15 m/s**. Secure the robot on a stable stand with **all wheels off the ground** and provide a physical way to disconnect motor power. Do not hold the robot while AUTO is active. The system has experienced collisions and its stopping distance and floor-level obstacle coverage are not yet validated. This README does **not** approve autonomous floor driving.

---

## Project structure

The following files are available in the cleaned-up GitHub repository. The main entry point is `run_teleop_yolo_real.py`. Some modules are retained as dependencies or diagnostic tools; their presence alone does not mean every experimental behavior runs simultaneously.

```text
CatRobot-YOLO-Detector/
├── README.md                         # This English operating guide
├── README_REAL_ROBOT_TH.md           # Additional Thai guide
├── requirements.txt                  # Basic Python requirements (not full robot setup)
├── .gitignore
│
├── run_teleop_yolo_real.py           # Real-robot entry point / orchestration
├── robot_teleop_yolo_robot.py        # Web UI, camera, YOLO and interaction
├── robot_teleop.py                   # Original teleoperation, audio and controls
├── dino_motion.py                    # ROS 2 bridge, motors, servos, buzzer and LiDAR process
├── dino_auto_center.py               # Pan/tilt tracking and parallel follow behavior
├── dino_auto_meow.py                 # Automatic meow behavior
├── dino_help_resume_v6.py            # V6 assisted help / SOS / safe resume
├── dino_avoidance_v4.py              # Parent class in V4 → V5 → V6 dependency chain
├── dino_avoidance_v5.py              # Parent class for V6 avoidance
├── dino_avoidance_v6.py              # Optional V6 avoidance implementation
│
├── lidar_directional_avoidance.py    # Directional scan and safety gate
├── lidar_360_guard.py                # 360-degree obstacle guard
├── lidar_obstacle_alert.py           # Obstacle alert logic
├── lidar_buzzer_tiers.py             # Buzzer and SOS patterns
├── tmini_plus_lidar.py               # YDLIDAR reader
├── catrobot_vision_diagnostics.py    # Diagnostic helper
│
├── models/
│   └── best.pt                       # Trained green-dinosaur YOLO weights
├── docs/
│   ├── ROBOT_SETUP_TH.md
│   └── TMINI_PLUS_SETUP_TH.md
└── tests/
    └── test_tmini_plus_lidar.py
```

**Important external resources:** The original Dino-arrival sound is expected at `~/sounds/meow.wav` on the Raspberry Pi. ROS 2 and the motor driver run in the pre-existing Docker container named `affectionate_lamport` (ROS domain `62`). The Git repository does not contain a full Docker image or a complete Raspberry Pi system image.

**Older work:** Installer scripts such as `apply_*.py`, historical prototypes, backups, datasets, `.venv/`, logs and patch payloads are not part of this final GitHub runtime source. They must not be copied back into the repository just to make the tree larger.

To inspect source files on the Raspberry Pi without listing virtual environments and backup directories:

```bash
cd ~/CatRobot-YOLO-Detector
find . -maxdepth 2 \
  \( -name '.git' -o -name '.venv' -o -name '__pycache__' -o -name 'backups' -o -name 'backup_before_*' -o -name '.ipynb_checkpoints' \) -prune -o \
  -type f \( -name '*.py' -o -name '*.md' -o -name 'requirements*.txt' \) -print | sort
```

> Before publishing source code, review all staged changes for credentials, private information, generated logs and unnecessary local data. Do not stage `.venv/`, `__pycache__/`, backups or training datasets.

---

## Startup flow

`SSH to Pi` → `Check source and Python` → `Check USB / LiDAR / motor serial` → **`Check Docker → stop conflicting motor driver → start affectionate_lamport → verify ROS 2`** → `Check stale processes / port 8080 / camera` → `Check YOLO model / audio` → `Run V6 with wheels up` → `Verify STOP / AUTO / SOS / meow / resume` → `Stop and shut down safely`.

```text
Power on the Raspberry Pi
    |
    v
STEP 0: SSH and activate Python virtual environment
    |
    v
STEP 1: Verify source files, Python modules and V6 thresholds
    |
    v
STEP 2: Verify USB, LiDAR and motor serial connections
    |
    v
STEP 3: Check Docker -> stop only the confirmed conflicting motor driver
        -> start affectionate_lamport -> verify ROS 2
    |
    v
STEP 4: Check for stale runners, port 8080, camera and LiDAR ownership
    |
    v
STEP 5: Verify best.pt and meow.wav
    |
    v
STEP 6: Run CatRobot V6 on a stable, wheels-up test stand
    |
    v
STEP 7: Verify logs, STOP, MANUAL, AUTO, SOS, arrival and resume
    |
    v
STEP 8: STOP -> Ctrl+C -> verify process exit -> shut down if required
```

| When | Actions |
| --- | --- |
| After each SSH login | STEP 0 |
| After boot, code updates, USB changes or Docker changes | STEP 1–3 and STEP 5 |
| **Before every program launch**, including a second launch in the same boot | STEP 4 |
| For each controlled robot test | STEP 6–8 |

If USB disconnects, LiDAR stops scanning, Docker restarts, or the program is suspended with `Ctrl+Z`, return to STEP 2–4 even if the Raspberry Pi has not rebooted.

**Floor tests are not covered by this operating procedure.** They require independent braking, physical-clearance, obstacle-detection and emergency-stop validation.

---

## STEP 0 — SSH into Raspberry Pi

**On Windows CMD or PowerShell:**

```bat
ssh pi@192.168.1.11
```

The IP address is from an earlier test; replace it with the Pi's current IP address when the network changes.

**On the Raspberry Pi host:**

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
pwd
python --version
```

Expected directory: `/home/pi/CatRobot-YOLO-Detector`. Python must run from the project's `.venv` (typically indicated by `(.venv)` in the shell prompt).

---

## STEP 1 — Verify final V6 code, Python modules and YOLO hooks

Run after boot and repeat after editing source, rebuilding `.venv` or updating packages.

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate

echo '===== 1. REQUIRED FILES ====='
missing=0
for f in \
  run_teleop_yolo_real.py \
  robot_teleop_yolo_robot.py \
  robot_teleop.py \
  dino_auto_center.py \
  dino_auto_meow.py \
  dino_motion.py \
  dino_help_resume_v6.py \
  dino_avoidance_v4.py \
  dino_avoidance_v5.py \
  dino_avoidance_v6.py \
  lidar_directional_avoidance.py \
  lidar_360_guard.py \
  lidar_obstacle_alert.py \
  lidar_buzzer_tiers.py \
  tmini_plus_lidar.py \
  models/best.pt; do
  if [ -f "$f" ]; then
    echo "PASS: $f"
  else
    echo "FAIL: MISSING $f"
    missing=1
  fi
done
[ "$missing" -eq 0 ] && echo 'PASS: ALL REQUIRED FILES PRESENT'

echo '===== 2. PYTHON SYNTAX ====='
python -m py_compile \
  run_teleop_yolo_real.py \
  robot_teleop_yolo_robot.py \
  robot_teleop.py \
  dino_auto_center.py \
  dino_auto_meow.py \
  dino_motion.py \
  dino_help_resume_v6.py \
  dino_avoidance_v4.py \
  dino_avoidance_v5.py \
  dino_avoidance_v6.py \
  lidar_directional_avoidance.py \
  lidar_360_guard.py \
  lidar_obstacle_alert.py \
  lidar_buzzer_tiers.py \
  tmini_plus_lidar.py && echo 'PASS: PYTHON SYNTAX'

echo '===== 3. PYTHON MODULES ====='
python - <<'PY'
import importlib
import sys

required = ('ultralytics', 'torch', 'cv2', 'numpy', 'ydlidar')
failed = []
for name in required:
    try:
        module = importlib.import_module(name)
        version = getattr(module, '__version__', 'installed')
        print(f'PASS: {name} ({version})')
    except Exception as exc:
        print(f'FAIL: {name}: {exc}')
        failed.append(name)
if failed:
    sys.exit('MODULE CHECK FAILED')
print('PASS: ALL MODULES')
PY

echo '===== 4. FINAL AUTO HOOKS ====='
grep -nE 'start_auto_center|start_auto_meow' \
  run_teleop_yolo_real.py || echo 'CHECK: AUTO HOOKS NOT FOUND'
grep -n 'CATROBOT_MOVE_WHILE_CENTERING' \
  dino_auto_center.py || echo 'CHECK: PARALLEL MODE NOT FOUND'

echo '===== 5. FINAL AUTO SOS THRESHOLDS ====='
python - <<'PY'
import ast
from pathlib import Path

tree = ast.parse(Path('dino_help_resume_v6.py').read_text())
actual = {}
for node in tree.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                try:
                    actual[target.id] = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    pass
expected = {
    'STOP_AHEAD_M': 0.36,
    'RESUME_FRONT_FORWARD_M': 0.37,
    'CLEAR_FRONT_M': 0.29,
    'CLEAR_REAR_M': 0.29,
    'CLEAR_FLANK_M': 0.26,
    'CLEAR_CIRCLE_M': 0.26,
}
failed = False
for name, value in expected.items():
    found = actual.get(name)
    if found == value:
        print(f'PASS: {name} = {found} m')
    else:
        print(f'FAIL: {name}: expected {value}, got {found}')
        failed = True
if failed:
    raise SystemExit('FAIL: V6 SOS THRESHOLD MISMATCH')
print('PASS: FINAL V6 AUTO SOS36 / RESUME37 / HELP29-26')
PY

echo '===== 6. YOLO / SPEED / ARRIVAL FLAGS ====='
grep -n 'CATROBOT_ORANGE_FOLLOW_TRIAL' \
  run_teleop_yolo_real.py || echo 'CHECK: ORANGE FOLLOW NOT FOUND'
grep -n 'CATROBOT_BENCH_SPEED_015' \
  run_teleop_yolo_real.py || echo 'CHECK: SPEED 015 NOT FOUND'
grep -n 'DINO ARRIVAL V6' \
  dino_auto_center.py || echo 'CHECK: DINO RESUME NOT FOUND'
```

### Expected V6 settings

| Subsystem | Reference value |
| --- | --- |
| AUTO forward stop / SOS | **0.36 m** (36 cm) |
| Forward rearm after WAIT_HELP | **0.37 m** (37 cm) |
| General front/rear clearance for WAIT_HELP | **0.29 m** (29 cm) |
| Flank and 360° clearance for WAIT_HELP | **0.26 m** (26 cm) |
| Dino tracking | Confidence `0.10`; `1` confirmation frame |
| Dino arrival | Image box area `4.5%` plus centering conditions |
| Dino departure | Four new frames with the box below the configured rearm threshold |
| Experimental AUTO/MANUAL translational speed | Up to `0.15 m/s`, wheels-up only |

**Interpretation:** A passing syntax check does not prove hardware behavior. Finding a feature flag in source does not mean it is enabled; verify the launch command and runtime logs. Do not proceed past a real `FAIL`.

---

## STEP 2 — Check USB devices and serial ports

Perform after each boot, after USB changes or when LiDAR or power stability is in doubt.

```bash
echo '===== 1. USB DEVICES ====='
lsusb -t
lsusb

echo '===== 2. LIDAR PORT ====='
LIDAR_PORT="$(readlink -f /dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0)"
echo "LiDAR = $LIDAR_PORT"

echo '===== 3. MOTOR PORT ====='
MOTOR_PORT="$(readlink -f /dev/myserial)"
echo "Motor = $MOTOR_PORT"

echo '===== 4. PORT CHECK ====='
if [ -c "$LIDAR_PORT" ] && [ -c "$MOTOR_PORT" ] && [ "$LIDAR_PORT" != "$MOTOR_PORT" ]; then
    echo 'PASS: LiDAR and Motor use separate valid ports'
else
    echo 'FAIL: Check USB ports before continuing'
fi

echo '===== 5. LIDAR PORT OWNER ====='
if [ -c "$LIDAR_PORT" ]; then
    sudo fuser -v "$LIDAR_PORT" || echo 'LiDAR port is free'
fi

echo '===== 6. MOTOR PORT OWNER ====='
if [ -c "$MOTOR_PORT" ]; then
    sudo fuser -v "$MOTOR_PORT" || true
fi
```

Previously observed on this robot:

| Device | Previously observed path | USB interface |
| --- | --- | --- |
| T-MINI Plus LiDAR | `/dev/ttyUSB0` | CP2102 USB–UART |
| Motor controller | `/dev/ttyUSB1` | CH341 USB–UART |
| Motor symlink | `/dev/myserial` | Resolve to the actual motor port |

`ttyUSB0` and `ttyUSB1` can switch after a reboot. **Always use the actual output from `readlink -f`, not a guessed serial number.** Before starting the CatRobot runner, the LiDAR port should be free. It is normal for the Docker ROS 2 motor driver to own the motor port.

---

## STEP 3 — Check Docker, stop a conflicting motor driver, and verify ROS 2

**Perform after every Raspberry Pi boot**, or whenever Docker/motor control is restarted or changes unexpectedly. This robot has previously started a container other than `affectionate_lamport` after boot.

Before changing Docker containers, press **STOP** if the web control is available, verify the wheels are stationary, and **disconnect motor power during driver changes**. Do not stop/restart drivers while the robot can move.

### 3.1 Inspect running containers and motor serial ownership

```bash
echo '===== RUNNING DOCKER CONTAINERS ====='
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'

echo '===== ALL DOCKER CONTAINERS ====='
sudo docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'

echo '===== MOTOR SERIAL OWNER ====='
MOTOR_PORT="$(readlink -f /dev/myserial)"
echo "Motor serial = $MOTOR_PORT"
if [ -c "$MOTOR_PORT" ]; then
    sudo fuser -v "$MOTOR_PORT" 2>&1 || echo 'No visible motor serial owner'
else
    echo 'FAIL: MOTOR SERIAL MISSING'
fi
```

For this setup, the intended motor-driver container is **`affectionate_lamport`**. An unrelated container is **not automatically wrong** just because it has a different name. Investigate whether it duplicates the ROS 2 motor driver, owns the motor serial port, or publishes conflicting commands.

### 3.2 Inspect and stop a confirmed conflicting driver

Use the **actual** container name shown by `sudo docker ps`. For example, if `interesting_feynman` appears:

```bash
OTHER_CONTAINER="interesting_feynman"

sudo docker inspect -f 'Name={{.Name}} Image={{.Config.Image}} Restart={{.HostConfig.RestartPolicy.Name}} Privileged={{.HostConfig.Privileged}} Devices={{json .HostConfig.Devices}}' "$OTHER_CONTAINER"
sudo docker top "$OTHER_CONTAINER"
```

The name `interesting_feynman` is a **previously observed example**, not a claim that it is the wrong container on the current boot. Replace it with the container you inspected. **Only after confirming that it is a conflicting motor driver**, run:

```bash
sudo docker stop "$OTHER_CONTAINER"
```

Alternatively, after confirming that the example container is the conflict:

```bash
sudo docker stop interesting_feynman
```

Do not type placeholders such as `(DOCKER NAME)` or `<DOCKER NAME>` verbatim: parentheses and angle brackets have special meanings in a shell. Do not stop every Docker container indiscriminately.

Confirm the unwanted driver is no longer running:

```bash
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
```

### 3.3 Start the intended container

If `affectionate_lamport` is not already running, and the conflicting driver has been stopped:

```bash
sudo docker start affectionate_lamport
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
```

If it is already `Up`, leave it running. If startup fails, inspect the logs rather than launching another motor driver:

```bash
sudo docker logs --tail 80 affectionate_lamport
```

### 3.4 Verify the ROS 2 `/cmd_vel` subscriber

```bash
echo '===== ROS2 MOTOR DRIVER ====='
sudo docker exec affectionate_lamport bash -lc '
source /opt/ros/humble/setup.bash
source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash
export ROS_DOMAIN_ID=62
export ROS_LOCALHOST_ONLY=1
ros2 topic info /cmd_vel -v
'
```

Expected: `/cmd_vel` has **`Subscription count: 1`**, a motor-driver node such as `driver_node`, and topic type `geometry_msgs/msg/Twist`. Do not start the robot runner while there are multiple competing motor drivers.

### 3.5 Optional: prevent a confirmed wrong driver from auto-starting

Check its Docker restart policy:

```bash
sudo docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$OTHER_CONTAINER"
```

**Only with the machine owner's approval**, disable auto-restart for the confirmed conflicting container:

```bash
sudo docker update --restart=no "$OTHER_CONTAINER"
```

This changes the policy across reboots. It **does not remove or stop** a currently running container; run `docker stop` separately when appropriate. Record the original policy first. Do not change the restart policy of `affectionate_lamport` or unrelated containers.

---

## STEP 4 — Check and clean up before every CatRobot launch

Complete this step **every time** before launching the runner, including after `Ctrl+C`, an SSH disconnect, or a previous run during the same boot.

```bash
echo '===== 1. OLD ROBOT PROCESSES ====='
ps -eo pid,ppid,stat,tty,args | grep -E '[r]un_teleop_yolo_real.py|[r]obot_teleop_yolo_robot.py|[y]dlidar|[t]mini' || true

echo '===== 2. WEB PORT 8080 ====='
sudo ss -ltnp | grep ':8080' || echo 'PORT 8080 FREE'

echo '===== 3. CAMERA ====='
ls -l /dev/video0 2>/dev/null || echo 'FAIL: CAMERA /dev/video0 NOT FOUND'

echo '===== 4. LIDAR SERIAL ====='
ls -l /dev/serial/by-id/
LIDAR_PORT="$(readlink -f /dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0)"
echo "LIDAR PORT = $LIDAR_PORT"
if [ -c "$LIDAR_PORT" ]; then
    sudo fuser -v "$LIDAR_PORT" 2>&1 || echo 'LiDAR port is free'
else
    echo 'FAIL: LiDAR serial device not found'
fi

echo '===== 5. USB / POWER ERRORS ====='
sudo journalctl -k --no-pager -n 100 | grep -Ei 'usb|ttyUSB|cp210|voltage|reset|disconnect' | tail -n 35 || true
```

Before starting, confirm that port 8080 is free, there is no old CatRobot runner, the LiDAR port is not owned by another program, the camera exists, and the correct Docker motor driver is running.

### If web port 8080 is still listening

Do **not** launch another instance. Inspect the PID reported by `ss`:

```bash
sudo ss -ltnp | grep ':8080'
ps -o pid,ppid,stat,tty,cmd -p PID_HERE
```

Replace `PID_HERE` with the **numeric PID** returned by `ss`. If it is the previous CatRobot runner in your terminal, click **STOP**, verify the wheels stop, and press **`Ctrl+C`** in that terminal. **Do not use `Ctrl+Z`** to stop the robot: it only suspends the process.

If the previous terminal is unavailable, **disconnect motor power first**, verify the PID really belongs to the stale CatRobot runner, and then terminate it:

```bash
kill -TERM PID_HERE
```

If the process is in state `T`/`t` because of `Ctrl+Z`, do not resume it with motor power connected. Once the motor is safely disconnected, you may use `kill -CONT PID_HERE` followed by `kill -TERM PID_HERE`; `CONT` can immediately resume active robot code.

Check again until port 8080 is free. If `MOTOR STOP FAILED` occurs, stop the experiment and investigate; do not forcibly kill processes while the motors are powered.

### If LiDAR does not scan

If no other process owns the serial port, stop CatRobot, disconnect motor power, inspect cables and USB connections, and safely reconnect LiDAR if necessary. Repeat STEP 2 and STEP 4. Do not restart every Docker container or weaken the motor safety gate to bypass a serial problem.

---

## STEP 5 — Verify the YOLO model and arrival audio

Run once after boot or after changes to the model, speaker, or sound files.

```bash
cd ~/CatRobot-YOLO-Detector

echo '===== YOLO MODEL ====='
if [ -s models/best.pt ]; then
    ls -lh models/best.pt
    echo 'PASS: YOLO MODEL PRESENT'
else
    echo 'FAIL: models/best.pt MISSING OR EMPTY'
fi

echo '===== DINO ARRIVAL SOUND ====='
if [ -s "$HOME/sounds/meow.wav" ]; then
    ls -lh "$HOME/sounds/meow.wav"
    echo 'PASS: meow.wav PRESENT'
else
    echo 'FAIL: ~/sounds/meow.wav MISSING OR EMPTY'
fi
```

These are file-presence checks, not proof that YOLO detects the dinosaur or that sound is heard through the speaker. Check actual behavior and logs in STEP 7.

---

## STEP 6 — Run CatRobot V6 (wheels-up only)

> Only run this command with the robot **secured on a stable stand, with all wheels raised** and a physical motor-power cutoff ready. This is not an approved floor-driving command.

Copy the complete Bash block into the Raspberry Pi's SSH terminal. Do not insert blank lines between lines ending with `\`.

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
sudo -v

unset CATROBOT_AVOIDANCE_V7 CATROBOT_AVOIDANCE_V3 CATROBOT_AVOIDANCE_V4 CATROBOT_SPEED_TRIAL CATROBOT_STABLE_SPEED_08

LIDAR_PORT="$(readlink -f /dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0)"
if [ ! -c "$LIDAR_PORT" ]; then
  echo 'FAIL: LIDAR PORT INVALID - DO NOT START ROBOT'
else
  CATROBOT_BENCH_SPEED_015=1 \
  CATROBOT_ORANGE_FOLLOW_TRIAL=1 \
  CATROBOT_AVOIDANCE_V1=1 \
  CATROBOT_AVOIDANCE_V5=1 \
  CATROBOT_AVOIDANCE_V6=1 \
  CATROBOT_V6_ASSISTED_HELP=1 \
  CATROBOT_DINO_CLOSE_MEOW=1 \
  CATROBOT_DINO_CLOSE_BOX_AREA=0.045 \
  CATROBOT_LIDAR_FRONT28_SIDE26=1 \
  CATROBOT_LIDAR_360_RADIUS_TEST=1 \
  CATROBOT_LIDAR_360_DEBUG=1 \
  CATROBOT_AUTO_CENTER=1 \
  CATROBOT_CENTER_BASE=1 \
  CATROBOT_MOVE_WHILE_CENTERING=1 \
  CATROBOT_PAN_RIGHT_SIGN=-1 \
  CATROBOT_TILT_DOWN_SIGN=-1 \
  CATROBOT_BASE_SIGN=1 \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -u run_teleop_yolo_real.py \
    --mode wheels-up --imgsz 320 --ros-domain-id 62 \
    --lidar-port "$LIDAR_PORT" \
    --confirm-wheels-up --confirm-emergency-stop 2>&1 | tee ~/catrobot_v6_sos36_flow_final_015.log
fi
```

The `CATROBOT_BENCH_SPEED_015=1` profile uses up to **0.150 m/s translational speed** for the wheels-up AUTO/MANUAL tests. Angular velocity `w` is in **rad/s**, not m/s. For the earlier lower-speed trial, stop the runner and replace `CATROBOT_BENCH_SPEED_015=1` with `CATROBOT_STABLE_SPEED_08=1`, then choose a different log filename.

Open the web interface from a computer on the same network: **`http://192.168.1.11:8080`** (use the actual Pi IP). The robot should initially be in **STOPPED** mode. Verify STOP before switching to MANUAL or AUTO.

### Expected startup logs

```text
[VISION] YOLO warm-up OK
[MOTOR] READY /cmd_vel subscribers=1
[TMINI] Scanning: /dev/ttyUSB...
[LIDAR 360] min=... valid_points=...
[BENCH SPEED] WHEELS-UP ONLY: AUTO=0.150 m/s MANUAL=0.150 m/s
[MOTOR DOCKER] BRIDGE_DIAG speed_limit_mps=0.15
[ORANGE FOLLOW] ... TRACK >= 0.10 and CONFIRM_FRAMES=1
[DINO CAMERA] IMG_SIZE=320 YOLO=0.05 TRACK=0.1 CONFIRM_FRAMES=1
[WEB] Original teleop UI + real YOLO: http://192.168.1.11:8080
```

If you see `WEB HEARTBEAT LOST`, `AVOID`, `LIDAR scan stale`, `MOTOR ERROR` or `MOTOR STOP FAILED`, do not bypass safety checks. Review logs and STEP 2–4 first.

---

## STEP 7 — Verify AUTO, SOS, Dino arrival and resume (wheels-up)

```text
AUTO + confirmed Dino (YOLO TRACK >= 0.10 / 1 frame)
  |
  +-- Dino is not yet close; directional gate allows movement
  |     -> FOLLOW: camera servos track Dino and the base follows
  |
  +-- Dino is close (bounding-box area >= 4.5% of image)
  |     -> stop advancing; center Dino with camera servos
  |     -> once centering / arrival conditions are satisfied
  |     -> play meow.wav as the distinct arrival sound
  |     -> if Dino moves away and its box <= 3.06% for 4 new frames
  |     -> FOLLOW again, only if the motor safety gate allows it
  |
  +-- During AUTO forward travel, front LiDAR < 0.36 m
        -> stop motor -> SOS alert -> WAIT_HELP
        -> require at least 2.5 seconds and 6 fresh scans
        -> confirm Dino is visible again
        -> front and rear general clearance >= 0.29 m
        -> side and 360-degree clearance >= 0.26 m
        -> any new forward motion needs front >= 0.37 m
        -> re-check proposed motion with directional motor safety gate
        -> WAIT_HELP -> IDLE -> FOLLOW again
           (or ARRIVED if Dino still meets arrival conditions)
```

### Reference thresholds and behaviors

| Behavior | Reference threshold | Meaning |
| --- | --- | --- |
| AUTO forward stop and WAIT_HELP | Front `< 0.36 m` | Stop before a detected front obstacle |
| Forward motion after WAIT_HELP | Front `>= 0.37 m` | Forward rearm hysteresis |
| WAIT_HELP general front/rear clearance | `>= 0.29 m` | Required for state release; **not** permission to drive forward at 29 cm |
| WAIT_HELP side/360-degree clearance | `>= 0.26 m` | Required before releasing help state |
| Directional motor gate | Front/side `0.28 / 0.26 m` | Separate motor safety layer |
| 360-degree emergency threshold | `0.22 m` | Emergency condition separate from WAIT_HELP |
| WAIT_HELP release | `>= 2.5 s` + 6 new scans + Dino confirmation | The directional safety gate still applies |
| YOLO tracking | Confidence `0.10`, 1 frame | Selected trial settings |
| Dino close / arrived | Bounding-box area `4.5%` | Relative image area, **not** distance in centimeters |
| Dino moves away | Box `<= 3.06%` for 4 new frames | May resume following only after safety checks |

The LiDAR thresholds are measured from the **LiDAR sensor origin**, not from the front bumper. A 2D LiDAR cannot reliably detect every low object or blind spot, and stopping distance at `0.15 m/s` has not been validated. **WAIT_HELP does not autonomously reverse or plan a bypass route** in this selected V6 assisted-help mode. If a safe path is not available, the robot must remain stopped and await assistance.

### Inspect behavior logs

```bash
grep -E 'BENCH SPEED|STABLE SPEED|BRIDGE_DIAG speed_limit|DINO CAMERA|ORANGE FOLLOW|DRIVE GATE|REAL MOTOR|AUTO ZERO DIAG|HELP V6|HELP WAIT DIAG|HELP V6 SOS|DINO ARRIVAL V6|DINO CLOSE MEOW|Playing meow.wav|OBSTACLE BUZZER|MOTOR ERROR|MOTOR STOP FAILED' \
  ~/catrobot_v6_sos36_flow_final_015.log | tail -n 180
```

Hearing `meow_7.wav` or `meow_m.wav` is **not** the same as the distinct `meow.wav` arrival sound. If `Playing meow.wav` does not appear, inspect the target-size and image-centering conditions before treating the arrival test as passed.

### About future floor testing

Do **not** infer floor safety from wheels-up success. Before any separately controlled floor trial, verify real braking distance, the LiDAR-to-bumper offsets, swept space during turns, hazards below the LiDAR scanning plane, STOP/physical power cutoff, and safe behavior on loss of web/ROS 2 communication. Keep using wheels-up tests until those checks have passed.

---

## STEP 8 — STOP, exit the runner and shut down safely

1. Press **STOP** in the web UI and physically verify that the wheels are stationary.
2. Press **`Ctrl+C`** in the terminal running CatRobot (**not** `Ctrl+Z`).
3. Confirm there is no remaining runner and the web port is free:

```bash
sudo ss -ltnp | grep ':8080' || echo 'PORT 8080 FREE'
ps -eo pid,ppid,stat,cmd | grep -E '[r]un_teleop_yolo_real.py' || echo 'NO CATROBOT RUNNER'
```

For another run during the same boot, repeat **STEP 4** before STEP 6. No need to repeat STEP 1–3 unless code, USB, ROS 2 or power conditions changed.

If STOP fails or the motor reports `MOTOR STOP FAILED`, disconnect motor power and stop testing. Never rely on closing SSH or pressing `Ctrl+Z` as an emergency stop.

If you need to power down the Raspberry Pi after the robot is safely stopped and the runner has exited:

```bash
sudo shutdown -h now
```

Let the Pi finish shutting down before removing its power source. `shutdown` is not a substitute for a physical emergency stop.

---

## Quick reference for the next lab session

| Situation | Steps |
| --- | --- |
| Fresh Raspberry Pi boot | STEP 0 → 1 → 2 → **3 (inspect Docker, stop only the wrong motor driver, start `affectionate_lamport`, verify ROS 2)** → 4 → 5 → 6 |
| Re-running CatRobot in the same boot | STOP → `Ctrl+C` → STEP 4 → 6 |
| Wrong Docker motor driver auto-started | STEP 3.1 → 3.2 → 3.3 → 3.4 before STEP 6 |
| USB / LiDAR / Docker fault | STOP → exit runner → STEP 2 → 3 → 4 → 5 if needed → 6 |
| Source code updated | STOP → exit runner → STEP 1 → 2–5 as needed → 6 |
| End of experiment | STEP 8: STOP → `Ctrl+C` → check runner/port → safe shutdown |

This document records the configuration and verification procedures used during development. It is **not** a certificate of safe autonomous floor operation or guaranteed detection of obstacles at every height.
