# T-MINI Plus LiDAR + ROSMASTER M1 Setup Guide

## เป้าหมาย

เชื่อม **YDLIDAR T-MINI Plus** เข้ากับโปรเจกต์ YOLO V7.2 เพื่อใช้ตรวจสิ่งกีดขวางก่อนอนุญาตให้ ROSMASTER M1 เคลื่อนที่

ใช้ Python บน Raspberry Pi โดยตรง ไม่ต้องติดตั้ง Docker หรือ ROS2 ใหม่

**สถานะ:** โค้ด Integration สำหรับทดสอบ ยังไม่ได้ผ่านการตรวจ Hardware จริง

## ไฟล์ที่ใช้

- `robot_teleop_yolo_robot.py` — ระบบ YOLO, Web UI, Motor เดิม
- `tmini_plus_lidar.py` — ตัวอ่าน T-MINI Plus และตรวจพื้นที่ว่าง
- `robot_teleop_yolo_lidar.py` — ตัวเริ่มโปรแกรมเชื่อม LiDAR กับ Robot
- `tests/test_tmini_plus_lidar.py` — ทดสอบ Safety Logic แบบจำลอง

**ห้ามทับ `robot_teleop.py` ต้นฉบับของเพื่อน**

## ข้อมูลอุปกรณ์

| รายการ | T-MINI Plus |
|---|---|
| ผู้ผลิต | YDLIDAR |
| ประเภท | 2D 360° LiDAR |
| การวัดระยะ | ToF |
| ความถี่สแกน | 6–12 Hz |
| Baud rate | 230400 |
| Sampling rate ใน SDK example | 4 |
| SingleChannel | False |
| SDK lidar type | TYPE_TRIANGLE ตามตัวอย่าง Python เฉพาะรุ่น |
| Driver ที่ใช้ | Official YDLidar-SDK |

ข้อควรระวัง: 2D LiDAR เห็นเฉพาะวัตถุที่ตัดผ่านระนาบสแกน จึงไม่รับประกันว่าจะเห็นตุ๊กตาเล็ก พื้นต่างระดับ หรือสิ่งกีดขวางทุกชนิด

---

# PHASE T0 — เตรียม Raspberry Pi ขณะมีอินเทอร์เน็ต

## T0.1 ตรวจระบบ

```bash
uname -m
python3 --version
cat /etc/os-release
df -h /
```

- [ ] ทราบสถาปัตยกรรม CPU
- [ ] ทราบ Python Version
- [ ] ตรวจพื้นที่ว่างแล้ว

## T0.2 เข้าโปรเจกต์

```bash
cd ~/CatRobot-YOLO-Detector
```

ถ้ามีไฟล์ที่เพื่อนแก้เองอยู่ ให้สำรองไว้ก่อน Pull

```bash
git status
```

ถ้าไม่มีงานค้างและเป็น Repository ถูกต้อง:

```bash
git pull --ff-only origin main
```

ตรวจไฟล์:

```bash
ls -l tmini_plus_lidar.py
ls -l robot_teleop_yolo_lidar.py
ls -l robot_teleop_yolo_robot.py
ls -l docs/TMINI_PLUS_SETUP_TH.md
```

ต้องเห็นครบทุกไฟล์

## T0.3 ติดตั้งเครื่องมือสำหรับ Compile SDK

ทำขณะยังออนไลน์:

```bash
sudo apt update
sudo apt install -y git cmake build-essential pkg-config swig python3-dev libusb-1.0-0-dev
```

หากติดตั้งไม่ผ่าน ให้ส่ง Error กลับทีมก่อน ไม่ข้ามขั้นตอน

---

# PHASE T1 — ระบุ Serial Port ของ LiDAR

## T1.1 ตรวจ USB

```bash
lsusb
```

