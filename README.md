# CatRobot YOLO V7.2 — ROSMASTER M1 + T-MINI Plus LiDAR

## Complete Raspberry Pi Setup & Robot Testing Guide

**อ่านและทำตามไฟล์นี้ไฟล์เดียว ตั้งแต่เริ่มติดตั้งจนถึงทดสอบหุ่นยนต์**

โปรเจกต์ Interactive Cat Robot ใช้ YOLO11n V7.2 ตรวจจับตุ๊กตา Green Dino และใช้ YDLIDAR T-MINI Plus ตรวจสิ่งกีดขวางก่อนอนุญาตให้ ROSMASTER M1 เคลื่อนที่

ไม่ใช้ Docker และไม่จำเป็นต้องติดตั้ง ROS2 เพิ่ม ห้ามเขียนทับ `robot_teleop.py` ต้นฉบับของทีม

**IMPORTANT:** โค้ดยังไม่ได้ผ่านการทดสอบกับหุ่นยนต์จริงทั้งหมด ห้ามทดลอง AUTO FOLLOW บนพื้นจนกว่าจะผ่านการทดสอบมอเตอร์ LiDAR ระบบหยุด และข้อจำกัดของเซนเซอร์ครบถ้วน

---

# PHASE A — ONLINE SETUP

**ต้องทำ STEP 1–8 ให้เสร็จขณะ Raspberry Pi ยังมีอินเทอร์เน็ต**

ใน PHASE นี้ เราจะดาวน์โหลด ติดตั้ง และตรวจทุกอย่างให้พร้อมก่อนเปลี่ยนไป Robot Wi-Fi ที่ไม่มีอินเทอร์เน็ต

อย่าเปลี่ยน Wi-Fi ระหว่าง STEP 1–8

## STEP 1 — ตรวจ Raspberry Pi

เปิด Terminal บน Raspberry Pi หรือ SSH จากคอมพิวเตอร์:

```bash
ssh USERNAME@ROBOT_IP
```

ตรวจระบบ:

```bash
uname -m
python3 --version
cat /etc/os-release
df -h /
```

บันทึก OS, Python Version, CPU Architecture และพื้นที่ว่าง

- [ ] Raspberry Pi ทำงานได้
- [ ] มีอินเทอร์เน็ต
- [ ] รู้ OS และ Python Version
- [ ] มีพื้นที่เพียงพอต่อการติดตั้ง

หาก PyTorch ไม่รองรับ Python/OS/Architecture ที่ใช้อยู่ ให้แก้ปัญหานี้ก่อน

## STEP 2 — ดาวน์โหลด GitHub และติดตั้ง YOLO

### 2.1 ติดตั้งเครื่องมือระบบ

```bash
sudo apt update
sudo apt install -y git python3-pip python3-venv cmake build-essential pkg-config swig python3-dev libusb-1.0-0-dev v4l-utils libgl1 alsa-utils mpg123
```

ถ้ามี Package ติดตั้งไม่ผ่าน ให้เก็บ Error และแก้ก่อน

### 2.2 Clone Repository

หากยังไม่เคย Clone:

```bash
cd ~
git clone https://github.com/Gamaneeya/CatRobot-YOLO-Detector.git
cd CatRobot-YOLO-Detector
```

หากมี Repository อยู่แล้ว:

```bash
cd ~/CatRobot-YOLO-Detector
git status
git pull --ff-only origin main
```

หากมี Local Changes ให้สำรองก่อน Pull ห้ามใช้ `git reset --hard` โดยไม่ตรวจงานที่มีอยู่

### 2.3 ตรวจไฟล์

```bash
ls -lh models/best.pt
ls -l robot_teleop_yolo_pi_dryrun.py
ls -l robot_teleop_yolo_robot.py
ls -l robot_teleop_yolo_lidar.py
ls -l tmini_plus_lidar.py
ls -l requirements.txt
```

ทุกไฟล์ต้องอยู่ครบ

### 2.4 สร้าง Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
which python
```

`which python` ต้องชี้ไปยัง `.venv/bin/python` ของโปรเจกต์

### 2.5 ติดตั้ง Python Dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyserial
python -m pip check
```

ตรวจ:

```bash
python -c "import torch, cv2, numpy, ultralytics, serial; print('YOLO DEPENDENCIES OK')"
```

- [ ] Ultralytics พร้อม
- [ ] PyTorch พร้อม
- [ ] OpenCV พร้อม
- [ ] NumPy พร้อม
- [ ] PySerial พร้อม
- [ ] `pip check` ผ่าน

## STEP 3 — ติดตั้ง T-MINI Plus LiDAR SDK

ใช้ Official YDLidar-SDK ตามตัวอย่างสำหรับ T-MINI Plus ของผู้ผลิต

### 3.1 ดาวน์โหลด SDK

