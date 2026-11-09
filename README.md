# CatRobot V6 — Final Startup, Docker Check & AUTO Flow

**เวอร์ชันที่ใช้อ้างอิง:** V6 Flow25 + Dino Arrival/Resume → HELP29/26 → **AUTO SOS36 / Safe Rearm37** (เวอร์ชันล่าสุดที่ผู้ใช้รายงานว่าทดสอบผ่าน)

**อุปกรณ์:** Raspberry Pi 5 บน ROSMASTER M1 · LiDAR T-Mini Plus · กล้อง + Servo · YOLO `models/best.pt` · ROS2 Motor Driver ใน Docker · Web Teleop

> เอกสารนี้เป็น **ขั้นตอนเปิดและตรวจระบบที่ติดตั้งไว้แล้ว** ไม่ใช่ตัวติดตั้งแพตช์หรือคำสั่งเปลี่ยนโค้ด ถ้า Pi ยังไม่ได้ติดตั้ง AUTO SOS36 ให้ติดตั้งจากคู่มือแพตช์ก่อน ไม่ต้องติดตั้งใหม่ทุกครั้งที่บูต

**กฎสำคัญ:** อย่าข้ามขั้นที่ขึ้น `FAIL` และอย่าเปิด Robot Runner หรือ ROS2 Motor Driver ซ้อนกันสองตัว

> **ความปลอดภัย:** คำสั่งหลักด้านล่างเปิด `--mode wheels-up` และความเร็วทดลอง `0.15 m/s` ใช้ได้เฉพาะ **หุ่นยนต์ยึดอยู่บนแท่นมั่นคงและล้อไม่สัมผัสพื้น** เท่านั้น เพราะเคยมีการชนจริงและยังไม่มีการวัดระยะเบรกบนพื้น อย่าอุ้มหุ่นยนต์ขณะ AUTO พร้อมสั่งล้อ หรือใช้มือทดสอบใกล้ล้อ/เซ็นเซอร์ที่กำลังเคลื่อนที่ ให้เตรียมวิธีตัดกำลังมอเตอร์ไว้เสมอ


---


## Project Structure — ไฟล์ Source Code บน Raspberry Pi

ส่วนนี้ช่วยให้คนอ่าน GitHub รู้จักจุดเริ่มต้นของโค้ด โดยผังด้านล่างสรุป **ไฟล์ที่ตรวจพบว่ามีอยู่บน Pi** และไฟล์ที่เกี่ยวข้องกับ Flow V6 ตามชื่อและการตั้งค่าที่ใช้รัน ไม่ใช่ผลตรวจ import chain ทุกไฟล์ (ยังต้องตรวจจาก Source Archive เพื่อยืนยัน dependency ที่ใช้งานจริง)

```text
CatRobot-YOLO-Detector/
├── run_teleop_yolo_real.py       # Entry point ที่ใช้ในคำสั่งรันจริง
├── robot_teleop_yolo_robot.py    # ส่วนประกอบ Robot/Web/YOLO (ตรวจการเรียกใช้จาก Source อีกครั้ง)
├── robot_teleop.py               # ไฟล์ teleop เดิม
├── dino_auto_center.py          # กล้องติดตามและการจัด Dino ให้อยู่กลางภาพ
├── dino_auto_meow.py            # ระบบเสียงแมวและเงื่อนไขถึง Dino
├── dino_motion.py               # การคำนวณ/ควบคุมความเร็วการเคลื่อนที่
├── dino_help_resume_v6.py       # AUTO SOS36, WAIT_HELP, resume37
├── dino_avoidance_v5.py         # โมดูลหลบสิ่งกีดขวางที่อยู่ในโครงการ
├── dino_avoidance_v6.py         # โมดูลหลบสิ่งกีดขวาง V6
├── lidar_directional_avoidance.py
├── lidar_360_guard.py
├── lidar_buzzer_tiers.py
├── tmini_plus_lidar.py
├── requirements.txt
├── models/
│   └── best.pt                  # มีบน Pi; ไม่รวมใน source-only tar.gz
└── README.md
```

**ไฟล์เพิ่มเติมใน Pi:** มีสคริปต์ `apply_*.py`, โค้ดทดลอง `cat_robot_*.py`, เวอร์ชัน `dino_avoidance_v3/v4/v7.py`, ไฟล์ `test_*.py` และโฟลเดอร์ backup/payload เก่าด้วย ไม่ควรถือว่าเป็นส่วนของ Final Runtime ทั้งหมดหรืออัปโหลดขึ้น GitHub โดยไม่คัดแยกก่อน

