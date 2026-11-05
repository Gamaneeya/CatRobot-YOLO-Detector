# ROSMASTER M1 — YOLO Green Dino Setup Guide

**Project:** Interactive Cat Robot  
**Model:** Custom YOLO11n V7.2 (`green_dino`)  
**Repository:** https://github.com/Gamaneeya/CatRobot-YOLO-Detector  
**Platform:** Raspberry Pi, ไม่ใช้ Docker  
**First test:** Camera + YOLO + Mock Motor

---

## กฎสำคัญก่อนเริ่ม

- ห้ามแก้หรือเขียนทับ `robot_teleop.py` เดิมบนหุ่นยนต์
- ห้ามรัน `robot_teleop.py` และไฟล์ Dry Run พร้อมกัน เพราะอาจแย่งกล้องและ Port 8080
- ห้ามเปิดใช้งานมอเตอร์จริงจากโค้ด Dry Run
- ถ้าคำสั่งใด Error ให้เก็บข้อความ Error ทั้งหมดไว้
- ห้ามตัดอินเทอร์เน็ตจนกว่าจะผ่านขั้นตรวจ Dependencies และการทดสอบออฟไลน์

## PHASE A — ตรวจ Raspberry Pi ขณะมีอินเทอร์เน็ต

### A1. เข้า Raspberry Pi

ใช้ SSH, Terminal หรือวิธีที่ทีมใช้อยู่เดิม

ถ้าเข้า SSH จากคอม ให้ใช้ชื่อผู้ใช้และ IP ที่ถูกต้องของ Pi

```bash
ssh pi@ROBOT_IP
```

`ROBOT_IP` เป็นตัวแทน IP จริง ไม่ต้องพิมพ์คำนี้ตรง ๆ

### A2. ตรวจระบบ

รันทีละคำสั่ง:

```bash
whoami
```

```bash
uname -m
```

```bash
python3 --version
```

```bash
cat /etc/os-release
```

```bash
df -h /
```

```bash
free -h
```

ตรวจว่า OS เป็น 64-bit หรือไม่ โดยผล `uname -m` สำหรับ ARM64 ควรเป็น `aarch64`

ถ้าขึ้น `armv7l` หรือ `armv6l` ให้หยุดก่อน เพราะการติดตั้ง PyTorch แบบที่เราวางแผนอาจใช้ไม่ได้

### A3. ตรวจกล้องและอุปกรณ์

```bash
lsusb
```

```bash
ls -l /dev/video*
```

```bash
ls -l /dev/myserial /dev/rplidar
```

```bash
v4l2-ctl --list-devices
```

ถ้า `v4l2-ctl` ไม่มีคำสั่ง ให้ติดตั้ง `v4l-utils` ใน PHASE B

อุปกรณ์บางตัวไม่พบได้ แต่ต้องรายงานผล ไม่ถือว่าใช้งานได้โดยอัตโนมัติ

### A4. ตรวจ Libraries เดิมของเพื่อน

```bash
python3 -c "import cv2; print('OpenCV:', cv2.__version__)"
```

```bash
python3 -c "import torch; print('Torch:', torch.__version__)"
```

```bash
python3 -c "import ultralytics; print('Ultralytics:', ultralytics.__version__)"
```

```bash
python3 -c "import Rosmaster_Lib; print('Rosmaster:', Rosmaster_Lib.__file__)"
```

ถ้าตัวไหนไม่พบ ให้จดไว้ก่อน ยังไม่ต้องลบ Library หรือเปลี่ยน Python เดิมของหุ่นยนต์

---

## PHASE B — ดาวน์โหลดโค้ดและติดตั้ง Dependencies ขณะ ONLINE

**ต้องทำตอน Raspberry Pi มีอินเทอร์เน็ต**

### B1. ติดตั้งเครื่องมือระบบ

```bash
sudo apt update
```

```bash
sudo apt install -y git python3-venv python3-pip v4l-utils libgl1 libglib2.0-0
```

ถ้าคำสั่งติดตั้งล้มเหลวหรือมี Package หาไม่พบ ให้หยุดและส่ง Error กลับมา

### B2. ดาวน์โหลด Repository

```bash
cd ~
```

```bash
git clone https://github.com/Gamaneeya/CatRobot-YOLO-Detector.git
```

```bash
cd CatRobot-YOLO-Detector
```

ถ้าโฟลเดอร์มีอยู่แล้ว ห้าม Clone ทับ ให้ตรวจ:

```bash
git status
```

```bash
git remote -v
```

หากเป็น Repository ที่ถูกต้องและไม่มี Local Changes ที่ต้องเก็บ จึงใช้:

```bash
git pull --ff-only origin main
```

### B3. ตรวจไฟล์สำคัญ