```bash
cd ~
git clone https://github.com/YDLIDAR/YDLidar-SDK.git
```

### 3.2 Build SDK

```bash
cd ~/YDLidar-SDK
mkdir -p build
cd build
cmake ..
make -j2
sudo make install
sudo ldconfig
```

### 3.3 ติดตั้ง Python SDK ใน Environment เดียวกับ YOLO

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

กลับไปยังโปรเจกต์และตรวจรวม:

```bash
cd ~/CatRobot-YOLO-Detector
python -c "import torch, cv2, ultralytics, ydlidar; print('VISION + LIDAR READY')"
```

- [ ] Build SDK ผ่าน
- [ ] Python SDK ติดตั้งผ่าน
- [ ] `import ydlidar` ผ่าน
- [ ] YOLO และ LiDAR อยู่ใน Python Environment เดียวกัน

## STEP 4 — ตรวจ Rosmaster Motor Library

ใน Environment ของโปรเจกต์:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
python -c "from Rosmaster_Lib import Rosmaster; print('ROSMASTER LIB OK')"
```

ถ้าผ่าน ถือว่า Python พบ Library แล้ว แต่ยังไม่ใช่การยืนยันว่ามอเตอร์ทำงานถูกต้อง

หากไม่พบ ให้ตรวจ Python ระบบ:

```bash
/usr/bin/python3 -c "import Rosmaster_Lib; print(Rosmaster_Lib.__file__)"
```

หาตำแหน่ง Library ของเพื่อน:

```bash
find ~ -name 'Rosmaster_Lib.py' 2>/dev/null
```

ต้องใช้ Library ของ ROSMASTER M1 ที่ตรงกับบอร์ดจริง และทำให้ Import จาก `.venv` ได้

หากจำเป็นต้องใช้ `PYTHONPATH` ให้ตั้งค่าตำแหน่ง Library ที่ตรวจพบ และจัดให้มีผลถาวรหรือผ่านสคริปต์เริ่มโปรแกรมด้วย เพราะ `export` ใน Terminal เดียวจะไม่คงอยู่หลังเปิด Terminal ใหม่

**ห้ามเปลี่ยน Wi-Fi จนกว่าจะเปิด Terminal ใหม่แล้ว Import `Rosmaster_Lib` ผ่านได้อีกครั้ง**

## STEP 5 — ตรวจ YOLO และกล้อง

### 5.1 ตรวจโมเดล

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
python -c "from ultralytics import YOLO; m=YOLO('models/best.pt'); print(m.names)"
```

ต้องเห็น:

```text
{0: 'green_dino'}
```

ทดลอง Inference:

```bash
python -c "import numpy as np; from ultralytics import YOLO; m=YOLO('models/best.pt'); r=m.predict(np.zeros((480,640,3),dtype=np.uint8),imgsz=640,verbose=False); print('INFERENCE OK:',len(r))"
```

ต้องเห็น `INFERENCE OK: 1`

### 5.2 ตรวจกล้อง

```bash
v4l2-ctl --list-devices
ls -l /dev/video*
```

```bash
python -c "import cv2; c=cv2.VideoCapture(0); ok,f=c.read(); print('Opened:',c.isOpened(),'Frame:',ok,'Shape:',None if f is None else f.shape); c.release()"
```

ต้องได้ `Opened: True` และ `Frame: True`

หากเป็นกล้อง CSI ที่ OpenCV เปิดด้วย Index ไม่ได้ อาจต้องปรับ Camera Pipeline ให้ตรงกับกล้องจริงก่อน

### 5.3 ทดสอบ Dry Run ขณะยังออนไลน์

ตรวจว่าโปรแกรมเดิมไม่ได้ใช้กล้องหรือ Port 8080 อยู่:

```bash
sudo ss -ltnp | grep ':8080'
```

เปิดโปรแกรม:

```bash
python robot_teleop_yolo_pi_dryrun.py
```

เปิด Browser ผ่าน IP ของ Pi ในเครือข่ายปัจจุบัน:

```text
http://PI_IP:8080
```

หากใช้หน้าจอบน Pi เอง สามารถเปิด `http://localhost:8080` ได้

ตรวจ:

- [ ] หน้าเว็บเปิดได้
- [ ] ภาพกล้องแสดง
- [ ] เห็น Bounding Box รอบ Green Dino
- [ ] Confidence แสดงผล
- [ ] ขยับ Dino แล้วทิศ LEFT / RIGHT เปลี่ยน
- [ ] Dino หายแล้วแสดง STOP
- [ ] ล้อจริงไม่เคลื่อนที่

Dry Run เป็นการจำลองคำสั่งมอเตอร์เท่านั้น

กด `Ctrl+C` เพื่อปิดโปรแกรมก่อนทำขั้นต่อไป