**ไฟล์ภายนอก Repository:** เสียงถึงเป้าหมายอยู่ที่ `~/sounds/meow.wav`; ส่วน ROS2 Motor Driver ทำงานใน Docker container `affectionate_lamport` และโมเดล YOLO อยู่ที่ `models/best.pt` บน Pi จึงควรอธิบายวิธีเตรียมไฟล์เหล่านี้เมื่อเพื่อนต้องการนำโค้ดไปรัน ไม่ใช่แค่อ่าน Source

ถ้าต้องการดูรายการไฟล์จริงจาก Pi (ไม่รวม virtual environment, Git และไฟล์ backup) รัน:

```bash
cd ~/CatRobot-YOLO-Detector
find . -maxdepth 2 \
  \( -name '.git' -o -name '.venv' -o -name '__pycache__' -o -name 'backups' -o -name 'backup_before_*' -o -name '.ipynb_checkpoints' \) -prune -o \
  -type f \( -name '*.py' -o -name '*.md' -o -name 'requirements*.txt' \) -print | sort
```

> สำหรับ GitHub ควรอัปโหลด Source ที่ยืนยันว่าจำเป็นจริง + README + requirements เท่านั้น ก่อนเผยแพร่ให้ตรวจข้อมูลลับ และไม่เพิ่ม `.venv/`, `__pycache__/`, `backups/`, `*.log`, Dataset หรือไฟล์โมเดลขนาดใหญ่โดยไม่จำเป็น

---

## Flow ภาพรวม

`SSH เข้า Pi` → `ตรวจไฟล์ + Python` → `ตรวจ USB / LiDAR / Motor` → **`ตรวจ Docker + หยุด Driver ตัวผิด + เริ่มตัวที่ใช้จริง`** → `ตรวจโปรแกรมค้าง + Port 8080 + Camera` → `ตรวจโมเดล + Audio` → `ยกล้อทดสอบ V6 AUTO/Arc Follow` → `ตรวจ SOS / Meow / Resume` → `STOP / Shutdown`

```text
เปิด Raspberry Pi
   ↓
[STEP 0] SSH + เข้า .venv
   ↓
[STEP 1] ตรวจ Source / Python modules / เกณฑ์ V6    (หลังบูตหรือแก้โค้ด)
   ↓
[STEP 2] ตรวจ USB / LiDAR / Motor Serial             (หลังบูตหรือ USB เปลี่ยน)
   ↓
[STEP 3] ตรวจ Docker → หยุดเฉพาะ Motor Driver ตัวผิด → เริ่ม affectionate_lamport → ตรวจ ROS2
   ↓
[STEP 4] ตรวจ Runner ค้าง / Port 8080 / Camera / LiDAR Port  (ทุกครั้งก่อนรัน)
   ↓
[STEP 5] ตรวจ best.pt / meow.wav                    (หลังบูตหรือเปลี่ยนไฟล์)
   ↓
[STEP 6] เปิด CatRobot V6 บนแท่นยกล้อที่มั่นคง
   ↓
[STEP 7] ตรวจ Log + STOP / MANUAL / AUTO / SOS / Arrival / Resume
   ↓
[STEP 8] STOP + Ctrl+C → ตรวจโปรแกรมปิด → Shutdown ตามต้องการ
```

| ทำเมื่อไหร่ | ขั้นตอน |
| --- | --- |
| ทุกครั้งที่เปิด SSH | STEP 0 |
| ครั้งแรกหลังบูต หรือหลังแก้โค้ด / USB / Docker | STEP 1–3 และ STEP 5 |
| **ทุกครั้งก่อนรันโปรแกรม** รวมถึงรันรอบสองในบูตเดียวกัน | STEP 4 |
| ทุกครั้งที่ทดลองหุ่นยนต์ | STEP 6–8 |

**เงื่อนไขการทดสอบบนพื้น:** ยังไม่รวมคำสั่งขับบนพื้นใน README นี้ เพราะหุ่นยนต์เคยชนจริง และยังไม่ได้สอบเทียบระยะเบรก/พื้นที่กวาด/วัตถุต่ำกว่า LiDAR ที่ความเร็ว `0.15 m/s` เมื่อทดสอบและยืนยันความปลอดภัยแล้วจึงทำขั้นตอนทดลองบนพื้นแยกต่างหาก อย่าใช้ `--mode wheels-up` เพื่ออ้างว่าได้ทดสอบบนพื้นสำเร็จ

