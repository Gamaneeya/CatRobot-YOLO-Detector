# CatRobot YOLO V7.2 — ROSMASTER M1 + T-MINI Plus LiDAR

**One-Page Setup & Testing Guide | คู่มือสำหรับเพื่อน**

โปรเจกต์ Interactive Cat Robot ใช้โมเดล YOLO11n V7.2 ตรวจจับตุ๊กตา Green Dino ผ่านกล้อง และใช้ YDLIDAR T-MINI Plus ช่วยตรวจสิ่งกีดขวางก่อนสั่งมอเตอร์ ROSMASTER M1

**เป้าหมาย:** ติดตั้งทุกอย่างบน Raspberry Pi ขณะมีอินเทอร์เน็ต จากนั้นสลับไปใช้เครือข่ายของหุ่นยนต์ ทดสอบกล้อง, YOLO, LiDAR, Motor และ Auto Follow ตามลำดับ

ไม่ใช้ Docker ไม่จำเป็นต้องติดตั้ง ROS2 เพิ่ม และ **ห้ามเขียนทับ `robot_teleop.py` ต้นฉบับของทีม**

> **สถานะ:** โค้ดและคู่มือเตรียมไว้สำหรับการทดลองแล้ว แต่ยังไม่ผ่านการยืนยันบน Raspberry Pi / Robot จริง ต้องทดสอบล้อพ้นพื้นก่อน และห้ามทดลองวิ่งบนพื้นหากระบบหยุดฉุกเฉินหรือการตรวจสิ่งกีดขวางยังไม่ผ่าน

---

# STEP 0 — เตรียมก่อนเริ่ม

สิ่งที่ต้องมี:

- Raspberry Pi บน ROSMASTER M1 พร้อมแบตเตอรี่
- กล้องที่ใช้งานได้
- YDLIDAR T-MINI Plus พร้อมสายเชื่อมต่อ
- Green Dino ตัวจริง
- คอมพิวเตอร์ที่เชื่อมต่อ Raspberry Pi ได้
- อินเทอร์เน็ตสำหรับติดตั้ง Packages
- ฐานรองหุ่นยนต์ที่ทำให้ล้อพ้นพื้นอย่างมั่นคง
- วิธีหยุดหรือตัดกำลังมอเตอร์ได้ทันทีโดยไม่ต้องพึ่งหน้าเว็บ

**ลำดับที่ต้องทำ**

1. ติดตั้งโปรแกรมและ Dependencies ขณะออนไลน์
2. ติดตั้ง YDLidar SDK
3. ตรวจ Motor Library
4. ตรวจ YOLO และกล้อง
5. อ่านข้อมูล LiDAR จริง
6. Calibrate ทิศ LiDAR
7. ทดสอบ MANUAL แบบยกล้อ
8. ทดสอบ AUTO + LiDAR แบบยกล้อ
9. ตรวจระบบหยุดและความเสี่ยงจากสิ่งกีดขวางที่เซนเซอร์มองไม่เห็น
10. จึงพิจารณาทดลองเดินตาม Dino บนพื้นแบบมีคนควบคุมดูแล

หากขั้นใดไม่ผ่าน หยุดที่ขั้นนั้นและบันทึก Error

---

# STEP 1 — ตรวจ Raspberry Pi ขณะมีอินเทอร์เน็ต

เปิด Terminal บน Raspberry Pi หรือเชื่อมต่อด้วย SSH:

```bash
ssh USERNAME@ROBOT_IP
```

แทน `USERNAME` และ `ROBOT_IP` ด้วยค่าจริงของเครื่อง

ตรวจระบบ:

```bash
uname -m
python3 --version
cat /etc/os-release
df -h /
```

บันทึก Architecture, Python Version, OS และพื้นที่ว่าง

ถ้าใช้ระบบ Linux 32-bit หรือพบปัญหา Compatibility ของ PyTorch ให้ตรวจให้เรียบร้อยก่อนติดตั้งต่อ

---

# STEP 2 — ดาวน์โหลดโปรเจกต์และติดตั้ง YOLO

## 2.1 ติดตั้งเครื่องมือระบบ

ทำขณะที่ Raspberry Pi ยังมีอินเทอร์เน็ต:

```bash
sudo apt update
sudo apt install -y git python3-pip python3-venv cmake build-essential pkg-config swig python3-dev libusb-1.0-0-dev v4l-utils libgl1 alsa-utils mpg123
```