## STEP 6 — ตรวจ T-MINI Plus และ Serial Port

ตรวจ USB:

```bash
lsusb
ls -l /dev/serial/by-id/
ls -l /dev/ttyUSB* /dev/ttyACM*
sudo dmesg | tail -n 30
```

ระบุให้ได้ว่า Port ไหนเป็น LiDAR และ Port ไหนเป็น Motor Controller

ตัวอย่าง Port ของ LiDAR:

```text
/dev/ttyUSB0
```

**เป็นเพียงตัวอย่าง ต้องใช้ Port ที่ตรวจพบจริง**

ตรวจสิทธิ์ของ Port:

```bash
groups
ls -l /dev/ttyUSB0
```

หากอุปกรณ์ใช้กลุ่ม `dialout` และผู้ใช้ยังไม่มีสิทธิ์:

```bash
sudo usermod -aG dialout "$(whoami)"
```

Logout/Login หรือ Reboot แล้วตรวจสิทธิ์ใหม่

### 6.1 ทดลองอ่าน LiDAR อย่างเดียว

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
```

แทน `/dev/ttyUSB0` ด้วย Port จริง:

```bash
python robot_teleop_yolo_lidar.py --mode scan-only --port /dev/ttyUSB0 --front-angle 0
```

โหมดนี้ไม่เปิด Motor Controller

ตรวจค่าที่รายงาน:

```text
[LiDAR] REASON | age: ... | points: ... | front: ... | left: ... | right: ...
```

ทดลองนำวัตถุที่ LiDAR ตรวจพบได้ไปวางด้านหน้า ซ้าย และขวาที่ระดับเลเซอร์

- [ ] ได้รับ Scan จริง
- [ ] จำนวน Valid Points ไม่เป็นศูนย์ตลอดเวลา
- [ ] ระยะเปลี่ยนเมื่อย้ายวัตถุ
- [ ] วัตถุใกล้แล้วรายงาน OBSTACLE
- [ ] ข้อมูลไม่เพียงพอแล้วไม่รายงาน SCAN CLEAR
- [ ] ข้อมูลหมดอายุแล้วรายงาน STALE

กด `Ctrl+C` เพื่อหยุด

### 6.2 Calibrate ทิศหน้า

มุม `0°` ของ LiDAR อาจไม่ตรงกับด้านหน้าหุ่นยนต์

ให้ทดลองวางวัตถุด้านหน้าของหุ่นยนต์และดูว่าระยะใน Sector หน้าเปลี่ยนถูกต้องหรือไม่ จากนั้นตรวจซ้ายและขวาด้วย

หากไม่ตรง ให้แก้ `--front-angle` จากการทดลองจริง

ตัวอย่าง:

```bash
python robot_teleop_yolo_lidar.py --mode scan-only --port /dev/ttyUSB0 --front-angle 90
```

ใช้ 90° เฉพาะเมื่อสอบเทียบแล้วว่าถูกต้อง

บันทึก:

| Setting | Actual value |
|---|---|
| LiDAR Port | __________ |
| Front Angle | __________ |
| Front Scan | PASS / FAIL |
| Left Scan | PASS / FAIL |
| Right Scan | PASS / FAIL |

**หาก Calibrate ไม่ผ่าน ห้ามเริ่ม Auto Motor Test**

## STEP 7 — ติดตั้งและตรวจระบบเสียง

ทำให้เสร็จขณะยังออนไลน์:

```bash
command -v aplay
command -v mpg123
aplay -l
```

หากขาดโปรแกรมเสียง ให้ติดตั้งก่อนเปลี่ยน Wi-Fi:

```bash
sudo apt install -y alsa-utils mpg123
```

ถ้าเสียงต้องใช้อุปกรณ์ USB ให้ตรวจว่า Raspberry Pi มองเห็นอุปกรณ์นั้นแล้ว

ตรวจตำแหน่งลำโพงและการตั้งค่า Output Device ก่อนทดลองจริง

- [ ] `aplay` มีอยู่
- [ ] `mpg123` มีอยู่
- [ ] Pi พบอุปกรณ์เสียง
- [ ] เลือก Output Device ได้

การกด Meow และ Buzzer ผ่านหน้าเว็บจะทดสอบอีกครั้งใน PHASE B

## STEP 8 — Offline Backup + FINAL ONLINE CHECK

**นี่คือจุดสุดท้ายก่อนเปลี่ยนไป Robot Wi-Fi**

### 8.1 สำรอง Python Packages

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
mkdir -p offline/wheels
```

บันทึก Packages ทั้งหมด:

```bash
python -m pip freeze > offline/requirements-pi-full.txt
```

ทำ Lock File สำหรับ Dependencies ที่ติดตั้งผ่าน pip โดยแยก YDLidar ที่ติดตั้งจาก Source:

```bash
python -m pip freeze | grep -vi '^ydlidar' > offline/requirements-pi.lock.txt
```

ดาวน์โหลด Wheels:

```bash
python -m pip download --only-binary=:all: -d offline/wheels -r offline/requirements-pi.lock.txt
```

สร้าง Wheel ของ YDLidar SDK:

```bash
python -m pip wheel ~/YDLidar-SDK --no-deps -w offline/wheels
```

หากคำสั่งใดไม่ผ่าน ห้ามถือว่าชุด Offline Backup สมบูรณ์ ต้องตรวจ Package ที่ขาดก่อน

ตรวจไฟล์:

```bash
ls -lh offline/wheels
```

เก็บ Source ของ `~/YDLidar-SDK` และ Library ของ ROSMASTER ไว้ด้วย เพราะ Wheels ไม่ได้รวม System Libraries และไฟล์ของผู้ผลิตทุกตัว

### 8.2 ทดลอง Offline Installation

หากต้องการให้สามารถติดตั้ง Python Packages ใหม่โดยไม่ใช้อินเทอร์เน็ตได้ ให้ทดลองใน Environment แยก:

```bash
cd ~/CatRobot-YOLO-Detector
python3 -m venv .venv_offline_test
```

```bash
.venv_offline_test/bin/python -m pip install --no-index --find-links=offline/wheels -r offline/requirements-pi.lock.txt
```

```bash
.venv_offline_test/bin/python -m pip install --no-index --find-links=offline/wheels ydlidar
```

```bash
.venv_offline_test/bin/python -m pip check
```

```bash
.venv_offline_test/bin/python -c "import torch, cv2, ultralytics, ydlidar; print('OFFLINE PYTHON IMPORT OK')"
```

ถ้า Package ใดติดตั้งไม่ได้ ให้แก้ชุดสำรองขณะยังมีอินเทอร์เน็ต

**หมายเหตุ:** การทดลองนี้พิสูจน์เฉพาะ Python Packages บนเครื่องที่ใช้ทดสอบ ไม่ได้พิสูจน์ว่าการติดตั้ง System Packages หรือ ROSMASTER Library ใหม่จะทำได้โดยไม่มีอินเทอร์เน็ตด้วย ต้องสำรองและทดสอบส่วนเหล่านั้นแยกหากต้องการกู้ระบบทั้งหมด

### 8.3 FINAL ONLINE CHECK — ต้องผ่านก่อนเปลี่ยน Wi-Fi

เปิด Terminal ใหม่เพื่อทดสอบว่าระบบยังทำงานได้หลังเริ่ม Session ใหม่:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
```

ตรวจ Dependencies:

```bash
python -m pip check
```

```bash
python -c "import torch, cv2, numpy, ultralytics, serial, ydlidar; print('VISION + LIDAR IMPORT OK')"
```

ตรวจ Motor Library:

```bash
python -c "from Rosmaster_Lib import Rosmaster; print('ROSMASTER LIB OK')"
```

ตรวจโมเดล:

```bash
python -c "from ultralytics import YOLO; m=YOLO('models/best.pt'); print(m.names)"
```

ตรวจระบบเสียง:

```bash
command -v aplay
command -v mpg123
```

### FINAL CHECKLIST — ก่อนออกจากเครือข่ายที่มีอินเทอร์เน็ต

- [ ] GitHub Code ดาวน์โหลดครบ
- [ ] `models/best.pt` อยู่ในเครื่อง
- [ ] Python `.venv` ใช้ได้
- [ ] Ultralytics / Torch / OpenCV / NumPy / PySerial พร้อม
- [ ] YDLidar SDK ติดตั้งสำเร็จ
- [ ] T-MINI Plus อ่านข้อมูล Scan จริงได้
- [ ] LiDAR Port ถูกต้อง
- [ ] Front Angle Calibrate แล้ว
- [ ] `Rosmaster_Lib` Import ได้จาก Terminal ใหม่
- [ ] กล้องเปิดได้
- [ ] YOLO ตรวจ Dino ได้
- [ ] Dry Run ทำงานและไม่ขยับล้อจริง
- [ ] โปรแกรมเสียงติดตั้งครบ
- [ ] Source Code และ SDK เก็บในเครื่องแล้ว
- [ ] Offline Backup ผ่านตามระดับการกู้ระบบที่ต้องการ
- [ ] ไม่มี Error ค้างที่จำเป็นต้องใช้อินเทอร์เน็ตแก้

**ทุกข้อที่จำเป็นสำหรับการทดลองต้องผ่านก่อน จึงเปลี่ยน Wi-Fi**

---

# SWITCH NETWORK — เปลี่ยนไป Robot Wi-Fi ครั้งเดียว

หลัง PHASE A ผ่านแล้ว ให้เชื่อม Raspberry Pi และคอมพิวเตอร์ที่จะเปิด Web Control เข้ากับเครือข่ายภายในของหุ่นยนต์ตามการตั้งค่าของทีม

หากการเปลี่ยน Wi-Fi ทำให้ SSH หลุด ให้เชื่อมใหม่ด้วย IP ของ Pi บนเครือข่ายใหม่

ตรวจ IP:

```bash
hostname -I
```

บันทึก:

```text
ROBOT_IP = ___________________
```

จากนี้ใช้ Source Code และ Libraries ที่ติดตั้งอยู่ใน Raspberry Pi ได้โดยไม่ต้องมีอินเทอร์เน็ต

**PHASE B ไม่ต้องใช้ `apt install`, `pip install` หรือ `git clone` อีกแล้ว**

---

# PHASE B — ROBOT TEST (NO INTERNET REQUIRED)

ทำบน Robot Wi-Fi หลังผ่าน PHASE A

## STEP 9 — ยืนยันระบบหลังเปลี่ยนเครือข่าย

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
```