หาก USB หลุด, LiDAR ไม่สแกน, Docker รีสตาร์ต, หรือใช้ `Ctrl+Z` ค้าง ให้กลับไปตรวจ STEP 2–4 ใหม่ แม้ยังไม่ได้ปิด Pi

---


## STEP 0 — SSH เข้า Raspberry Pi

**บน Windows CMD / PowerShell**

```
ssh pi@192.168.1.11
```

> `192.168.1.11` เป็น IP ของ Pi ที่ใช้ในการทดสอบก่อนหน้า หากเครือข่ายเปลี่ยนให้ใช้ IP ปัจจุบัน

**บน Raspberry Pi SSH**

```
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
pwd
python --version
```

**ต้องเห็น:** path `/home/pi/CatRobot-YOLO-Detector` และ Prompt มี `(.venv)`; Python เรียกใช้งานได้


---


## STEP 1 — ตรวจโค้ด Final V6, Python Modules และ YOLO

ทำ **ครั้งเดียวหลังเปิดเครื่อง** และทำซ้ำเมื่อแก้โค้ด, เปลี่ยน `.venv` หรืออัปเดตแพ็กเกจ

```
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate

echo '===== 1. REQUIRED FILES ====='
missing=0
for f in \
  run_teleop_yolo_real.py \
  robot_teleop_yolo_robot.py \
  dino_auto_center.py \
  dino_auto_meow.py \
  dino_motion.py \
  dino_help_resume_v6.py \
  dino_avoidance_v6.py \
  lidar_directional_avoidance.py \
  lidar_360_guard.py \
  lidar_buzzer_tiers.py \
  tmini_plus_lidar.py \
  robot_teleop.py \
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
  dino_auto_center.py \
  dino_auto_meow.py \
  dino_motion.py \
  dino_help_resume_v6.py \
  dino_avoidance_v6.py \
  lidar_directional_avoidance.py \
  lidar_360_guard.py \
  lidar_buzzer_tiers.py \
  tmini_plus_lidar.py \
  robot_teleop.py && echo 'PASS: PYTHON SYNTAX'

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


## ค่าที่ต้องตรงกับ CatRobot ล่าสุด

| **ระบบ**                  | **ค่า**                         |
| ------------------------- | ------------------------------- |
| AUTO SOS ด้านหน้า         | 36 ซม.                          |
| Resume เดินหน้าหลัง SOS   | 37 ซม.                          |
| WAIT_HELP หน้า/หลัง       | 29 ซม.                          |
| WAIT_HELP ด้านข้าง/360°   | 26 ซม.                          |
| Dino Tracking             | Conf 0.10 / 1 frame             |
| Dino Arrival              | Box 4.5% + Center               |
| Dino Departure            | 4 เฟรมที่ขนาดกรอบเล็กลงตามเกณฑ์ |
| ความเร็วทดลอง AUTO/MANUAL | สูงสุด 0.15 m/s                 |

ข้อสำคัญ: การตรวจพบ Flag ใน Source ไม่ได้หมายความว่าเปิดใช้งานแล้ว ต้องตรวจคำสั่งรันและ Log ด้วย และการตรวจ Syntax ผ่านไม่ได้ยืนยันว่าทุกฟังก์ชันทำงานครบ

**ผลที่ต้องได้:** ไฟล์ครบ, `PASS: PYTHON SYNTAX`, `PASS: ALL MODULES` และเห็น AUTO hooks / Parallel Mode / เกณฑ์ SOS36 → Rearm37. ถ้ามี `FAIL` ให้แก้ปัญหานั้นก่อน อย่าเพิ่งเปิดมอเตอร์


---


## STEP 2 — ตรวจ USB และ Serial Ports

ทำ **ครั้งแรกหลังเปิดเครื่อง** หรือเมื่อถอดเสียบ USB, LiDAR มีปัญหา หรือไฟเลี้ยงไม่เสถียร

```
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

ผลที่เคยพบจากเครื่องนี้:

| **อุปกรณ์**       | **ค่าที่เคยพบ** | **หมายเหตุ**       |
| ----------------- | --------------- | ------------------ |
| LiDAR T-Mini Plus | /dev/ttyUSB0    | USB–UART CP2102    |
| Motor Controller  | /dev/ttyUSB1    | USB–UART CH341     |
| Motor symlink     | /dev/myserial   | ใช้ตรวจเส้นทางจริง |

**สำคัญ:** `ttyUSB0` / `ttyUSB1` อาจสลับหลังรีบูต ให้ยึดผลจาก `readlink -f` ไม่เดาพอร์ตและไม่สลับสายโดยไม่จำเป็น LiDAR Port ควรว่างก่อนเปิดโปรแกรมหลัก; Motor Port อาจถูกครอบครองโดย ROS2 Motor Driver ใน Docker ตามปกติ