หากมี Package ไม่รองรับ OS ให้หยุดและเก็บ Error ก่อน

## 2.2 ดาวน์โหลด Repository

```bash
cd ~
git clone https://github.com/Gamaneeya/CatRobot-YOLO-Detector.git
cd CatRobot-YOLO-Detector
```

หากเคย Clone ไว้แล้ว ไม่ต้อง Clone ซ้ำ ใช้:

```bash
cd ~/CatRobot-YOLO-Detector
git status
git pull --ff-only origin main
```

หาก `git pull` ไม่สำเร็จเพราะมีการแก้ไฟล์ค้างอยู่ ให้สำรองงานเดิมก่อน ไม่ใช้ `git reset --hard`

## 2.3 ตรวจไฟล์สำคัญ

```bash
ls -lh models/best.pt
ls -l robot_teleop_yolo_pi_dryrun.py
ls -l robot_teleop_yolo_robot.py
ls -l robot_teleop_yolo_lidar.py
ls -l tmini_plus_lidar.py
```

ไฟล์เหล่านี้ต้องอยู่ใน Repository

## 2.4 สร้าง Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

ตรวจ:

```bash
which python
```

ต้องชี้ไปยัง `.venv/bin/python` ของโปรเจกต์

## 2.5 ติดตั้ง Python Dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyserial
python -m pip check
```

ตรวจ Imports:

```bash
python -c "import torch, cv2, numpy, ultralytics; print('YOLO ENVIRONMENT OK')"
```

ถ้าไม่ผ่านให้แก้ก่อนเปลี่ยนเครือข่าย

---

# STEP 3 — ติดตั้ง T-MINI Plus LiDAR SDK

เราใช้ Official YDLidar-SDK สำหรับ T-MINI Plus โดยตรง

## 3.1 ดาวน์โหลด SDK

```bash
cd ~
git clone https://github.com/YDLIDAR/YDLidar-SDK.git
```

## 3.2 Build SDK

```bash
cd ~/YDLidar-SDK
mkdir -p build
cd build
cmake ..
make -j2
sudo make install
sudo ldconfig
```

รอให้แต่ละคำสั่งสำเร็จก่อนพิมพ์คำสั่งถัดไป

## 3.3 ติดตั้ง Python Module ใน Environment ของ YOLO

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
cd ~/YDLidar-SDK
python -m pip install .
```

ตรวจ:

```bash
python -c "import ydlidar; print('YDLIDAR SDK OK')"
```

ต้องแสดง:

```text
YDLIDAR SDK OK
```

## 3.4 ตรวจว่า YOLO กับ LiDAR อยู่ใน Python Environment เดียวกัน

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
python -c "import ultralytics, cv2, torch, ydlidar; print('VISION + LIDAR READY')"
```

หากขึ้น `ModuleNotFoundError` ให้ตรวจว่ากำลังใช้ `.venv` เดียวกันหรือไม่

---

# STEP 4 — ตรวจ Motor Library ของ ROSMASTER M1

โปรเจกต์ใช้ `Rosmaster_Lib` ของหุ่นยนต์สำหรับสั่งมอเตอร์

ใน Terminal ที่เปิด `.venv` แล้ว:

```bash
python -c "from Rosmaster_Lib import Rosmaster; print('ROSMASTER LIB OK')"
```

ถ้าผ่าน ทำต่อได้

ถ้าไม่ผ่าน ให้ตรวจ Python ระบบ:

```bash
/usr/bin/python3 -c "import Rosmaster_Lib; print(Rosmaster_Lib.__file__)"
```

หาก Python ระบบพบ Library แต่ `.venv` ไม่พบ แปลว่าอาจมีปัญหาเรื่อง Python Path

กรณี Library เป็นไฟล์ Python ที่ติดตั้งไว้ในระบบ สามารถทดลองเพิ่มตำแหน่ง Library ใน Terminal ปัจจุบัน:

```bash
ROSDIR=$(/usr/bin/python3 -c 'import os, Rosmaster_Lib; print(os.path.dirname(Rosmaster_Lib.__file__))')
export PYTHONPATH="$ROSDIR:${PYTHONPATH:-}"
python -c "from Rosmaster_Lib import Rosmaster; print('ROSMASTER LIB OK')"
```

ถ้าผ่าน ต้องเก็บค่า `PYTHONPATH` ใน Terminal เดียวกันเมื่อทดสอบ Robot ต่อ หรือจัดการติดตั้ง Library ให้ถาวรใน Environment ที่ใช้งาน

ถ้า Python ระบบก็ไม่พบ Library ให้ค้นหาไฟล์เดิมของทีม:

```bash
find ~ -name 'Rosmaster_Lib.py' 2>/dev/null
```

ตรวจตำแหน่งไฟล์กับโปรแกรม `robot_teleop.py` เดิม และใช้ Library เวอร์ชันที่ตรงกับบอร์ดของทีม ไม่ดาวน์โหลด Library ชื่อคล้ายกันมาแทนโดยไม่ได้ตรวจ API

**จุดนี้ต้องผ่านก่อน STEP ที่สั่งมอเตอร์จริง**

---

# STEP 5 — ตรวจ YOLO V7.2 และกล้อง

## 5.1 ตรวจโมเดล

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
python -c "from ultralytics import YOLO; m=YOLO('models/best.pt'); print(m.names)"
```