ตรวจ:

```bash
python -c "import torch, cv2, ultralytics, ydlidar; print('READY')"
```

```bash
python -c "from Rosmaster_Lib import Rosmaster; print('MOTOR LIB READY')"
```

```bash
hostname -I
```

ตรวจ Port 8080:

```bash
sudo ss -ltnp | grep ':8080'
```

หากมีโปรแกรมเดิมใช้งานอยู่ ให้ระบุโปรแกรมและหยุดอย่างถูกวิธีก่อนเปิดโปรแกรมใหม่

## STEP 10 — Dry Run บน Robot Wi-Fi

```bash
python robot_teleop_yolo_pi_dryrun.py
```

เปิด Browser จากคอมที่อยู่เครือข่ายเดียวกัน:

```text
http://ROBOT_IP:8080
```

ตรวจ:

- [ ] เปิดเว็บได้
- [ ] เห็นภาพกล้อง
- [ ] YOLO ตรวจ Green Dino ได้
- [ ] Bounding Box ตรงกับ Dino
- [ ] LEFT / RIGHT / FORWARD / STOP แสดงผล
- [ ] ล้อจริงไม่เคลื่อนที่

กด `Ctrl+C` เมื่อจบ

หาก Dry Run บน Robot Wi-Fi ไม่ผ่าน ให้แก้การเชื่อมต่อกล้องหรือเครือข่ายก่อน ไม่ข้ามไปทดลองมอเตอร์

## STEP 11 — MANUAL MOTOR TEST (WHEELS UP)

**ยกล้อหุ่นยนต์พ้นพื้นอย่างมั่นคง มีคนควบคุมอยู่กับหุ่นยนต์ และเตรียมวิธีตัดกำลังมอเตอร์ทันที**

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
```

```bash
python robot_teleop_yolo_lidar.py --mode manual-wheels-up --confirm-wheels-up
```

เปิดเว็บ:

```text
http://ROBOT_IP:8080
```

ทดสอบ:

1. เริ่มโปรแกรมแล้วล้อต้องหยุด
2. กด MANUAL
3. กด W สั้น ๆ → ตรวจทิศทางเดินหน้า
4. กด A สั้น ๆ → ตรวจทิศทางเลี้ยวซ้าย
5. กด D สั้น ๆ → ตรวจทิศทางเลี้ยวขวา
6. ปล่อยปุ่ม → ตรวจว่าหยุด
7. กด SPACE / STOP → ตรวจว่าหยุด
8. ทดสอบ Web Heartbeat ขาด → ตรวจว่าหยุด
9. ทดสอบวิธีหยุดฉุกเฉินที่ไม่พึ่งหน้าเว็บ

**โหมดนี้ไม่ได้ใช้ LiDAR เป็นตัวควบคุมความปลอดภัย และห้ามทดลองโดยวางล้อบนพื้น**

หากทิศผิดหรือไม่หยุด ให้หยุดทดลองและแก้ปัญหาก่อน

### STEP 11.1 — หลัง MANUAL Test ผ่านแล้ว ต้องทำอะไรต่อ?

เมื่อทดสอบมอเตอร์ใน STEP 11 ผ่านทั้งหมดแล้ว ให้เปลี่ยนจากโปรแกรมทดสอบมอเตอร์แยกไปเป็นโปรแกรมรวม YOLO + LiDAR + Motor

**ทำตามทีละข้อ**

1. กลับไปที่หน้าเว็บ `http://ROBOT_IP:8080`
2. กดปุ่ม **STOP**
3. ตรวจให้แน่ใจว่าล้อหยุดหมุนสนิท
4. กลับไปที่ Terminal ของ Raspberry Pi ที่กำลังรัน `manual-wheels-up`
5. กด `Ctrl+C` ใน Terminal เพื่อปิดโปรแกรมทดสอบ
6. ตรวจว่า Terminal กลับมารับคำสั่งได้ และโปรแกรมเดิมไม่ใช้ Port 8080 แล้ว
7. ทำ STEP 12 ต่อ