```bash
ls -l /dev/serial/by-id/
```

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
```

ไม่ใช่ทุกเครื่องจะมี `/dev/ttyUSB0` และ Port ที่ขึ้นอาจเป็นอุปกรณ์ของมอเตอร์แทน LiDAR ได้

**ให้ระบุ Port จากการถอดและเสียบ LiDAR เทียบกันโดยไม่ถอดอุปกรณ์ผิดตัว**

ตรวจ Log หลังเสียบ LiDAR:

```bash
sudo dmesg | tail -n 30
```

บันทึก Serial Port จริงไว้

ตัวอย่าง:

```text
/dev/ttyUSB0
```

ถ้าพบ Path ใน `/dev/serial/by-id/` ที่ชี้ไปยัง LiDAR ให้ใช้ Path นั้นได้ เพราะช่วยลดปัญหาเลข USB เปลี่ยน

## T1.2 ตรวจ Permission

```bash
ls -l /dev/ttyUSB0
```

หาก Port จริงไม่ใช่ `/dev/ttyUSB0` ให้เปลี่ยนตามค่าที่ตรวจพบ

```bash
groups
```

หาก Permission ไม่อนุญาตให้เปิด Serial และอุปกรณ์อยู่ในกลุ่ม `dialout` ให้เพิ่มผู้ใช้:

```bash
sudo usermod -aG dialout "$(whoami)"
```

จากนั้น Logout/Login หรือ Reboot แล้วตรวจ `groups` ใหม่

ไม่ใช้ `chmod 777` เป็นวิธีแก้ถาวร

---

# PHASE T2 — ติดตั้ง Official YDLidar SDK

## T2.1 ดาวน์โหลด SDK ตอนออนไลน์

```bash
cd ~
git clone https://github.com/YDLIDAR/YDLidar-SDK.git
```

ตรวจ:

```bash
cd ~/YDLidar-SDK
git status
```

## T2.2 Build C/C++ SDK

```bash
mkdir -p build
cd build
cmake ..
make -j2
sudo make install
sudo ldconfig
```

ถ้า Build ไม่ผ่าน ให้ส่ง Error, OS, Python Version และ Architecture กลับทีมก่อน

## T2.3 ติดตั้ง Python SDK ใน Environment ของ YOLO

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
```

ตรวจ Python:

```bash
which python
```

ติดตั้ง YDLidar Python Module:

```bash
cd ~/YDLidar-SDK
python -m pip install .
```

ตรวจ Import:

```bash
python -c "import ydlidar; print('YDLIDAR SDK IMPORT OK')"
```

ตรวจว่า SDK มีค่าที่ใช้สำหรับ T-MINI Plus:

```bash
python -c "import ydlidar; print(ydlidar.TYPE_TRIANGLE, ydlidar.LidarPropSerialBaudrate)"
```

- [ ] Compile SDK ผ่าน
- [ ] `import ydlidar` ผ่านใน `.venv` ของ YOLO
- [ ] ตรวจ Serial Port แล้ว

หาก SDK ถูกติดตั้งใน Python ระบบแต่ไม่อยู่ใน `.venv` ให้แก้ Environment ก่อน อย่าสลับ Python ไปมาโดยไม่ตรวจ

---

# PHASE T3 — ตรวจ Motor Library ใน Environment เดียวกัน

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
```

```bash
python -c "from Rosmaster_Lib import Rosmaster; print('ROSMASTER IMPORT OK')"
```

ถ้าผ่าน ให้ทำต่อ

ถ้าไม่ผ่าน ให้ตรวจ Python ระบบ:

```bash
python3 -c "import Rosmaster_Lib; print(Rosmaster_Lib.__file__)"
```

ถ้า Import จาก Python ระบบได้ แต่จาก `.venv` ไม่ได้ ให้ส่งตำแหน่ง Library กลับทีมเพื่อเลือกวิธีติดตั้ง/เชื่อม Environment ที่ถูกต้อง

อย่าโหลด Rosmaster Library ชื่อคล้ายกันจากอินเทอร์เน็ตมาแทนของหุ่นยนต์โดยไม่ตรวจ API

ตรวจ Libraries อื่น:

```bash
python -c "import torch, cv2, ultralytics, ydlidar; print('VISION + LIDAR OK')"
```

**ต้องผ่านทั้งหมดก่อนรัน Robot Integration**

---

# PHASE T4 — ทดสอบ LiDAR อย่างเดียวก่อน

**ขั้นนี้ไม่เปิด Motor**

ใช้ Port จริงที่ตรวจได้ โดยตัวอย่างสมมติว่าเป็น `/dev/ttyUSB0`

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
```

```bash
python robot_teleop_yolo_lidar.py --mode scan-only --port /dev/ttyUSB0 --front-angle 0
```

ควรเห็นการรายงานประมาณนี้:

```text
[TMINI] Scanning: /dev/ttyUSB0
[LiDAR] SCAN CLEAR | age: ... | points: ... | front: ... | left: ... | right: ...
```

หากขึ้น `INSUFFICIENT ... DATA` แต่ยังเห็นจำนวน Points เพิ่มขึ้น แสดงว่ามีการรับ Scan บางส่วนแล้ว แต่ข้อมูลยังไม่เพียงพอตามเกณฑ์ Safety

หากไม่เห็นการสแกนเลย ให้ตรวจ Serial Port, Permission, SDK และ Power Supply ก่อน

## T4.1 ทดลองสิ่งกีดขวาง

ให้มีคนถือแผ่นกระดาษแข็งหรือวัตถุที่ LiDAR ตรวจจับได้ อยู่บริเวณด้านหน้าที่ระดับความสูงเดียวกับระนาบสแกน

- [ ] เมื่อไม่มีสิ่งกีดขวางใกล้ ระบบรายงานค่าระยะจากสภาพแวดล้อม
- [ ] เมื่อนำวัตถุเข้ามาด้านหน้า ค่า Front เปลี่ยน
- [ ] เมื่อนำวัตถุเข้ามาด้านซ้าย ค่า Left เปลี่ยน
- [ ] เมื่อนำวัตถุเข้ามาด้านขวา ค่า Right เปลี่ยน
- [ ] เมื่อวัตถุอยู่ใกล้กว่าค่าทดลอง ระบบรายงาน `OBSTACLE`
- [ ] เมื่อถอด LiDAR หรือข้อมูลขาด ระบบกลับเป็น `NOT READY` / `STALE`

**ถ้า Front/Left/Right ไม่ตรงกับทิศจริง อย่าทดลอง AUTO**

กด `Ctrl+C` เพื่อหยุด

---

# PHASE T5 — Calibrate ทิศหน้าของ LiDAR

ค่า `--front-angle` ใช้บอกว่าในข้อมูลสแกนของ LiDAR มุมใดตรงกับด้านหน้าของหุ่นยนต์

ไม่สามารถถือว่า `0°` ตรงกับหน้า Robot โดยอัตโนมัติ เพราะขึ้นอยู่กับตำแหน่งและองศาที่ติดตั้งเซนเซอร์

## วิธีตรวจ

1. ยืนยันว่าล้อหุ่นยนต์ไม่สามารถเคลื่อนที่
2. เปิด `scan-only`
3. นำวัตถุไปไว้ข้างหน้าหุ่นยนต์ในแนวระดับเลเซอร์
4. ตรวจว่าระยะด้านหน้าเปลี่ยนถูกต้อง
5. ตรวจซ้ำด้านซ้ายและด้านขวา
6. หากทิศผิด ให้ตรวจการติดตั้งและแก้ค่า `--front-angle`
7. ทำซ้ำจนระบุทั้งสามทิศได้ถูกต้อง

ตัวอย่างเมื่อยืนยันแล้วว่าใช้ 90°:

```bash
python robot_teleop_yolo_lidar.py --mode scan-only --port /dev/ttyUSB0 --front-angle 90
```

หากยังไม่สามารถยืนยันทิศได้ ให้หยุดที่ขั้นนี้

บันทึกค่าที่ผ่านการทดสอบ:

```text
LIDAR_PORT = ______________
FRONT_ANGLE_DEG = _________
```

---

# PHASE T6 — เตรียม Offline Backup เพิ่มเติม

ต้องทำตอน Raspberry Pi ยังเข้าถึงอินเทอร์เน็ตได้

เก็บ SDK Source ที่ดาวน์โหลดไว้:

```bash
cd ~/YDLidar-SDK
git rev-parse HEAD
```

บันทึก Commit ID ของ SDK ด้วย เพื่อให้ทีมรู้ว่า Build จากเวอร์ชันใด