ต้องเห็น:

```text
{0: 'green_dino'}
```

ทดสอบ Inference:

```bash
python -c "import numpy as np; from ultralytics import YOLO; m=YOLO('models/best.pt'); r=m.predict(np.zeros((480,640,3),dtype=np.uint8),imgsz=640,verbose=False); print('INFERENCE OK:',len(r))"
```

ต้องเห็น:

```text
INFERENCE OK: 1
```

## 5.2 ตรวจ Camera

ตรวจ Camera Device:

```bash
v4l2-ctl --list-devices
```

```bash
ls -l /dev/video*
```

ทดลอง Camera Index 0:

```bash
python -c "import cv2; c=cv2.VideoCapture(0); ok,f=c.read(); print('Opened:',c.isOpened(),'Frame:',ok,'Shape:',None if f is None else f.shape); c.release()"
```

ผลที่ต้องการ:

```text
Opened: True Frame: True
```

หากกล้องเป็น CSI หรือใช้งานด้วย Pipeline พิเศษ อาจต้องแก้ส่วน Camera Capture ให้ตรงกับอุปกรณ์จริง อย่าเปลี่ยน Camera Index โดยเดา

## 5.3 ทดสอบ YOLO แบบไม่ขยับมอเตอร์

ตรวจว่าไม่มีโปรแกรมอื่นใช้กล้องหรือ Port 8080:

```bash
sudo ss -ltnp | grep ':8080'
```

เปิด Dry Run:

```bash
python robot_teleop_yolo_pi_dryrun.py
```

เปิด Browser:

```text
http://ROBOT_IP:8080
```

ตรวจ:

- [ ] เห็นภาพจากกล้อง
- [ ] เห็น Bounding Box เมื่อยก Dino หน้ากล้อง
- [ ] Confidence แสดงค่า
- [ ] Dino อยู่ซ้าย แสดง TURN LEFT
- [ ] Dino อยู่ขวา แสดง TURN RIGHT
- [ ] Dino อยู่กลาง แสดง FORWARD ตามเงื่อนไขของ Simulator
- [ ] Dino หาย แสดง STOP
- [ ] ล้อจริงไม่ขยับ

**Dry Run ต้องไม่ทำให้ล้อจริงขยับ**

จบการทดสอบแล้วกด `Ctrl+C`

---

# STEP 6 — ระบุ Serial Port ของ T-MINI Plus

ตรวจ USB:

```bash
lsusb
```

```bash
ls -l /dev/serial/by-id/
```

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
```

ตรวจ Kernel Log:

```bash
sudo dmesg | tail -n 30
```

ต้องแยกให้ได้ว่า Port ไหนเป็น **T-MINI Plus** และ Port ไหนเป็น Motor Controller

ถ้าจำเป็น ให้ตรวจการเปลี่ยนแปลงของรายการอุปกรณ์ขณะถอดและเสียบ LiDAR ใหม่อย่างถูกวิธี

ตัวอย่าง Port:

```text
/dev/ttyUSB0
```

นี่เป็นเพียงตัวอย่าง ต้องใช้ Port ที่ตรวจพบจริง

ตรวจสิทธิ์:

```bash
groups
```

```bash
ls -l /dev/ttyUSB0
```

ถ้า Serial Device ใช้กลุ่ม `dialout` และผู้ใช้ยังไม่อยู่ในกลุ่มนี้:

```bash
sudo usermod -aG dialout "$(whoami)"
```

จากนั้น Logout/Login ใหม่หรือ Reboot เพื่อให้สิทธิ์มีผล

---

# STEP 7 — ทดสอบ T-MINI Plus โดยไม่เปิดมอเตอร์

เข้าโปรเจกต์:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
```