**ทำไมต้องปิดโปรแกรมนี้?**

เพราะ `manual-wheels-up` เป็นโปรแกรมทดสอบมอเตอร์แยกที่ยังไม่เปิด AUTO FOLLOW

เมื่อเปิดโปรแกรมรวมใน STEP 12 แล้ว จะสามารถกด MANUAL ↔ AUTO FOLLOW ↔ STOP บนหน้าเว็บได้โดยไม่ต้องปิด Python อีก

---

## STEP 12 — เปิดโปรแกรมรวม MANUAL + AUTO FOLLOW + LiDAR (WHEELS UP)

**ขั้นนี้ยังต้องยกล้อหุ่นยนต์พ้นพื้นอย่างมั่นคง และมีคนพร้อมตัดกำลังมอเตอร์ทันที**

ต้องผ่าน MANUAL Test, LiDAR Calibration และการทดสอบระบบหยุดเบื้องต้นก่อน

### STEP 12.1 — เปิดโปรแกรมรวมครั้งเดียว

ใน Terminal ของ Raspberry Pi พิมพ์:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
```

จากนั้นรัน:

```bash
python robot_teleop_yolo_lidar.py --mode auto-supervised --port /dev/ttyUSB0 --front-angle 0 --confirm-orientation --confirm-supervised
```

**สำคัญ:** เปลี่ยน `/dev/ttyUSB0` และ `--front-angle 0` เป็นค่าที่ตรวจสอบและ Calibrate ได้จริงใน PHASE A

โปรแกรมนี้จะเปิดระบบ YOLO, LiDAR, Motor และ Web Interface พร้อมกัน

ไม่ต้องแก้ `ENABLE_REAL_MOTOR` หรือ `ENABLE_AUTO_FOLLOW` ในไฟล์ Python ด้วยมือ

หากมี Error ให้แก้ก่อนทำขั้นตอนถัดไป

### STEP 12.2 — เปิดหน้าเว็บควบคุม

1. เชื่อมคอมพิวเตอร์กับ Robot Wi-Fi เดียวกับ Raspberry Pi
2. เปิด Chrome หรือ Browser
3. เข้า `http://ROBOT_IP:8080`
4. ตรวจว่าเห็นภาพกล้อง
5. ตรวจว่าเห็นปุ่ม MANUAL, AUTO FOLLOW และ STOP
6. ตรวจว่าตอนเริ่มแสดง `Mode: STOPPED`
7. ล้อหุ่นยนต์ต้องยังไม่หมุน

สามารถเปิด `http://ROBOT_IP:8080/status` เพื่อดูรายละเอียดสถานะระบบได้

### STEP 12.3 — ทดลองสลับ MANUAL / AUTO / STOP บนหน้าเว็บ

**ทดสอบ MANUAL**

1. กด **MANUAL**
2. กด W สั้น ๆ → ตรวจว่าล้อหมุนไปทิศเดินหน้า
3. กด A สั้น ๆ → ตรวจว่าล้อหมุนไปทิศเลี้ยวซ้าย
4. กด D สั้น ๆ → ตรวจว่าล้อหมุนไปทิศเลี้ยวขวา
5. ปล่อยปุ่มทั้งหมด → ล้อต้องหยุด

การสั่งล้อในโหมดนี้ยังต้องผ่าน LiDAR Safety Check

**ทดสอบ AUTO FOLLOW**

1. กด **AUTO FOLLOW** โดยไม่ต้องปิด Python
2. นำ Green Dino ไปไว้หน้ากล้อง
3. ตรวจว่า YOLO แสดง Bounding Box รอบ Dino
4. ขยับ Dino ไปด้านซ้าย → ตรวจคำสั่ง TURN LEFT
5. ขยับ Dino ไปด้านขวา → ตรวจคำสั่ง TURN RIGHT
6. วาง Dino ตรงกลาง → ตรวจคำสั่ง FORWARD เมื่อผ่านเงื่อนไข
7. นำ Dino ออกจากภาพ → ล้อต้องหยุด
8. กด STOP → ล้อต้องหยุดและเข้า STOPPED

**ทดลองกลับจาก AUTO เป็น MANUAL**

1. กด **MANUAL** อีกครั้งบนหน้าเว็บ
2. ตรวจว่า Mode เปลี่ยนเป็น MANUAL
3. ทดลอง WASD สั้น ๆ อีกครั้ง
4. กด STOP เพื่อจบการทดสอบ

**จำง่าย ๆ**