สร้าง Wheel ของ SDK:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
mkdir -p offline/wheels
```

```bash
python -m pip wheel ~/YDLidar-SDK --no-deps -w offline/wheels
```

ตรวจ:

```bash
ls -lh offline/wheels
```

ควรเก็บ Backup ของโฟลเดอร์ `~/YDLidar-SDK` และ Wheel ที่ Build ได้ไว้กับข้อมูลออฟไลน์ของ Pi

**ข้อควรระวัง:** Wheel ของ Python ไม่ครอบคลุม System Libraries ที่ Build และติดตั้งด้วย `sudo make install` ดังนั้นการย้ายไป Pi เครื่องอื่นยังต้องตรวจ SDK และไฟล์ระบบด้วย

หาก `pip freeze` บันทึก `ydlidar` เป็น Local File URL ให้ตรวจ Lock File ก่อนนำไปติดตั้งใน Environment ใหม่ เพราะ Path แบบ Local อาจใช้ไม่ได้หากย้ายเครื่อง

ก่อนตัดอินเทอร์เน็ต ให้ยืนยัน:

- [ ] YOLO Import ผ่าน
- [ ] YDLidar Import ผ่าน
- [ ] Rosmaster Import ผ่าน
- [ ] LiDAR รับ Scan ได้
- [ ] Python Packages สำหรับ Offline ผ่าน
- [ ] มี Backup SDK Source และ SDK Wheel
- [ ] ทราบวิธีกู้ System Libraries หากต้องติดตั้งระบบใหม่

---

# PHASE T7 — ทดสอบ MANUAL Motor แบบยกล้อ

**ทำเฉพาะเมื่อมีผู้ควบคุมอยู่ตรงหุ่นยนต์ และยกล้อพ้นพื้นอย่างมั่นคง**

ตรวจให้แน่ใจว่าโปรแกรม Robot เดิมไม่ได้รันอยู่และไม่มีโปรแกรมอื่นใช้ Port 8080

```bash
sudo ss -ltnp | grep ':8080'
```

จากนั้น:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
```

```bash
python robot_teleop_yolo_lidar.py --mode manual-wheels-up --confirm-wheels-up
```

เปิดเว็บในเครือข่ายเดียวกัน:

```text
http://ROBOT_IP:8080
```

ทดสอบ:

1. หลังเริ่มโปรแกรม ล้อต้องหยุด
2. กด MANUAL
3. กด W ชั่วครู่ ตรวจทิศทางเดินหน้า
4. กด A ชั่วครู่ ตรวจทิศทางเลี้ยวซ้าย
5. กด D ชั่วครู่ ตรวจทิศทางเลี้ยวขวา
6. ปล่อยปุ่ม ต้องหยุด
7. กด SPACE หรือ STOP ต้องหยุด
8. ปิดหน้าเว็บ ตรวจว่าหยุด
9. ทดลองระบบหยุดฉุกเฉินที่เตรียมไว้

ตรวจว่า Motor Direction ถูกต้องทั้งหมด

**หากพบความผิดปกติ ให้ตัดกำลังมอเตอร์และหยุดการทดสอบ ไม่ใช่ลองซ้ำบนพื้น**

ขั้นนี้ยังไม่ได้ทดสอบ LiDAR กับ Motor พร้อมกัน

---

# PHASE T8 — ทดสอบ AUTO + LiDAR แบบยกล้อก่อน

ทำได้เมื่อผ่าน PHASE T4, T5 และ T7 แล้วเท่านั้น

ต้องตรวจ LiDAR, Front Angle และมีผู้ควบคุมพร้อมหยุดมอเตอร์

ตัวอย่างคำสั่งเมื่อยืนยันว่า Front Angle เป็น 0° จริง:

```bash
python robot_teleop_yolo_lidar.py --mode auto-supervised --port /dev/ttyUSB0 --front-angle 0 --confirm-orientation --confirm-supervised
```

เปิด:

```text
http://ROBOT_IP:8080
```

ตรวจ `/status` ด้วย:

```text
http://ROBOT_IP:8080/status
```

## T8.1 ตรวจสถานะ LiDAR

ต้องเห็น:

- `lidar_ready` เป็น `true` เฉพาะตอนสแกนผ่านเกณฑ์
- `lidar_reason` เป็น `SCAN CLEAR` เฉพาะตอนพื้นที่ที่ตรวจว่าง
- เมื่อมีสิ่งกีดขวาง `lidar_ready` เป็น `false`
- เมื่อข้อมูลขาดหรือหมดอายุ `lidar_ready` เป็น `false`

## T8.2 ตรวจ YOLO

- [ ] Dino อยู่ซ้าย → ต้องมี TURN LEFT
- [ ] Dino อยู่ขวา → ต้องมี TURN RIGHT
- [ ] Dino อยู่กลาง → มี FORWARD REQUESTED
- [ ] Dino หาย → NO TARGET - STOP
- [ ] Confidence ไม่ผ่าน → STOP