รันโดยแทน Port ให้ตรงกับอุปกรณ์จริง:

```bash
python robot_teleop_yolo_lidar.py --mode scan-only --port /dev/ttyUSB0 --front-angle 0
```

คำสั่งนี้ **เปิดเฉพาะ LiDAR ไม่เปิด Motor**

โปรแกรมจะรายงาน:

```text
[LiDAR] REASON | age: ... | points: ... | front: ... | left: ... | right: ...
```

ตรวจจำนวน Points และระยะที่อ่านได้จริง

ตัวอย่างสถานะ:

- `SCAN CLEAR` — พื้นที่ในส่วนที่ตรวจผ่านเกณฑ์
- `FRONT OBSTACLE` — พบวัตถุใกล้ด้านหน้า
- `LEFT OBSTACLE` — พบวัตถุใกล้ด้านซ้าย
- `RIGHT OBSTACLE` — พบวัตถุใกล้ด้านขวา
- `INSUFFICIENT ... DATA` — จุดวัดไม่เพียงพอ
- `STALE LIDAR DATA` — ข้อมูลสแกนเก่า
- `T-MINI Plus initialize failed` — เปิด LiDAR ไม่สำเร็จ

หากค่าเป็น `None` บางด้าน อาจเกิดจากโปรแกรมหยุดการตรวจที่ Sector ก่อนหน้าซึ่งไม่ผ่านเกณฑ์ ไม่ได้หมายความว่า LiDAR เสียเสมอไป

## ทดสอบสิ่งกีดขวาง

ใช้วัตถุที่ LiDAR ตรวจพบได้ เช่น แผ่นกระดาษแข็ง ตั้งให้ตัดผ่านระดับเลเซอร์

- [ ] วางวัตถุด้านหน้าแล้วค่าระยะเปลี่ยน
- [ ] วางวัตถุด้านซ้ายแล้วค่าระยะเปลี่ยน
- [ ] วางวัตถุด้านขวาแล้วค่าระยะเปลี่ยน
- [ ] วางวัตถุใกล้เกณฑ์หยุดแล้วระบบรายงาน OBSTACLE
- [ ] ข้อมูลขาดแล้วระบบไม่รายงานว่าพื้นที่ปลอดภัย

กด `Ctrl+C` เมื่อจบการทดสอบ

---

# STEP 8 — Calibrate ทิศ LiDAR ให้ตรงกับ Robot

**สำคัญมาก:** มุม 0° ของเซนเซอร์ไม่ได้รับประกันว่าจะตรงกับหน้าหุ่นยนต์

ให้ทดสอบโดยใช้ `scan-only` และวัตถุที่มองเห็นด้วย LiDAR ได้

1. เปิด `scan-only` ด้วยมุมเริ่มต้น 0°
2. วางวัตถุด้านหน้าของหุ่นยนต์
3. ตรวจว่าค่าระยะด้านหน้าเปลี่ยนถูกต้อง
4. ย้ายวัตถุไปด้านซ้ายและขวา
5. หากทิศไม่ตรง ให้ตรวจตำแหน่งติดตั้งและปรับ `--front-angle`
6. ทำซ้ำจน Front / Left / Right ตรงกับตำแหน่งจริง

ตัวอย่างเมื่อวัดแล้วว่าด้านหน้าอยู่ที่ 90°:

```bash
python robot_teleop_yolo_lidar.py --mode scan-only --port /dev/ttyUSB0 --front-angle 90
```

**อย่าใช้ 90° เพียงเพราะเห็นในตัวอย่าง ต้องยืนยันจากอุปกรณ์จริง**

บันทึกค่าที่ได้:

| รายการ | ค่าจริง |
|---|---|
| Serial Port | __________ |
| Front Angle | __________ |
| Front Distance | __________ |
| Left Distance | __________ |
| Right Distance | __________ |

หากการ Calibrate ยังไม่ผ่าน ห้ามเปิด AUTO

---

# STEP 9 — เตรียมให้ใช้ได้หลังสลับไป Robot Wi-Fi

เมื่อ Packages ถูกติดตั้งใน Raspberry Pi แล้ว สามารถใช้งานต่อบนเครื่องเดิมได้แม้ไม่มีอินเทอร์เน็ต ไม่จำเป็นต้องดาวน์โหลดใหม่ทุกครั้งที่เปลี่ยน Wi-Fi