- MANUAL → AUTO FOLLOW: กดปุ่ม AUTO FOLLOW บนเว็บ
- AUTO FOLLOW → MANUAL: กดปุ่ม MANUAL บนเว็บ
- MANUAL / AUTO → STOP: กด STOP
- ไม่ต้อง Restart Python เพื่อสลับโหมด
- ไม่ต้องเปลี่ยน Wi-Fi
- ไม่ต้องแก้ตัวแปรในโค้ด

### STEP 12.4 — ทดสอบ LiDAR Safety

ในโหมดโปรแกรมรวม ทั้ง MANUAL และ AUTO ต้องหยุดการเคลื่อนที่หาก LiDAR ไม่ผ่านเงื่อนไข

ทดสอบโดยยังยกล้อพ้นพื้น:

- [ ] ไม่มีข้อมูล LiDAR → ล้อไม่หมุน
- [ ] ข้อมูล LiDAR เก่า → ล้อหยุด
- [ ] สิ่งกีดขวางด้านหน้า → ล้อหยุด
- [ ] สิ่งกีดขวางด้านซ้าย → ล้อหยุด
- [ ] สิ่งกีดขวางด้านขวา → ล้อหยุด
- [ ] Dino หายจากกล้องใน AUTO → ล้อหยุด
- [ ] ขาด Web Heartbeat → ล้อหยุด
- [ ] กด STOP → ล้อหยุด
- [ ] สลับ MANUAL ↔ AUTO ได้โดยไม่มีคำสั่งเก่าค้าง

### STEP 12.5 — หากกด AUTO แล้ว Robot ไม่ขยับ

เปิด:

`http://ROBOT_IP:8080/status`

ตรวจค่าต่อไปนี้:

| Status | สิ่งที่ต้องตรวจ |
|---|---|
| `mode` | เป็น AUTO หรือไม่ |
| `motor_enabled` | เป็น true หรือไม่ |
| `auto_enabled` | เป็น true หรือไม่ |
| `lidar_ready` | เป็น true หรือไม่ |
| `detection` | YOLO พบ Dino หรือไม่ |
| `motor_action` | โปรแกรมสั่งอะไร หรือหยุดเพราะอะไร |

หากแสดง `AUTO BLOCKED`, `LIDAR NOT READY` หรือไม่พบ Dino ต้องแก้สาเหตุให้ถูกต้องก่อน ไม่ปิด Safety Check เพื่อบังคับให้ล้อหมุน

**หากข้อใดใน STEP 12 ไม่ผ่าน ห้ามทดลอง AUTO บนพื้นจริง**

การทดลองบนพื้นต้องผ่านเงื่อนไขใน STEP 14 ก่อน โดยเฉพาะระบบหยุดฉุกเฉินที่ไม่พึ่งซอฟต์แวร์ ระยะเบรกจริง และสิ่งกีดขวางที่ LiDAR 2D อาจตรวจไม่พบ

## STEP 13 — ทดสอบ Meow และ Buzzer

ใช้หน้าเว็บของ Robot Program

Controls:

| Control | Function |
|---|---|
| MANUAL | Manual Drive Mode |
| AUTO FOLLOW | YOLO + LiDAR Follow Test |
| STOP / SPACE | Software Stop |
| W / A / S / D | Manual movement |
| M | Meow |
| 6–0 | Other Meow Variants |
| 1–5 | Buzzer Patterns |

Camera Servo ยังถูกปิดไว้ใน Real Robot Controller เวอร์ชันนี้

ตรวจ:

- [ ] Meow ออกลำโพง
- [ ] Buzzer ทำงาน
- [ ] เสียงไม่ทำให้ Loop ควบคุมมอเตอร์ค้าง
- [ ] STOP ยังทำงานขณะเล่นเสียง

หน้าเว็บไม่มีระบบ Login จึงใช้เฉพาะเครือข่ายภายในที่เชื่อถือได้ ไม่เปิด Port 8080 สู่ Internet

## STEP 14 — ก่อนทดลองเดินตาม Dino บนพื้นจริง

**ยังไม่ให้ทำขั้นนี้เพียงเพราะ STEP 12 ผ่าน**

ต้องยืนยันเพิ่มเติม:

- [ ] มีระบบหยุดหรือตัดกำลังมอเตอร์ที่ไม่พึ่ง Python/Web UI
- [ ] ทดสอบกรณีโปรแกรมหรือการสื่อสารมอเตอร์ค้างแล้ว
- [ ] ตรวจระยะเบรกจริงของหุ่นยนต์แล้ว
- [ ] ตั้งระยะหยุดจากผลทดสอบ ไม่ใช่เดาตัวเลข
- [ ] ตรวจทิศ LiDAR และจุดบอดของหุ่นยนต์แล้ว
- [ ] ตรวจการชนขณะหมุนแล้ว
- [ ] มีวิธีจัดการวัตถุที่ต่ำกว่าระนาบเลเซอร์
- [ ] ไม่มีบันได ขอบตก หรือสิ่งกีดขวางอันตราย
- [ ] มีคนพร้อมหยุดหุ่นยนต์ทุกช่วงเวลา