---


## STEP 3 — ตรวจ Docker, หยุด Motor Driver ตัวผิด และตรวจ ROS2

**ทำครั้งแรกหลังเปิด Raspberry Pi ใหม่ทุกครั้ง** และทำใหม่เมื่อ Docker/Motor Driver รีสตาร์ตหรือสลับตัวเอง เพราะเครื่องนี้เคยเปิด Container อื่นแทน `affectionate_lamport` หลังบูต

ก่อนจัดการ Container: กด STOP หากหน้าเว็บยังเข้าถึงได้ ยืนยันว่าล้อหยุด และ **ตัดกำลังไฟมอเตอร์ระหว่างเปลี่ยน Driver** ไม่สั่ง `docker stop`/`docker start` ขณะหุ่นยนต์อาจเคลื่อนที่ได้

### 3.1 — ดู Container ที่ Docker เปิดจริง

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

**ที่ต้องการ:** Motor Driver สำหรับโปรเจกต์นี้คือ Container ชื่อ **`affectionate_lamport`** เท่านั้น ส่วน Container ชื่ออื่น **ยังไม่ถือว่าผิดโดยอัตโนมัติ** ต้องตรวจว่าเป็น Driver ที่แย่ง `/dev/myserial` / `/dev/ttyUSB*` หรือสั่ง `/cmd_vel` ด้วยหรือไม่

### 3.2 — ถ้ามี Motor Driver ตัวอื่นเปิดผิดตัว: ตรวจชื่อก่อน แล้วสั่งหยุด

ตรวจ Container ที่สงสัย โดยใช้ชื่อ **ที่ขึ้นจาก `sudo docker ps` จริง** เช่นหากพบ `interesting_feynman`:

```bash
OTHER_CONTAINER="interesting_feynman"

sudo docker inspect -f 'Name={{.Name}} Image={{.Config.Image}} Restart={{.HostConfig.RestartPolicy.Name}} Privileged={{.HostConfig.Privileged}} Devices={{json .HostConfig.Devices}}' "$OTHER_CONTAINER"
sudo docker top "$OTHER_CONTAINER"
```

> `interesting_feynman` เป็น **ตัวอย่างชื่อที่เคยพบ** ไม่ใช่การยืนยันว่าตัวนี้เป็น Driver ผิดในบูตปัจจุบัน ให้เปลี่ยน `OTHER_CONTAINER` เป็นชื่อที่ตรวจพบ และยืนยันก่อนว่ามันเป็น Motor Driver ซ้ำ/ครอบครองพอร์ตจริง ไม่ใช่ Container สำหรับงานอื่น

**เมื่อยืนยันแล้วว่าเป็น Motor Driver ตัวที่ผิด** ให้ใช้คำสั่งนี้:

```bash
sudo docker stop "$OTHER_CONTAINER"
```

หรือเขียนแบบใส่ชื่อโดยตรง เช่น **เฉพาะเมื่อยืนยันว่า `interesting_feynman` เป็นตัวที่ผิดจริง**:

```bash
sudo docker stop interesting_feynman
```

รูปแบบคำสั่งทั่วไปคือ `sudo docker stop ชื่อคอนเทนเนอร์` — **อย่าพิมพ์ `(DOCKER NAME)` หรือ `<DOCKER NAME>` ตรง ๆ ใน Terminal** เพราะวงเล็บและเครื่องหมาย `<` มีความหมายพิเศษใน Shell

ตรวจซ้ำว่า Container ที่ผิดหยุดแล้ว:

```bash
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
```

**ไม่ใช้** `sudo docker stop $(sudo docker ps -q)` หรือหยุดทุก Container แบบเหมารวม

### 3.3 — เปิด Motor Driver ที่เราใช้จริง

หาก `affectionate_lamport` ยังไม่ได้ `Up` และแน่ใจว่า Driver ตัวผิดหยุดแล้ว:

```bash
sudo docker start affectionate_lamport
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
```

หาก Container ที่ถูกต้อง `Up` อยู่แล้ว **ไม่ต้องสั่ง start ซ้ำ** หากเปิดไม่ขึ้น ให้ตรวจ `sudo docker logs --tail 80 affectionate_lamport` แทนการเปิด Container ใหม่เพิ่ม

### 3.4 — ตรวจ ROS2 `/cmd_vel` หลังเลือก Container ถูกต้อง

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