แต่เพื่อสำรองสำหรับติดตั้งซ้ำ แนะนำให้ทำขณะยังออนไลน์:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
mkdir -p offline/wheels
```

บันทึก Packages:

```bash
python -m pip freeze > offline/requirements-pi-full.txt
```

สร้าง Wheel ของ YDLidar SDK:

```bash
python -m pip wheel ~/YDLidar-SDK --no-deps -w offline/wheels
```

บันทึก Lock File สำหรับ Packages อื่นโดยแยก YDLidar ที่ติดตั้งจาก Source:

```bash
python -m pip freeze | grep -vi '^ydlidar' > offline/requirements-pi.lock.txt
```

ทดลองดาวน์โหลด Wheels:

```bash
python -m pip download --only-binary=:all: -d offline/wheels -r offline/requirements-pi.lock.txt
```

ถ้าดาวน์โหลดไม่ครบ ชุด Offline ยังไม่พร้อมสำหรับการติดตั้งใหม่ทั้งหมด ต้องตรวจ Package ที่ขาดก่อน

ตรวจว่ามีไฟล์:

```bash
ls -lh offline/wheels
```

บันทึก SDK Version:

```bash
cd ~/YDLidar-SDK
git rev-parse HEAD
```

หมายเหตุ: Wheels ไม่รวม System Libraries ทุกตัว และ `Rosmaster_Lib` อาจเป็นไฟล์ของหุ่นยนต์ที่ไม่ได้ติดตั้งผ่าน pip ต้องเก็บสำรองแยกด้วยหากต้องการกู้ระบบจากศูนย์

หลังตรวจ Packages และ Code ครบแล้ว จึงสลับเครือข่ายไป Robot Wi-Fi

ตรวจ IP ใหม่:

```bash
hostname -I
```

หาก SSH หลุดหลังสลับเครือข่าย ให้เชื่อมใหม่ด้วย IP ปัจจุบัน

---

# STEP 10 — ทดลอง MANUAL กับ Robot จริงแบบยกล้อ

**ห้ามวางล้อสัมผัสพื้นในขั้นนี้**

ต้องผ่าน:

- YOLO Environment
- Camera
- `Rosmaster_Lib`
- มีวิธีหยุดมอเตอร์จริงทันที
- ไม่มีโปรแกรมเดิมใช้ Port 8080 หรือควบคุมมอเตอร์พร้อมกัน

ยกล้อทั้งหมดพ้นพื้นด้วยฐานรองที่มั่นคง และมีคนพร้อมตัดกำลังมอเตอร์

เปิด:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
```

หาก Motor Library ต้องใช้ `PYTHONPATH` ให้ตั้งค่าตาม STEP 4 ใน Terminal นี้ก่อน

จากนั้นรัน:

```bash
python robot_teleop_yolo_lidar.py --mode manual-wheels-up --confirm-wheels-up
```

เปิดเว็บ:

```text
http://ROBOT_IP:8080
```

ทดสอบตามลำดับ:

1. เปิดโปรแกรมแล้วล้อต้องไม่หมุน
2. กด `MANUAL`
3. กด `W` สั้น ๆ แล้วปล่อย — ตรวจทิศทางเดินหน้า
4. กด `A` สั้น ๆ แล้วปล่อย — ตรวจทิศทางเลี้ยวซ้าย
5. กด `D` สั้น ๆ แล้วปล่อย — ตรวจทิศทางเลี้ยวขวา
6. ปล่อยปุ่มทั้งหมด — ตรวจว่าหยุด
7. กด `SPACE` หรือ `STOP` — ตรวจว่าหยุด
8. ทดสอบขาดการเชื่อมต่อหน้าเว็บ — ตรวจว่าหยุด
9. ทดลองวิธีหยุดมอเตอร์ฉุกเฉินที่ไม่พึ่งหน้าเว็บ

**ขั้นนี้ไม่ใช้ LiDAR ควบคุมมอเตอร์ และ AUTO ถูกปิดไว้** จึงห้ามทดสอบโดยวางหุ่นยนต์บนพื้น

หากทิศทางผิดหรือไม่หยุด ให้หยุดทดสอบทันทีและแก้ระบบควบคุมก่อน

---

# STEP 11 — ทดลอง AUTO FOLLOW + LiDAR แบบยกล้อ