**T-MINI Plus เป็น 2D LiDAR** ซึ่งอาจไม่เห็น Green Dino ถ้าตุ๊กตาเตี้ยกว่าระนาบเลเซอร์ และไม่สามารถใช้ป้องกันการตกจากขอบพื้นได้

**ขนาด Bounding Box ของ YOLO ไม่ใช่ระยะทางจริง** จึงไม่เพียงพอสำหรับรับประกันว่าหุ่นยนต์จะหยุดก่อนชน Dino

เมื่อแก้ความเสี่ยงเหล่านี้และผ่านการทดสอบระบบหยุดครบแล้ว จึงพิจารณาทดลองบนพื้นในพื้นที่ควบคุมด้วยความเร็วต่ำและมีผู้ดูแล

หากยังไม่ผ่าน ให้ใช้ผลทดสอบแบบยกล้อเป็น Demo ชั่วคราวแทน

---

# Troubleshooting

| Problem | Check |
|---|---|
| `No module named ultralytics` | `.venv` และ Python Dependencies |
| `No module named ydlidar` | SDK Installation ใน STEP 3 |
| `No module named Rosmaster_Lib` | Motor Library และ Python Path |
| PyTorch Install Failed | OS / Python Version / Architecture |
| LiDAR Permission Denied | Serial Port / dialout Group |
| LiDAR Initialize Failed | USB / Port / SDK / Power |
| `INSUFFICIENT ... DATA` | Sensor Orientation และ Scan Coverage |
| `STALE LIDAR DATA` | USB / SDK / CPU Load |
| `Cannot open camera 0` | Camera Device / Video Pipeline |
| Port 8080 In Use | โปรแกรมอื่นกำลังทำงาน |
| YOLO ไม่จับ Dino | Model / Camera / Lighting / Confidence |
| AUTO ถูก Block | Detection / LiDAR Readiness / Mode |
| Robot เคลื่อนที่ผิดปกติ | ตัดกำลังมอเตอร์และหยุดการทดสอบ |

---

# Final Report to Team

ส่งข้อมูลกลับทีม:

1. Raspberry Pi OS / Python Version / Architecture
2. ผลการติดตั้ง YOLO และ YDLidar SDK
3. ผล `Rosmaster_Lib` Import
4. Serial Port และ Front Angle ของ T-MINI Plus
5. ภาพกล้องที่มี YOLO Bounding Box
6. ผล LiDAR Scan ด้านหน้า/ซ้าย/ขวา
7. ผล Manual Test แบบยกล้อ
8. ผล Auto + LiDAR Test แบบยกล้อ
9. วิดีโอ STOP เมื่อ Dino หายหรือมีสิ่งกีดขวาง
10. ผลทดสอบ Meow และ Buzzer
11. Error Logs หากมี
12. วิดีโอ Final Demo เมื่อผ่าน Hardware Safety Tests

---

# Technical Information

| Component | Technology |
|---|---|
| Robot | ROSMASTER M1 |
| Object Detection | YOLO11n V7.2 |
| Model | `models/best.pt` |
| Class | `green_dino` |
| Camera | OpenCV |
| LiDAR | YDLIDAR T-MINI Plus |
| LiDAR SDK | Official YDLidar-SDK |
| Motor Library | `Rosmaster_Lib` |
| Web Interface | Python HTTP Server Port 8080 |
| Docker | Not Required |
| ROS2 | Optional |

## Main Files

| File | Purpose |
|---|---|
| `robot_teleop_yolo_pi_dryrun.py` | YOLO + Mock Motor |
| `robot_teleop_yolo_robot.py` | YOLO + Robot Controller |
| `robot_teleop_yolo_lidar.py` | LiDAR-integrated Entry Point |
| `tmini_plus_lidar.py` | T-MINI Plus Reader |
| `tests/test_tmini_plus_lidar.py` | Simulated LiDAR Tests |
| `models/best.pt` | Trained YOLO V7.2 Model |
| `requirements.txt` | Python Dependencies |

## Official References

- [YDLidar-SDK](https://github.com/YDLIDAR/YDLidar-SDK)
- [T-MINI Plus Python Example](https://github.com/YDLIDAR/YDLidar-SDK/blob/master/python/examples/tminiplus_test.py)
- [Yahboom T-MINI Plus Resources](https://github.com/YahboomTechnology/T-MINI-PLUS-Lidar)

**This repository provides experimental robot integration. Physical AUTO FOLLOW remains unverified until real hardware tests and independent stopping safeguards pass.**