**ผลที่ต้องการ:** `/cmd_vel` มี `Subscription count: 1`, ชื่อ node ฝั่ง Driver เช่น `driver_node`, และ Topic type `geometry_msgs/msg/Twist` อย่าเปิด CatRobot Runner จนกว่าจะยืนยันว่าใช้ Motor Driver ถูกตัวและไม่มีตัวอื่นควบคุมมอเตอร์ซ้ำ

### 3.5 — ทางเลือก: ป้องกัน Driver ผิดตัวเปิดเองหลังรีบูต

หากตรวจแน่ชัดแล้วว่า Container ผิดตัวถูกตั้งให้เริ่มอัตโนมัติทุกครั้ง สามารถตรวจ Restart Policy ได้ด้วย:

```bash
sudo docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$OTHER_CONTAINER"
```

**เฉพาะเมื่อผู้ดูแลเครื่องตกลงให้ปิดการเริ่มอัตโนมัติของ Container นั้น** ใช้:

```bash
sudo docker update --restart=no "$OTHER_CONTAINER"
```

คำสั่งนี้เปลี่ยนการตั้งค่า Docker แบบถาวรข้ามการรีบูต **ไม่ลบ Container และไม่หยุด Container ที่กำลังรัน** (จึงต้องใช้ `docker stop` แยกต่างหาก) ควรจด Restart Policy เดิมไว้ก่อน และไม่เปลี่ยน Policy ของ `affectionate_lamport` หรือ Container ที่ไม่ทราบหน้าที่

---


## STEP 4 — CHECK & CLEAN ก่อนเปิด CatRobot ทุกครั้ง

แม้ผ่าน STEP 1–3 มาแล้ว ต้องทำขั้นนี้ **ทุกครั้งก่อนรัน CatRobot** รวมทั้งหลัง `Ctrl+C`, หลัง SSH หลุด หรือจะรันใหม่ในบูตเดียวกัน

```
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

**ก่อนรันต้องได้:** Port 8080 ว่าง, ไม่มี Runner CatRobot ค้าง, LiDAR Serial ไม่มีโปรแกรมอื่นจับ, `/dev/video0` มีอยู่ และ Motor Driver ยังทำงาน

### กรณี Port 8080 ยังมี `LISTEN`

**อย่าเพิ่งเปิดโปรแกรมใหม่ซ้อน** ตรวจ PID ก่อน:

```
sudo ss -ltnp | grep ':8080'
ps -o pid,ppid,stat,tty,cmd -p PID_HERE
```

ให้แทน `PID_HERE` ด้วยเลขจริงจาก `ss` ไม่พิมพ์คำว่า `PID_HERE` ตามตัวอักษร

ถ้าเป็น CatRobot ที่เปิดจาก Terminal เดิม: กด **STOP** บนเว็บ, ยืนยันว่าล้อหยุด, แล้วกด `Ctrl+C` ใน Terminal ที่รัน CatRobot (ห้าม `Ctrl+Z` เพราะเป็นการพักงาน)

ถ้าหา Terminal เดิมไม่พบ: **ตัดกำลังมอเตอร์ก่อน**, ยืนยัน PID ว่าเป็นโปรแกรม CatRobot ที่ค้างอยู่จริง แล้วจึงใช้:

```
kill -TERM PID_HERE
```

ถ้า `STAT` เป็น `T`/\`t\` (โปรแกรมถูกพักด้วย `Ctrl+Z`) ให้ตรวจความปลอดภัยและตัดกำลังมอเตอร์ก่อน แล้วจึงใช้ `kill -CONT PID_HERE` ตามด้วย `kill -TERM PID_HERE` เพื่อปิดอย่างเป็นระเบียบ; คำสั่ง `CONT` อาจทำให้โค้ดเริ่มทำงานใหม่ทันที อย่าใช้ขณะรถสามารถเคลื่อนที่ได้

ตรวจซ้ำจนเห็น `PORT 8080 FREE` ถ้ายังไม่ว่างหรือมี `MOTOR STOP FAILED` ให้หยุดการทดสอบและตรวจสาเหตุ ไม่บังคับฆ่าโปรเซสขณะมอเตอร์มีกำลังไฟ

### กรณี LiDAR ไม่สแกน

หากพอร์ตไม่มีโปรแกรมอื่นใช้อยู่ แต่ LiDAR ยังไม่เริ่ม ให้ปิด CatRobot และตัดกำลังมอเตอร์ก่อน ตรวจสายและพอร์ต แล้วลองถอด–เสียบ USB LiDAR เมื่อปลอดภัย จากนั้นทำ STEP 2 และ STEP 4 ซ้ำ อย่ารีเซ็ต Docker ทุกตัวหรือเปลี่ยนค่า Safety Gate เพื่อแก้ปัญหาพอร์ต


---


## STEP 5 — ตรวจ YOLO Model และ Audio

ทำหลังบูตครั้งแรก หรือเมื่อมีการเปลี่ยนโมเดล/ลำโพง/ไฟล์เสียง ก่อนเริ่มโปรแกรมหลัก

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

การมีไฟล์ครบไม่ได้ยืนยันว่าเสียงออกลำโพงได้หรือโมเดลตรวจ Dino ได้จริง ต้องตรวจ Log ใน STEP 7 ด้วย **ไม่เล่นเสียงและไม่ขับมอเตอร์เป็นส่วนหนึ่งของการตรวจนี้**

---


## STEP 6 — รัน CatRobot V6 ล่าสุด (wheels-up)

> **ทำเฉพาะเมื่อหุ่นยนต์ถูกยึดบนแท่นที่ล้อยกพ้นพื้นแล้ว** ป้องกันการไถล/หล่น และเตรียมการตัดกำลังมอเตอร์ไว้ นี่คือโหมดทดลอง ไม่ใช่คำสั่งใช้งานบนพื้น

**คัดลอกโค้ด Bash ทั้งชุดด้านล่างไปที่ SSH Terminal ของ Pi** ข้อควรระวัง: อย่าเว้นบรรทัดเปล่าระหว่างบรรทัดที่ลงท้ายด้วย `\` เพราะจะทำให้คำสั่งแตกเป็นหลายส่วน

```
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
sudo -v