```bash
ls -lh models/best.pt
```

```bash
ls -l robot_teleop_yolo_pi_dryrun.py
```

```bash
ls -l requirements.txt
```

ถ้าไม่พบไฟล์ใดไฟล์หนึ่ง ให้หยุดก่อน ยังไม่ต้องติดตั้ง

### B4. สร้าง Python Environment ใหม่

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
which python
```

ผล `which python` ต้องชี้ไปที่ `.venv/bin/python` ของ Repository นี้

### B5. ติดตั้ง Python Libraries

```bash
python -m pip install --upgrade pip
```

```bash
python -m pip install -r requirements.txt
```

ตรวจความเข้ากันได้:

```bash
python -m pip check
```

ต้องไม่มี Dependency Conflict ที่ยังแก้ไม่เสร็จ

**ถ้า PyTorch, NumPy หรือ OpenCV ติดตั้งไม่ผ่าน หยุดที่ขั้นนี้ ห้ามตัดอินเทอร์เน็ต**

### B6. ตรวจ Imports ใน Environment ใหม่

```bash
python -c "import platform, cv2, torch, ultralytics, numpy; print('Architecture:', platform.machine()); print('OpenCV:', cv2.__version__); print('Torch:', torch.__version__); print('Ultralytics:', ultralytics.__version__); print('NumPy:', numpy.__version__)"
```

หาก Import ได้ครบ ถือว่าผ่านขั้น Dependencies แต่ยังต้องทดสอบโมเดลและกล้อง

---

## PHASE C — ตรวจ YOLO V7.2

### C1. โหลดโมเดล

จากโฟลเดอร์ Repository และเปิดใช้งาน `.venv` แล้ว:

```bash
python -c "from ultralytics import YOLO; m=YOLO('models/best.pt'); print(m.names)"
```

ผลควรเป็น:

```text
{0: 'green_dino'}
```

### C2. ทดสอบ Inference โดยไม่ใช้กล้อง

```bash
python -c "import numpy as np; from ultralytics import YOLO; m=YOLO('models/best.pt'); r=m.predict(np.zeros((480,640,3),dtype=np.uint8),imgsz=640,verbose=False); print('Inference OK:',len(r))"
```

ถ้าขึ้น `Inference OK: 1` แปลว่าโมเดลทำ Inference กับภาพทดสอบได้ ไม่ได้หมายความว่าตรวจจับ Dino จริงผ่านแล้ว

### C3. ตรวจกล้อง

ต้องปิดโปรแกรมที่ใช้กล้องอยู่ก่อน

```bash
sudo fuser -v /dev/video0
```

```bash
v4l2-ctl --list-devices
```

ทดสอบเปิด Camera Index 0:

```bash
python -c "import cv2; c=cv2.VideoCapture(0); ok,f=c.read(); print('Opened:',c.isOpened(),'Frame:',ok,'Shape:',None if f is None else f.shape); c.release()"
```

ถ้า `Opened: True` และ `Frame: True` ถือว่าเปิดกล้องผ่าน OpenCV ได้

หากกล้องเป็น Raspberry Pi CSI Camera แทน USB Webcam อาจต้องใช้วิธีเปิดภาพอีกแบบ อย่าเดา Index ไปเรื่อย ๆ โดยไม่ตรวจอุปกรณ์

---

## PHASE D — เตรียม Backup Dependencies สำหรับ Offline

**ยังต้องมีอินเทอร์เน็ตในขั้นนี้**

### D1. บันทึก Versions ที่ติดตั้งสำเร็จ

ตรวจว่าอยู่ใน `.venv` ของโปรเจกต์ แล้วรัน:

```bash
mkdir -p offline/wheels
```

```bash
python -m pip freeze > offline/requirements-pi.lock.txt
```

### D2. ดาวน์โหลดไฟล์ติดตั้งสำหรับ Pi

```bash
python -m pip download --only-binary=:all: --dest offline/wheels -r offline/requirements-pi.lock.txt
```

คำสั่งนี้ดาวน์โหลด Python Wheels สำหรับสภาพแวดล้อมปัจจุบันของ Pi โดยเฉพาะ

ถ้าดาวน์โหลดบาง Package ไม่ได้ ห้ามถือว่าชุดออฟไลน์ครบ ให้บันทึก Error และแก้ขณะยังมีอินเทอร์เน็ต

### D3. ทดสอบติดตั้งจากไฟล์ Offline จริง

สร้าง Environment สำหรับทดสอบแยกจากตัวหลัก:

```bash
python3 -m venv .venv_offline_test
```

ติดตั้งโดยห้ามใช้ Package Index ออนไลน์:

```bash
.venv_offline_test/bin/python -m pip install --no-index --find-links=offline/wheels -r offline/requirements-pi.lock.txt
```

ตรวจผล:

```bash
.venv_offline_test/bin/python -m pip check
```

```bash
.venv_offline_test/bin/python -c "import cv2, torch, ultralytics; print('OFFLINE IMPORT OK')"
```

```bash
.venv_offline_test/bin/python -c "from ultralytics import YOLO; m=YOLO('models/best.pt'); print(m.names)"
```

**ต้องผ่านครบ** จึงถือว่าชุด Python Dependencies สำรองสามารถติดตั้งแบบออฟไลน์ได้

หมายเหตุ: Python Wheels ไม่ได้แทน System Packages ของ Linux ทุกตัว จึงต้องติดตั้งของระบบใน PHASE B ให้ครบก่อนเช่นกัน

---

## PHASE E — เชื่อมเครือข่ายหุ่นยนต์และทดสอบ Dry Run

ทำหลังจาก PHASE B–D ผ่านแล้ว

### E1. เปลี่ยนไปใช้เครือข่ายของ Robot

เชื่อมคอมพิวเตอร์เข้ากับเครือข่ายเดียวกับ Raspberry Pi ตามวิธีที่ทีมใช้อยู่

หากต้องเปลี่ยน Wi-Fi ของ Pi อาจทำให้ SSH เดิมตัด ให้เชื่อม SSH ใหม่ด้วย IP ล่าสุดของ Pi

**ไม่มีอินเทอร์เน็ตก็ยังสามารถใช้ SSH และหน้าเว็บได้ หากอุปกรณ์อยู่ใน LAN เดียวกัน**

### E2. ตรวจ Port และ Camera

```bash
sudo ss -ltnp | grep ':8080'
```

```bash
sudo fuser -v /dev/video0
```

ถ้ามีโปรแกรมเดิมใช้อยู่ ให้ปิดเฉพาะโปรแกรมที่ยืนยันได้ว่าเป็นของทีมและไม่จำเป็นในขณะนั้น

### E3. เปิด Dry Run

```bash
cd ~/CatRobot-YOLO-Detector
```

```bash
source .venv/bin/activate
```

```bash
python robot_teleop_yolo_pi_dryrun.py
```

ตรวจ IP ของ Pi:

```bash
hostname -I
```

คำสั่งตรวจ IP อาจต้องเปิดอีก Terminal หรือ SSH Session

เปิดเว็บจากคอมที่อยู่ในเครือข่ายเดียวกัน:

```text
http://ROBOT_IP:8080
```

แทน `ROBOT_IP` ด้วย IP จริง

### E4. ทดสอบการตรวจจับ

ทดสอบตามลำดับ:

1. เปิดหน้าเว็บและตรวจว่ากล้องมีภาพ
2. นำ Green Dino มาอยู่กลางกล้อง
3. ตรวจว่า Bounding Box ปรากฏ
4. กด AUTO FOLLOW
5. ขยับ Dino ไปทางซ้ายและขวา
6. ตรวจข้อความ TURN LEFT / TURN RIGHT
7. วาง Dino กลางภาพและตรวจ FORWARD (SIM ONLY)
8. เอา Dino ออกจากกล้องแล้วตรวจ NO TARGET - STOP
9. กด STOP และตรวจว่าเปลี่ยนเป็น STOPPED

**ในขั้นนี้ล้อหุ่นยนต์ต้องไม่เคลื่อนที่** เพราะใช้ Mock Motor

ถ้าล้อเคลื่อนที่ ให้ปิดโปรแกรมและหยุดการทดสอบทันที เนื่องจากไม่ตรงกับพฤติกรรมที่คาดไว้

### E5. หยุดโปรแกรม

ใน Terminal ที่รัน Dry Run กด:

```text
Ctrl+C
```

---

## Troubleshooting — เมื่อมีปัญหา

### 1. `No module named ultralytics` หรือ `No module named cv2`

ตรวจว่าเปิด Environment ถูกต้อง:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
which python
python -m pip list
```