เมื่อผ่าน STEP 7–10 แล้ว สามารถทดลองให้ YOLO สั่งมอเตอร์ผ่านระบบตรวจ LiDAR โดยยังยกล้อพ้นพื้น

ใช้ Port และ Front Angle ที่ Calibrate แล้วเท่านั้น

ตัวอย่างคำสั่ง:

```bash
python robot_teleop_yolo_lidar.py --mode auto-supervised --port /dev/ttyUSB0 --front-angle 0 --confirm-orientation --confirm-supervised
```

**เปลี่ยน `--port` และ `--front-angle` ให้ตรงกับค่าที่ตรวจจริง**

เปิดหน้าเว็บ:

```text
http://ROBOT_IP:8080
```

ตรวจสถานะโดยตรงได้ที่:

```text
http://ROBOT_IP:8080/status
```

ในหน้าเว็บต้องเห็น YOLO Bounding Box และสถานะ LiDAR

## 11.1 ทดสอบการติดตาม Dino

เมื่อไม่มีสิ่งกีดขวางที่ LiDAR ตรวจพบ:

- [ ] กด AUTO FOLLOW แล้วโปรแกรมรับคำสั่ง
- [ ] Dino อยู่ซ้าย → ระบบขอให้เลี้ยวซ้าย
- [ ] Dino อยู่ขวา → ระบบขอให้เลี้ยวขวา
- [ ] Dino อยู่กลาง → ระบบขอให้เดินหน้า
- [ ] Confidence ต่ำกว่าเกณฑ์ → ไม่สั่งเคลื่อนที่
- [ ] Dino หาย → สั่งหยุด
- [ ] กด STOP → สั่งหยุด

ขณะทดสอบให้ตรวจทั้งข้อความบนเว็บและทิศทางหมุนของล้อจริง

## 11.2 ทดสอบ LiDAR Blocking

ยังคงยกล้อพ้นพื้น

- [ ] มีสิ่งกีดขวางด้านหน้า → ล้อต้องหยุด
- [ ] มีสิ่งกีดขวางด้านซ้าย → ล้อต้องหยุด
- [ ] มีสิ่งกีดขวางด้านขวา → ล้อต้องหยุด
- [ ] LiDAR ไม่พร้อม → ล้อต้องหยุด
- [ ] ข้อมูล LiDAR หมดอายุ → ล้อต้องหยุด
- [ ] กล้องไม่สามารถอ่านภาพ → AUTO ต้องหยุด
- [ ] Web Heartbeat หาย → ล้อต้องหยุด
- [ ] เมื่อกด STOP แล้ว ต้องไม่กลับมาเคลื่อนที่เองจนกว่าจะเปลี่ยนโหมดโดยตั้งใจ

ถ้าข้อใดไม่ผ่าน **ห้ามทดสอบ AUTO บนพื้น**

คำว่า `SCAN CLEAR` ในซอฟต์แวร์หมายถึงข้อมูลผ่านเกณฑ์ของโค้ด ไม่ได้หมายความว่าสภาพแวดล้อมปลอดภัยทุกทิศทางหรือทุกระดับความสูง

---

# STEP 12 — ก่อนทดลอง Robot เดินตาม Dino บนพื้น

ขั้นนี้ต้องผ่านการตรวจเพิ่มเติมก่อน ไม่ใช่แค่เห็น YOLO และ LiDAR ทำงาน

## 12.1 สิ่งที่ต้องยืนยัน

- [ ] มอเตอร์หมุนถูกทิศทาง
- [ ] ระบบหยุดได้ด้วยวิธีที่ไม่พึ่ง Python หรือหน้าเว็บ
- [ ] ตรวจการหยุดเมื่อโปรแกรมควบคุมหรือการสื่อสารล้มเหลวแล้ว
- [ ] LiDAR ตรวจสิ่งกีดขวางที่ระดับเลเซอร์ได้จริง
- [ ] ตรวจว่าวัตถุด้านหลังและข้างตัวหุ่นยนต์ไม่ถูกชนขณะหมุน
- [ ] ไม่มีบันได ขอบตก หรือพื้นที่เสี่ยง
- [ ] ระยะหยุดตั้งจากผลการทดลองเบรกจริง
- [ ] มีวิธีป้องกันการชน Dino ที่อยู่ต่ำกว่าระนาบ LiDAR
- [ ] YOLO ไม่จับวัตถุสีเขียวอื่นผิดเป็น Dino
- [ ] มีคนอยู่ใกล้หุ่นยนต์พร้อมหยุดได้ทันที