unset CATROBOT_AVOIDANCE_V7 CATROBOT_AVOIDANCE_V3 CATROBOT_AVOIDANCE_V4 CATROBOT_SPEED_TRIAL CATROBOT_STABLE_SPEED_08

LIDAR_PORT="$(readlink -f /dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0)"
if [ ! -c "$LIDAR_PORT" ]; then
  echo 'FAIL: LIDAR PORT INVALID — DO NOT START ROBOT'
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

**ความเร็ว:** โค้ดด้านบนเปิด `CATROBOT_BENCH_SPEED_015=1` = คำสั่งเดินหน้าสูงสุด 0.150 m/s สำหรับ AUTO/MANUAL บนแท่น; `w` เป็นความเร็วหมุน หน่วย rad/s เช่น 0.190 rad/s ไม่ใช่ 0.190 m/s หากต้องทดสอบช่วงแรกด้วย 0.08 ให้ปิด Runner ก่อน แล้วเปลี่ยนบรรทัดเดียว `CATROBOT_BENCH_SPEED_015=1` เป็น `CATROBOT_STABLE_SPEED_08=1` พร้อมเปลี่ยนชื่อไฟล์ Log

**เปิดเว็บจากคอมพิวเตอร์ที่อยู่ในเครือข่ายเดียวกัน:** `http://192.168.1.11:8080` → ควรเริ่มใน STOPPED; ตรวจ STOP ก่อนทดลอง MANUAL/AUTO

### Log ที่ควรเห็นหลังเริ่มสำเร็จ

```
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

หากเห็น `WEB HEARTBEAT LOST`, `AVOID`, `LIDAR scan stale`, `MOTOR ERROR`, หรือ `MOTOR STOP FAILED` อย่าปลด Gate; ตรวจ log และ STEP 2–4 ก่อน


---


## STEP 7 — ทดสอบ AUTO, SOS, Dino Arrival และ Resume (ล้อยกบนแท่น)

```text
AUTO + ตรวจพบ Dino (YOLO TRACK >= 0.10 / 1 frame)
               |
               +-- Dino อยู่ไกลกว่าเกณฑ์ภาพ + เส้นทางปลอดภัย
               |      -> FOLLOW (Servo ตาม + มอเตอร์ตาม Dino)
               |
               +-- Dino ใกล้ (box >= 4.5% ของพื้นที่ภาพ)
               |      -> หยุดเดินหน้า + Servo จัด Dino ให้อยู่กลางภาพ
               |      -> กลางภาพ, ผ่านเงื่อนไขเสียง/ความปลอดภัย
               |      -> meow.wav (เสียงถึงเป้าหมาย)
               |      -> ถ้า Dino ถอยจน box <= 3.06% ต่อเนื่อง 4 เฟรมใหม่
               |      -> กลับ FOLLOW ถ้า Motor Gate อนุญาต
               |
               +-- AUTO กำลังเดินหน้าและ LiDAR ด้านหน้า < 36 ซม.
                      -> หยุดมอเตอร์ทันที -> SOS หนึ่งชุด -> WAIT_HELP
                      -> รอข้อมูล LiDAR ใหม่ต่อเนื่อง >= 2.5 วินาที
                         และ >= 6 สแกนใหม่
                      -> ต้องเห็น Dino ที่ผ่านเกณฑ์อีกครั้ง
                      -> Front >= 29 ซม., Rear >= 29 ซม.,
                         Side / 360 >= 26 ซม.
                      -> หากจะเดินหน้า ต้อง Front >= 37 ซม.
                      -> ตรวจเส้นทางที่จะขับด้วย Motor Safety Gate
                      -> WAIT_HELP -> IDLE -> FOLLOW Dino ต่อ
                         (หรือ ARRIVED ถ้า Dino ยังใกล้อยู่)