ถ้า Library ไม่อยู่ ให้ใช้ไฟล์ Offline ที่เตรียมไว้ ไม่ต้องเปลี่ยน Python ระบบของเพื่อน

### 2. `No matching distribution found for torch`

ตรวจ:

```bash
uname -m
python3 --version
```

อาจเกิดจาก OS 32-bit หรือ Python Version ที่ไม่มี Wheel ตรงกัน

ให้แก้ขณะมีอินเทอร์เน็ต ห้ามนำ Wheel ของ Windows มาแทน

### 3. `libGL.so.1` not found

ขณะออนไลน์:

```bash
sudo apt install -y libgl1
```

### 4. `Cannot open webcam 0`

ตรวจกล้อง:

```bash
v4l2-ctl --list-devices
sudo fuser -v /dev/video0
```

ตรวจว่าโปรแกรมเดิมยังจับกล้องอยู่หรือไม่ และ Camera Index 0 ตรงกับอุปกรณ์จริงหรือไม่

หากเป็น CSI Camera ให้แจ้งชนิดกล้องก่อนปรับโค้ด

### 5. `Address already in use` หรือ Port 8080 ใช้ไม่ได้

```bash
sudo ss -ltnp | grep ':8080'
```

หาว่าโปรแกรมใดเปิด Port 8080 อยู่ แล้วปิดเฉพาะโปรแกรมที่ทราบแน่ชัดว่าไม่จำเป็น