**ข้อจำกัดสำคัญ:** T-MINI Plus เป็น 2D LiDAR จึงอาจไม่เห็นตุ๊กตา Dino หากตุ๊กตาเตี้ยกว่าระดับสแกน และไม่ใช่เซนเซอร์ป้องกันการตกจากขอบหรือบันได

ค่า Bounding Box Area ของ YOLO ไม่ใช่ระยะจริง จึงไม่ควรใช้เป็นเงื่อนไขหยุดก่อนชนเพียงอย่างเดียว

## 12.2 การทดลองบนพื้นเมื่อผ่านเงื่อนไขทั้งหมด

ทดลองเฉพาะในพื้นที่ควบคุม ไม่มีกระจก/ขอบตก/ผู้คนหรือสัตว์ในเส้นทาง และใช้ความเร็วต่ำ พร้อมผู้ดูแลที่สามารถหยุดระบบได้ทันที

ทดสอบตามลำดับ:

1. เปิดโปรแกรมในโหมด STOPPED
2. ตรวจว่าหุ่นยนต์อยู่นิ่ง
3. ตรวจว่า YOLO มองเห็น Dino
4. ตรวจว่าระบบอ่าน LiDAR ได้และทิศทางถูกต้อง
5. เปิด AUTO FOLLOW ในการทดลองที่ควบคุมความเสี่ยงได้
6. ขยับ Dino ช้า ๆ ไปซ้ายและขวา
7. ตรวจว่าหุ่นยนต์ปรับทิศทางถูกต้อง
8. ตรวจการเดินหน้าเฉพาะเส้นทางที่ยืนยันว่าปลอดภัย
9. ตรวจการหยุดเมื่อเป้าหมายหายหรือถึงระยะหยุดที่ทดสอบแล้ว
10. กด STOP และจบการทดลอง

หากมีพฤติกรรมผิดปกติ ให้ตัดกำลังมอเตอร์ด้วยวิธีที่เตรียมไว้และหยุดการทดลอง ไม่แก้ด้วยการลด Safety Threshold โดยเดา

**หาก STEP 12.1 ยังไม่ผ่าน ให้จบการทดลองที่ STEP 11 แทน**

---

# STEP 13 — ทดสอบเสียงแมวและ Buzzer

ในหน้าเว็บของ Robot Program:

- `M` — Meow
- `6–0` — Meow Variants
- `1–5` — Buzzer Patterns
- `SPACE` — STOP
- `W/A/S/D` — MANUAL Drive เฉพาะโหมดที่อนุญาต
- Arrow Keys — Camera Servo (ปัจจุบันถูกปิดใน Real Robot Controller)

ตรวจระบบเสียง Raspberry Pi:

```bash
command -v aplay
command -v mpg123
aplay -l
```

กด Meow แล้วตรวจว่าเสียงออกจากลำโพงจริง

หากเสียงไม่ออกให้ตรวจ `AUDIO_DEV` ใน `robot_teleop_yolo_robot.py` และอุปกรณ์เสียงที่ Pi ใช้อยู่

ทดสอบว่าเสียงไม่ทำให้ Motor Control ค้าง และ STOP ยังใช้งานได้

---

# Troubleshooting

| ปัญหา | จุดที่ควรตรวจ |
|---|---|
| `No module named ultralytics` | Activate `.venv` และตรวจ `pip list` |
| `No module named ydlidar` | ตรวจ STEP 3 และ Python Environment |
| `No module named Rosmaster_Lib` | ตรวจ STEP 4 และ Python Path ของ Library เดิม |
| `No matching distribution found for torch` | ตรวจ Python Version และ Architecture |
| `Permission denied` ของ LiDAR | Serial Port, `groups`, สิทธิ์ `dialout` |
| `T-MINI Plus initialize failed` | Port, USB, SDK Settings, Power |
| `INSUFFICIENT FRONT DATA` | มุม LiDAR, สิ่งที่บังเซนเซอร์, ความครอบคลุมการสแกน |
| `STALE LIDAR DATA` | SDK, USB, CPU Load, อัตรารับข้อมูล |
| `Cannot open camera 0` | Camera Device, Camera Index, โปรแกรมที่ใช้กล้องอยู่ |
| `Address already in use` | มีโปรแกรมอื่นใช้ Port 8080 |
| `AUTO BLOCKED` | ตรวจ `lidar_ready`, Confidence, Mode และสถานะ Safety |
| Dino ไม่ถูกตรวจจับ | ตรวจโมเดล, กล้อง, มุมกล้อง, ความสว่าง, Confidence |
| Robot ไม่หยุดหรือเคลื่อนที่ผิดปกติ | ตัดกำลังมอเตอร์ทันที และหยุดทดสอบ |