```

### เกณฑ์ล่าสุด

| **รายการ**                                  | **ค่า**                             | **ผลที่ใช้**                                             |
| ------------------------------------------- | ----------------------------------- | -------------------------------------------------------- |
| AUTO STOP + เข้า WAIT_HELP ด้านหน้า         | < 36 ซม.                            | หยุดก่อนสิ่งกีดขวางขณะกำลังเดินหน้า                      |
| AUTO กลับไปเดินหน้าหลัง WAIT_HELP           | >= 37 ซม.                           | ช่วยไม่ให้หยุด–ปลดซ้ำ                                    |
| WAIT_HELP ด้านหน้า/หลัง (ตรวจพื้นที่ทั่วไป) | >= 29 ซม.                           | เงื่อนไขตรวจพื้นที่ ไม่ใช่อนุญาตให้เดินหน้าในระยะ 29 ซม. |
| WAIT_HELP ด้านข้าง/ใกล้สุดรอบตัว            | >= 26 ซม.                           | เงื่อนไขก่อนปลดสถานะ                                     |
| Motor Gate เดินหน้า/ด้านข้าง                | 28 / 26 ซม.                         | เป็นชั้นป้องกันแยกต่างหาก                                |
| ระยะฉุกเฉินรอบ 360°                         | 22 ซม.                              | ฉุกเฉินแยกจาก WAIT_HELP                                  |
| ปลด WAIT_HELP                               | 2.5 วินาที + 6 สแกนใหม่ + เห็น Dino | ต้องผ่านการตรวจทิศทางจริงด้วย                            |
| YOLO Tracking                               | conf `0.10`, `1 frame`              | ยังคงค่าที่เลือกไว้                                      |
| Dino ใกล้ (box area)                        | 4.5% ของภาพ                         | ไม่ใช่ระยะเป็นเซนติเมตร                                  |
| Dino ออกห่าง                                | ≤3.06% ของภาพ × 4 เฟรมใหม่          | กลับ FOLLOW เมื่อตรวจเส้นทางผ่าน                         |

**หมายเหตุ:** เงื่อนไข `36 ซม.` ใช้กับการเดินหน้า AUTO และขึ้นอยู่กับการวัดระยะจาก LiDAR ไม่ใช่จากกันชนจริง รถยังอาจชนวัตถุที่ LiDAR 2D ไม่เห็น หรือชนจากระยะเบรกไม่พอ โดยเฉพาะที่ 0.15 m/s. `WAIT_HELP` ไม่ได้ถอยหรือหมุนหาทางอ้อมอัตโนมัติ; หากยังไม่ปลอดภัย รถต้องหยุดและรอการช่วยเหลือ

### ตรวจ Flow ผ่าน Log

```
grep -E 'BENCH SPEED|STABLE SPEED|BRIDGE_DIAG speed_limit|DINO CAMERA|ORANGE FOLLOW|DRIVE GATE|REAL MOTOR|AUTO ZERO DIAG|HELP V6|HELP WAIT DIAG|HELP V6 SOS|DINO ARRIVAL V6|DINO CLOSE MEOW|Playing meow.wav|OBSTACLE BUZZER|MOTOR ERROR|MOTOR STOP FAILED' \
  ~/catrobot_v6_sos36_flow_final_015.log | tail -n 180