## T8.3 ตรวจ Motor Safety

ขณะยกล้อพ้นพื้น:

- [ ] ไม่มี Target → ล้อไม่หมุน
- [ ] LiDAR ไม่พร้อม → ล้อไม่หมุน
- [ ] มีสิ่งกีดขวาง → ล้อหยุด
- [ ] ดึงสายกล้อง → ล้อหยุดตามเงื่อนไข AUTO
- [ ] Web Heartbeat ขาด → ล้อหยุด
- [ ] กด STOP → ล้อหยุด
- [ ] เลือก MANUAL ระหว่าง AUTO TEST → ถูกปฏิเสธ

ถ้าข้อใดไม่ผ่าน **ห้ามปล่อยล้อลงพื้น**

---

# PHASE T9 — ทดสอบบนพื้นภายใต้การดูแล

ขั้นนี้ไม่ใช่การปล่อยหุ่นยนต์วิ่งเองโดยไม่มีคนอยู่ด้วย

ต้องผ่านการทดสอบ T8 และตรวจเพิ่มเติม:

- [ ] มีวิธีตัดกำลังมอเตอร์ได้โดยไม่ผ่าน Python หรือหน้าเว็บ
- [ ] ทดสอบการหยุดเมื่อ Controller มีปัญหาแล้ว
- [ ] ยืนยันว่าระนาบ LiDAR มองเห็นสิ่งกีดขวางที่ต้องหยุด
- [ ] มีวิธีป้องกันการชนตุ๊กตาที่อยู่ต่ำกว่าระนาบ LiDAR
- [ ] ไม่มีบันได ขอบตก หรือสิ่งกีดขวางที่ LiDAR ไม่สามารถตรวจพบ
- [ ] ทดสอบระยะเบรกจริงของหุ่นยนต์แล้ว
- [ ] ค่า Front/Side Stop Distance ถูกปรับจากผลทดสอบจริง
- [ ] มีคนพร้อมหยุด Robot ทุกช่วงเวลา

ให้เริ่มในพื้นที่เล็กที่ควบคุมได้ โดยใช้ความเร็วต่ำและทดสอบทีละพฤติกรรม

ห้ามตีความว่า Bounding Box ใหญ่เท่ากับระยะใกล้ที่ปลอดภัย หากตุ๊กตาอยู่ต่ำกว่า LiDAR ควรมีระบบวัดระยะเป้าหมายเพิ่มเติมหรือกลไกหยุดก่อนชนที่ผ่านการทดสอบ

---

# PHASE T10 — ทดสอบเสียงและส่งงานให้ทีม

ใน Robot Program:

- [ ] ปุ่ม Meow ใช้ได้
- [ ] เสียงออกจากลำโพง Pi
- [ ] Buzzer ใช้ได้
- [ ] เสียงไม่ทำให้การควบคุมมอเตอร์ค้าง
- [ ] STOP ระหว่างเล่นเสียงยังทำงานได้

ทดสอบ WAV:

```bash
command -v aplay
```

ตรวจ Sound Card:

```bash
aplay -l
```

หากเสียงไม่ออก ให้ตรวจ `AUDIO_DEV` ใน `robot_teleop_yolo_robot.py` และการเลือกอุปกรณ์เสียงจริง

---

# Troubleshooting

## 1. `ModuleNotFoundError: No module named ydlidar`

SDK Python Module ไม่อยู่ใน Environment ที่กำลังรัน

ตรวจ:

```bash
which python
python -m pip show ydlidar
```

แล้วติดตั้ง SDK ใน `.venv` ตาม PHASE T2

## 2. SDK Import ได้ แต่เปิด LiDAR ไม่ได้

ตรวจ Serial Port และ Permission:

```bash
lsusb
ls -l /dev/serial/by-id/
groups
```

ตรวจสาย USB และอุปกรณ์ที่อาจใช้ Port เดียวกัน

## 3. `Permission denied: /dev/ttyUSB0`

ตรวจสิทธิ์กลุ่ม Serial Device และ Login ใหม่หลังเพิ่มกลุ่ม `dialout`

## 4. LiDAR หมุนแต่ไม่มี Scan

ตรวจค่าตาม Official T-MINI Plus Example:

- Baud 230400
- SampleRate 4
- SingleChannel False
- TYPE_TRIANGLE ใน SDK Example

ตรวจแหล่งจ่ายไฟและ Driver ที่ตรงรุ่น

อย่าเปลี่ยนไปใช้ค่าของรุ่น TG15/TG30 โดยอัตโนมัติ

## 5. `INSUFFICIENT FRONT DATA`

มีจำนวนจุดวัดที่ใช้ได้ไม่พอตามเกณฑ์ที่ตั้งไว้

ตรวจ Orientation, มุม, ระยะ, สิ่งที่บังเลเซอร์ และความครอบคลุมของ Scan

อย่าลดเกณฑ์จำนวนจุดเพียงเพื่อทำให้ไฟสถานะเป็นเขียว

## 6. `STALE LIDAR DATA`

ข้อมูลสแกนไม่ใหม่พอ โปรแกรมจะปฏิเสธการเคลื่อนที่

ตรวจ FPS/CPU Load, USB, SDK และการรับ Scan

## 7. `AUTO BLOCKED: LIDAR NOT READY`

เกิดจาก LiDAR ไม่ผ่านเงื่อนไข หรือ Sensor ยังไม่ได้ Calibrate

ใช้ `scan-only` และตรวจ Reason ก่อน

## 8. `No module named Rosmaster_Lib`

ตรวจว่า Library ของมอเตอร์อยู่ใน `.venv` เดียวกับ YOLO หรือไม่

ห้ามแทน Library โดยไม่ทราบเวอร์ชันของหุ่นยนต์

## 9. กล้องใช้ไม่ได้หรือ Port 8080 ไม่ว่าง

หยุดโปรแกรมเดิมที่ยืนยันได้ว่าเป็นของทีมก่อน

ไม่รัน `robot_teleop.py`, Dry Run และ AUTO Integration พร้อมกัน

## 10. Robot ไม่หยุดตามที่สั่ง

ใช้ระบบหยุดฉุกเฉินหรือวิธีตัดกำลังมอเตอร์ที่เตรียมไว้ทันที

ห้ามทดสอบต่อจนกว่าจะตรวจพบสาเหตุ

---

# สิ่งที่ต้องรายงานกลับ

ส่งผลดังนี้:

1. รุ่น Raspberry Pi, OS และ Python Version
2. ผล `uname -m`
3. Serial Port ของ T-MINI Plus
4. ค่า Front Angle ที่ Calibrate แล้ว
5. ผล `import ydlidar`
6. ผล `import Rosmaster_Lib`
7. ภาพ Terminal ของ `scan-only`
8. ตัวอย่างค่า Front/Left/Right เมื่อวางสิ่งกีดขวาง
9. ผล MANUAL Motor Test แบบยกล้อ
10. ผล AUTO Motor Test แบบยกล้อ
11. Error Log ถ้ามี
12. วิดีโอสั้น ๆ แสดงระบบหยุดเมื่อมีสิ่งกีดขวาง

## Final Checklist

- [ ] ติดตั้ง SDK สำเร็จ
- [ ] LiDAR อ่านระยะได้
- [ ] Calibrate ทิศจริงแล้ว
- [ ] Offline Backup สำเร็จ
- [ ] YOLO + Rosmaster + YDLidar ใช้ Python Environment เดียวกัน
- [ ] Manual Wheels-Up Test ผ่าน
- [ ] AUTO Wheels-Up Test ผ่าน
- [ ] สิ่งกีดขวางทำให้หยุดได้
- [ ] ข้อมูล LiDAR หายแล้วหยุดได้
- [ ] Target หายแล้วหยุดได้
- [ ] Emergency Stop ผ่าน
- [ ] ความเสี่ยงจากวัตถุที่ LiDAR มองไม่เห็นได้รับการแก้ไข
- [ ] จึงเริ่มพิจารณาทดลองบนพื้นภายใต้การดูแล

## Official References

YDLidar-SDK:
https://github.com/YDLIDAR/YDLidar-SDK

Official T-MINI Plus Python Example:
https://github.com/YDLIDAR/YDLidar-SDK/blob/master/python/examples/tminiplus_test.py

T-MINI Plus Manufacturer:
https://www.ydlidar.com/product/ydlidar-t-mini-plus

Yahboom T-MINI Plus Resources:
https://github.com/YahboomTechnology/T-MINI-PLUS-Lidar