### 6. เปิดหน้าเว็บจากคอมไม่ได้

ตรวจว่า Pi และคอมอยู่เครือข่ายเดียวกัน และใช้ IP ล่าสุด ไม่ใช่ IP จาก Wi-Fi เดิม

ตรวจว่าโปรแกรมยังรันอยู่และไม่มี Error

### 7. `models/best.pt` ไม่พบ

ตรวจ:

```bash
pwd
ls -lh models/best.pt
```

ต้องรันจากโฟลเดอร์ Repository ที่มีโมเดลอยู่จริง

### 8. ตรวจจับเสื้อสีเขียวผิดเป็น Dino

การตรวจจับผิดเกิดขึ้นได้ โดยเฉพาะเมื่อ Threshold ต่ำ

อย่าใช้ผลจากการตรวจจับเพียงอย่างเดียวไปสั่งให้หุ่นยนต์เคลื่อนที่จริง

เก็บภาพหรือวิดีโอของเหตุการณ์และแจ้ง Confidence ที่แสดงบนกล้อง

### 9. ภาพกระตุกหรือ FPS ต่ำ

บันทึก FPS, CPU และ RAM ก่อน

```bash
free -h
```

```bash
top
```

การลด `IMG_SIZE` อาจช่วยได้ แต่ต้องทดสอบความแม่นยำอีกครั้ง ห้ามถือว่าผ่านโดยอัตโนมัติ

### 10. เสียงแมวไม่ทำงาน

ไฟล์ Dry Run มีส่วนเล่นเสียงด้วย `winsound` ของ Windows จึงยังไม่ใช่ตัวทดสอบเสียงบน Raspberry Pi

ให้ใช้ระบบเสียงในโปรแกรมเดิมของเพื่อนทดสอบแยกต่างหาก

---

## Checklist ก่อนรายงานว่าผ่าน

- [ ] Python และ OS Architecture ตรวจแล้ว
- [ ] ตรวจอุปกรณ์ USB / Camera แล้ว
- [ ] ติดตั้ง Dependencies สำเร็จ
- [ ] `pip check` ผ่าน
- [ ] โหลด `green_dino` ได้
- [ ] ทดสอบ Inference สำเร็จ
- [ ] Offline Wheels ดาวน์โหลดครบ
- [ ] ทดลองติดตั้ง Offline สำเร็จ
- [ ] Camera เปิดภาพได้
- [ ] Web UI เปิดจากคอมได้
- [ ] YOLO ตรวจ Dino ได้
- [ ] Auto Follow แสดง LEFT / RIGHT / FORWARD / STOP ได้
- [ ] ล้อหุ่นยนต์ไม่เคลื่อนที่ใน Dry Run
- [ ] เก็บ Log และภาพทดสอบแล้ว

**เมื่อผ่าน Checklist นี้ จะถือว่าผ่านเฉพาะ YOLO + Camera + Mock Follow บน Raspberry Pi เท่านั้น**

ยังไม่ถือว่าผ่าน Motor Integration, LiDAR Collision Avoidance หรือ Actual Robot Following

## สิ่งที่ต้องส่งกลับให้ทีม

ส่งข้อความผลคำสั่ง, Error, รูปหน้าเว็บ, FPS และวิดีโอทดสอบสั้น ๆ พร้อมระบุว่าแต่ละขั้นผ่านหรือไม่ผ่าน

ถ้าขั้นใดไม่ผ่าน ให้หยุดขั้นถัดไปที่ขึ้นอยู่กับขั้นนั้นก่อน

---

## ขั้นต่อไปหลัง Dry Run

การเคลื่อนที่จริงต้องใช้โค้ดแยกจาก Dry Run และต้องผ่านการตรวจ Motor Backend, ทิศทางการหมุน, ความเร็ว, การอ่าน LiDAR, การหยุดเมื่อกล้องขาด และ Emergency Stop

ให้ทดสอบมอเตอร์แบบยกล้อพ้นพื้นและมีคนพร้อมหยุดระบบก่อนการทดสอบบนพื้นจริง