```

หากไม่เห็น `Playing meow.wav` แต่ได้ `meow_7.wav` หรือ `meow_m.wav` นั่นคือเสียงแมวชุดปกติ **ไม่ใช่เสียงถึง Dino**; ต้องตรวจเงื่อนไขขนาดกล่องและตำแหน่งกลางภาพอีกครั้ง

### ทดสอบบนพื้น (เฉพาะหลังสอบเทียบผ่าน)

ส่วนนี้เป็น **เงื่อนไขอนุมัติให้ทดสอบในอนาคต ไม่ใช่คำสั่งให้เริ่มขับทันที**: ต้องยืนยันการเบรกที่ความเร็วจริง, ระยะจาก LiDAR ถึงกันชนหน้า/หลัง, พื้นที่กวาดของล้อและตัวรถขณะหมุน, วัตถุที่อยู่ต่ำกว่าระนาบ LiDAR, ปุ่ม STOP/การตัดกำลังไฟ และสถานะหลุดสัญญาณเว็บ/ROS2 จึงค่อยจัดทดสอบควบคุมบนพื้นแยกต่างหาก พร้อมคนคุมสวิตช์กำลังมอเตอร์

หากยังไม่ผ่านข้อใด ให้คงการทดสอบแบบยกล้อเท่านั้น ไม่ลดเกณฑ์ LiDAR เพื่อให้รถเคลื่อนที่ได้


---


## STEP 8 — STOP, ปิดโปรแกรมและ Shutdown ให้ถูกต้อง

1. กด **STOP** ที่หน้าเว็บ และยืนยันว่าล้อหยุดจริง
2. ใน Terminal ที่กำลังรัน CatRobot ให้กด **`Ctrl+C`** (ไม่ใช่ `Ctrl+Z`)
3. ตรวจว่าเว็บพอร์ตว่างและไม่มี Runner ค้าง

```
sudo ss -ltnp | grep ':8080' || echo 'PORT 8080 FREE'
ps -eo pid,ppid,stat,cmd | grep -E '[r]un_teleop_yolo_real.py' || echo 'NO CATROBOT RUNNER'
```

หากต้องเปิดใหม่ในบูตเดียวกัน ให้กลับไป **STEP 4** ก่อนทุกครั้ง ไม่ต้องทำ STEP 1–3 ใหม่หากไม่มี USB/ROS2/ไฟเลี้ยงเปลี่ยนแปลง

หาก STOP ไม่หยุดล้อหรือมี `MOTOR STOP FAILED` ให้ตัดกำลังมอเตอร์และหยุดทดสอบก่อนตรวจระบบ ห้ามอาศัยการปิด SSH หรือ `Ctrl+Z` เพื่อหยุดมอเตอร์

หากต้องการ **Shutdown Raspberry Pi ทั้งเครื่อง** หลังตรวจว่าล้อหยุดแล้วและปิด Runner สำเร็จ ให้บันทึกงานที่กำลังทำอยู่และใช้:

```bash
sudo shutdown -h now
```

รอให้ Pi ปิดระบบเรียบร้อยก่อนถอดไฟเลี้ยง อย่าใช้ Shutdown แทนปุ่ม STOP ฉุกเฉิน และอย่า Shutdown ขณะมอเตอร์ยังสั่งเคลื่อนที่อยู่


---


## Quick Reference — คำสั่งสั้นสำหรับวันถัดไป

**หลังเปิด Pi ใหม่:** STEP 0 → 1 → 2 → **3 (ดู Container, หยุดเฉพาะ Driver ผิด, เปิด `affectionate_lamport`, ตรวจ ROS2)** → 4 → 5 → 6

**ถ้าจะรัน CatRobot รอบที่สองในบูตเดียวกัน:** STOP + `Ctrl+C` → STEP 4 → 6 (ย้อน STEP 3 หาก Docker เปลี่ยน)

**ถ้า Docker เปิดผิดตัวหลังรีบูต:** STEP 3.1 → 3.2 → 3.3 → 3.4 ก่อนเริ่ม STEP 6

**ถ้า LiDAR/USB/Docker มีปัญหา:** STOP → ปิด Runner → STEP 2 → 3 → 4 → 5 (ตามอาการ) → 6

**ถ้าเปลี่ยนหรืออัปเดตโค้ด:** STOP → ปิด Runner → STEP 1 → 2–5 (ตามความจำเป็น) → 6

**เมื่อจบการทดลอง:** STEP 8: STOP → `Ctrl+C` → ตรวจพอร์ต/โปรเซส → ปิดเครื่องอย่างปลอดภัย

เอกสารนี้บันทึกการตั้งค่าและขั้นตอนตรวจจากแพตช์/Log ที่เคยใช้งาน ไม่ได้ยืนยันว่าปลอดภัยต่อการขับบนพื้นจริงหรือครอบคลุมสิ่งกีดขวางทุกระดับความสูง