คำสั่งตรวจ Port 8080:

```bash
sudo ss -ltnp | grep ':8080'
```

คำสั่งตรวจ IP:

```bash
hostname -I
```

ไม่รันโปรแกรมเดิมของทีม, Dry Run และโปรแกรม AUTO พร้อมกัน หากใช้กล้องหรือพอร์ตเดียวกัน

---

# Final Checklist — สิ่งที่ต้องส่งกลับให้ทีม

- [ ] ติดตั้ง Packages สำเร็จ
- [ ] YOLO โหลดโมเดล V7.2 ได้
- [ ] กล้องเปิดได้และตรวจ Dino ได้
- [ ] YDLidar SDK Import ได้
- [ ] T-MINI Plus อ่านข้อมูลระยะได้
- [ ] Calibrate Front Angle แล้ว
- [ ] Rosmaster Library Import ได้
- [ ] MANUAL Test แบบยกล้อผ่าน
- [ ] AUTO Test แบบยกล้อผ่าน
- [ ] Obstacle Blocking ผ่าน
- [ ] Target Lost STOP ผ่าน
- [ ] Web Disconnect STOP ผ่าน
- [ ] LiDAR Data Lost STOP ผ่าน
- [ ] Meow / Buzzer ผ่าน
- [ ] ตรวจระบบหยุดฉุกเฉินแล้ว
- [ ] ตรวจความเสี่ยงจากสิ่งกีดขวางที่ LiDAR มองไม่เห็นแล้ว
- [ ] ทดลองบนพื้นเฉพาะเมื่อผ่านเงื่อนไขความปลอดภัยทั้งหมด

ส่งข้อมูลกลับทีม:

1. Raspberry Pi OS / Python Version / Architecture
2. LiDAR Port และ Front Angle ที่ยืนยันแล้ว
3. ภาพ Terminal ตอน `scan-only`
4. ภาพ YOLO Bounding Box บนหน้าเว็บ
5. ผลการทดสอบ MANUAL และ AUTO แบบยกล้อ
6. วิดีโอแสดงว่าระบบหยุดเมื่อ Dino หายหรือมีสิ่งกีดขวาง
7. Error Log หากมี
8. วิดีโอ Final Demo เมื่อผ่านการทดลองบนพื้นแล้ว

---

# Technical Information

| Component | Implementation |
|---|---|
| Robot | ROSMASTER M1 |
| Object Detection | YOLO11n V7.2 |
| Model Class | `green_dino` |
| Model Weights | `models/best.pt` |
| Camera | OpenCV |
| LiDAR | YDLIDAR T-MINI Plus |
| LiDAR Driver | Official YDLidar-SDK |
| Motor Backend | `Rosmaster_Lib` |
| Interface | Python HTTP Server, Port 8080 |
| Docker | Not required |
| ROS2 | Optional, not required for this deployment |

## Important Files

| File | Purpose |
|---|---|
| `robot_teleop_yolo_pi_dryrun.py` | Camera + YOLO test, no real movement |
| `robot_teleop_yolo_robot.py` | Robot controller and web interface |
| `robot_teleop_yolo_lidar.py` | Main entry point for LiDAR integration |
| `tmini_plus_lidar.py` | T-MINI Plus reader and obstacle checks |
| `tests/test_tmini_plus_lidar.py` | Simulated LiDAR logic tests |
| `models/best.pt` | YOLO V7.2 weights |
| `requirements.txt` | Main Python dependencies |

## Official References

- [YDLidar SDK](https://github.com/YDLIDAR/YDLidar-SDK)
- [Official T-MINI Plus Python Example](https://github.com/YDLIDAR/YDLidar-SDK/blob/master/python/examples/tminiplus_test.py)
- [Yahboom T-MINI Plus Resources](https://github.com/YahboomTechnology/T-MINI-PLUS-Lidar)

**Hardware testing is required before claiming physical AUTO FOLLOW is complete.** Use only a trusted local network for the current web interface because it does not have authentication.