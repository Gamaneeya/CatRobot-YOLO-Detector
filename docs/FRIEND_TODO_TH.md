# Cat Robot — Teammate Setup & Testing TODO

## เป้าหมาย

ติดตั้ง YOLO Green Dino V7.2 บน ROSMASTER M1 และทดสอบจนสามารถควบคุมให้หุ่นยนต์เดินตามตุ๊กตา Green Dino ได้จริง เมื่อระบบตรวจจับและความปลอดภัยพร้อม

**ไม่ใช้ Docker และไม่เขียนทับ `robot_teleop.py` เดิม**

คู่มือนี้แบ่งเป็นขั้นตอนที่ต้องทำตามลำดับ หากขั้นไหนไม่ผ่าน ให้เก็บ Error และหยุดก่อน ไม่ข้ามไปสั่งมอเตอร์จริง

---


> **UPDATE — T-MINI Plus LiDAR**
>
> LiDAR ของทีมคือ **YDLIDAR T-MINI Plus**
>
> มีไฟล์ Integration เพิ่มแล้ว:
> `tmini_plus_lidar.py` และ `robot_teleop_yolo_lidar.py`
>
> ให้ใช้ [T-MINI Plus Setup Guide](TMINI_PLUS_SETUP_TH.md)
> สำหรับติดตั้ง SDK, ตรวจ Serial Port, Calibrate,
> ทดลอง Motor แบบยกล้อ และทดสอบ AUTO ภายใต้การดูแล
>
> PHASE 7–9 ในเอกสารเดิมเป็นภาพรวมเท่านั้น
> ให้ยึดรายละเอียดของ T-MINI Plus Guide เป็นหลัก
>
> ยังห้ามทดลอง AUTO บนพื้นจนกว่าจะตรวจการหยุด
> และข้อจำกัดของ LiDAR แบบ 2D ครบถ้วน

# PHASE 0 — ก่อนเริ่ม

## 0.1 เตรียมอุปกรณ์

- [ ] Raspberry Pi / ROSMASTER M1
- [ ] แหล่งจ่ายไฟและแบตเตอรี่หุ่นยนต์
- [ ] กล้องของหุ่นยนต์
- [ ] Green Dino ตัวจริง
- [ ] LiDAR ที่ติดตั้งบนหุ่นยนต์
- [ ] คอมพิวเตอร์สำหรับ SSH และเปิดเว็บ
- [ ] อินเทอร์เน็ตสำหรับติดตั้งครั้งแรก
- [ ] พื้นที่โล่งสำหรับทดสอบ
- [ ] คนที่สามารถหยุดหุ่นยนต์หรือตัดกำลังมอเตอร์ได้ทันที

## 0.2 ตรวจไฟล์บน GitHub

Repository:

https://github.com/Gamaneeya/CatRobot-YOLO-Detector

ต้องเห็น:

- [ ] `models/best.pt`
- [ ] `requirements.txt`
- [ ] `robot_teleop_yolo_pi_dryrun.py`
- [ ] `docs/FRIEND_TODO_TH.md`

ไฟล์ `robot_teleop_yolo_robot.py` มีอยู่ใน Repository แล้ว แต่ยังไม่ได้รับการยืนยันการทำงานบนฮาร์ดแวร์จริง

การทดสอบมอเตอร์และ LiDAR ต้องทำตาม `docs/TMINI_PLUS_SETUP_TH.md` ก่อน และห้ามใช้ Dry Run แทนไฟล์มอเตอร์จริง

---

# PHASE 1 — ตรวจเครื่อง Raspberry Pi

**ทำขณะ Raspberry Pi ยังเข้าถึงอินเทอร์เน็ตได้**

## 1.1 เปิด Terminal หรือ SSH

ถ้าใช้ SSH:

```bash
ssh USERNAME@ROBOT_IP
```

เปลี่ยน `USERNAME` และ `ROBOT_IP` เป็นค่าจริงของ Raspberry Pi

ถ้า SSH ไม่ได้ ให้ตรวจว่า Pi เปิดอยู่ คอมกับ Pi อยู่เครือข่ายเดียวกัน และ SSH เปิดใช้งานแล้ว

## 1.2 ตรวจ OS และ Python

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

**ผลที่ต้องตรวจ**

- Architecture เป็น `aarch64` สำหรับระบบ Linux ARM64
- ทราบ Python Version ที่ใช้อยู่
- มีพื้นที่เก็บข้อมูลเพียงพอสำหรับ PyTorch และไฟล์ติดตั้งออฟไลน์
- ไม่มีปัญหาเกี่ยวกับไฟล์ระบบหรือพื้นที่เต็ม

ถ้าเป็น 32-bit หรือพื้นที่ไม่พอ ให้แจ้งก่อน เพราะอาจติดตั้ง PyTorch ตามแผนไม่ได้

- [ ] PHASE 1.2 ผ่าน

## 1.3 ตรวจกล้องและอุปกรณ์

```bash
lsusb
```

```bash
ls -l /dev/video*
```

```bash
ls -l /dev/myserial /dev/rplidar
```

ตรวจอุปกรณ์เสียง:

```bash
command -v aplay
```

```bash
command -v mpg123
```

```bash
aplay -l
```

ตรวจ Motor Library เดิม:

```bash
python3 -c "from Rosmaster_Lib import Rosmaster; print('ROSmaster library OK')"
```

หากไม่พบ Library หรืออุปกรณ์ใด ให้ส่งข้อความ Error กลับมา อย่าเพิ่งติดตั้งหรือแก้ไฟล์ควบคุมหุ่นยนต์โดยเดาเอง

- [ ] ตรวจกล้องแล้ว
- [ ] ตรวจ Motor Library แล้ว
- [ ] ตรวจ LiDAR แล้ว
- [ ] ตรวจระบบเสียงแล้ว

---

# PHASE 2 — ดาวน์โหลดโค้ดและติดตั้ง Libraries

**ยังต้องมีอินเทอร์เน็ต**

## 2.1 ติดตั้งเครื่องมือที่จำเป็น

```bash
sudo apt update
```

```bash
sudo apt install -y git python3-venv python3-pip v4l-utils libgl1 alsa-utils mpg123
```

หากบาง Package ไม่มีสำหรับ OS นี้ ให้เก็บ Error ก่อน ไม่ต้องเปลี่ยน Repository หรือ OS ของหุ่นยนต์เอง

## 2.2 ดาวน์โหลด Source Code

```bash
cd ~
```

```bash
git clone https://github.com/Gamaneeya/CatRobot-YOLO-Detector.git
```

```bash
cd CatRobot-YOLO-Detector
```

หากขึ้นว่าโฟลเดอร์มีอยู่แล้ว ให้เข้าโฟลเดอร์เดิม:

```bash
cd ~/CatRobot-YOLO-Detector
```

ตรวจ:

```bash
git status
```

```bash
git remote -v
```

หากเป็น Repository ที่ถูกต้องและไม่มี Local Changes ที่ต้องเก็บ จึงอัปเดตด้วย:

```bash
git pull --ff-only origin main
```

อย่าใช้ `git reset --hard` เพื่อลบไฟล์ของทีม

## 2.3 ตรวจไฟล์

```bash
ls -lh models/best.pt
```

```bash
ls -l robot_teleop_yolo_pi_dryrun.py
```

```bash
ls -l docs/FRIEND_TODO_TH.md
```

ไฟล์โมเดล V7.2 ที่ทีมเตรียมมีขนาด 5,477,466 bytes

หากขนาดไม่ตรงหรือโหลดโมเดลไม่ได้ ให้ตรวจว่า Pull มาถูก Repository และ Commit หรือไม่

- [ ] Clone/Pull ผ่าน
- [ ] ไฟล์สำคัญครบ

## 2.4 สร้าง Python Environment

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
which python
```

ผลต้องชี้ไปยัง Python ในโฟลเดอร์ `.venv` ของโปรเจกต์

## 2.5 ติดตั้ง Python Dependencies

```bash
python -m pip install --upgrade pip
```

```bash
python -m pip install -r requirements.txt
```

```bash
python -m pip check
```

`requirements.txt` ใช้ Ultralytics ซึ่งมี Dependencies อื่นรวมถึง PyTorch แต่การติดตั้งบน Linux ARM64 อาจต้องปรับตามรุ่น Python และ OS

**ห้ามตัดอินเทอร์เน็ตหากติดตั้งไม่ผ่าน**

ถ้าติดตั้งไม่ได้ ให้ส่ง Error ทั้งหมดพร้อมผล `uname -m` และ `python3 --version`

## 2.6 ตรวจ Imports

```bash
python -c "import cv2; print('OpenCV',cv2.__version__)"
```

```bash
python -c "import torch; print('PyTorch',torch.__version__)"
```

```bash
python -c "import ultralytics; print('Ultralytics',ultralytics.__version__)"
```

```bash
python -c "import numpy; print('NumPy',numpy.__version__)"
```

ถ้าทุกคำสั่งผ่าน:

- [ ] Python Environment ผ่าน
- [ ] PyTorch Import ได้
- [ ] OpenCV Import ได้
- [ ] Ultralytics Import ได้
- [ ] NumPy Import ได้
- [ ] `pip check` ไม่มี Dependency Conflict

---

# PHASE 3 — ตรวจ YOLO V7.2

## 3.1 โหลดโมเดล

```bash
python -c "from ultralytics import YOLO; m=YOLO('models/best.pt'); print(m.names)"
```

ต้องเห็น:

```text
{0: 'green_dino'}
```

## 3.2 ทดสอบ Inference

```bash
python -c "import numpy as np; from ultralytics import YOLO; m=YOLO('models/best.pt'); r=m.predict(np.zeros((480,640,3),dtype=np.uint8),imgsz=640,verbose=False); print('INFERENCE OK:',len(r))"
```

ต้องเห็น:

```text
INFERENCE OK: 1
```

นี่เป็นการทดสอบว่าโมเดลประมวลผลได้ ไม่ได้แปลว่าตรวจจับ Dino จริงผ่านแล้ว

- [ ] โหลด YOLO V7.2 ผ่าน
- [ ] ทดสอบ Inference ผ่าน

---

# PHASE 4 — เตรียม Source และ Dependencies สำหรับ Offline

**ต้องทำขณะยังออนไลน์อยู่**

จุดประสงค์คือเมื่อเปลี่ยนไปเชื่อมเครือข่าย Robot แล้ว จะไม่ต้องดาวน์โหลด Python Packages ใหม่

## 4.1 บันทึก Packages ที่ติดตั้งสำเร็จ

ตรวจว่า `.venv` เปิดใช้งานอยู่:

```bash
which python
```

สร้างโฟลเดอร์:

```bash
mkdir -p offline/wheels
```

บันทึก Package Versions:

```bash
python -m pip freeze > offline/requirements-pi.lock.txt
```

## 4.2 ดาวน์โหลด Wheels สำหรับ Raspberry Pi

```bash
python -m pip download --only-binary=:all: --dest offline/wheels -r offline/requirements-pi.lock.txt
```

หากมี Package ที่ดาวน์โหลด Wheel ไม่ได้ ต้องแก้ก่อนถือว่าชุดออฟไลน์พร้อม

กรณีใช้ PyTorch Wheel จากแหล่งเฉพาะหรือ Package ที่ Build เอง อาจต้องเก็บ Wheel ต้นฉบับแยก ไม่ใช่สมมติว่า `pip download` จะหาได้เสมอ

## 4.3 ทดลองติดตั้งโดยไม่ใช้อินเทอร์เน็ต

สร้าง Environment ทดสอบ:

```bash
python3 -m venv .venv_offline_test
```

ติดตั้งจากไฟล์ที่ดาวน์โหลดไว้เท่านั้น:

```bash
.venv_offline_test/bin/python -m pip install --no-index --find-links=offline/wheels -r offline/requirements-pi.lock.txt
```

ตรวจ Dependencies:

```bash
.venv_offline_test/bin/python -m pip check
```

ตรวจ Imports:

```bash
.venv_offline_test/bin/python -c "import torch, cv2, ultralytics; print('OFFLINE IMPORT OK')"
```

ตรวจโมเดล:

```bash
.venv_offline_test/bin/python -c "from ultralytics import YOLO; m=YOLO('models/best.pt'); print(m.names)"
```

ถ้าผ่านครบ ถือว่าชุด Python Packages ผ่านการทดลองติดตั้งออฟไลน์ในเครื่องนี้

หมายเหตุ: Wheels ไม่ได้ทดแทน System Packages ของ Linux และไม่รับประกันว่าจะใช้กับ OS/Python Version อื่นได้

- [ ] บันทึก Packages แล้ว
- [ ] ดาวน์โหลด Wheels ครบ
- [ ] ทดลองติดตั้ง Offline ผ่าน
- [ ] Offline Import ผ่าน
- [ ] โหลดโมเดลผ่าน

**ห้ามตัดอินเทอร์เน็ตจนกว่าขั้นนี้จะผ่าน**

---

# PHASE 5 — ตรวจ Camera ก่อนเปลี่ยน Network

## 5.1 ตรวจโปรแกรมที่ใช้กล้อง

```bash
sudo fuser -v /dev/video0
```

ตรวจ Port 8080:

```bash
sudo ss -ltnp | grep ':8080'
```

ถ้ามีโปรแกรมเดิมของทีมทำงานอยู่ ให้แจ้งก่อนปิด และห้ามรันสองโปรแกรมที่ใช้กล้องและ Port เดียวกันพร้อมกัน

## 5.2 ตรวจ Camera Device

```bash
v4l2-ctl --list-devices
```

ทดสอบ Camera Index 0:

```bash
python -c "import cv2; c=cv2.VideoCapture(0); ok,f=c.read(); print('Opened:',c.isOpened(),'Frame:',ok,'Shape:',None if f is None else f.shape); c.release()"
```

ต้องได้ `Opened: True` และ `Frame: True`

หากใช้ Raspberry Pi CSI Camera การเปิดภาพอาจต้องใช้ Picamera2 หรือ Camera Pipeline ที่แตกต่างจาก USB Webcam

อย่าเปลี่ยน Camera Index โดยเดาเองโดยไม่ตรวจอุปกรณ์

- [ ] Camera เปิดได้
- [ ] รู้ Camera Device ที่ถูกต้อง
- [ ] ไม่มี Process อื่นจับกล้องหรือ Port 8080 ตอนทดสอบ

---

# PHASE 6 — เชื่อม Robot Network และทดสอบ Dry Run

หลัง PHASE 1–5 ผ่านแล้ว สามารถสลับไปใช้เครือข่ายหุ่นยนต์ได้

## 6.1 ตรวจ IP ของ Raspberry Pi

```bash
hostname -I
```

หลังเปลี่ยนเครือข่าย IP อาจเปลี่ยนไป ต้องใช้ IP ใหม่และเชื่อม SSH ใหม่

## 6.2 รัน Dry Run

```bash
cd ~/CatRobot-YOLO-Detector
```

```bash
source .venv/bin/activate
```

```bash
python robot_teleop_yolo_pi_dryrun.py
```

หากไม่มี Error เปิด Browser จากคอมที่อยู่เครือข่ายเดียวกัน:

```text
http://ROBOT_IP:8080
```

เปลี่ยน `ROBOT_IP` เป็น IP จริง

## 6.3 ทดสอบผ่านหน้าเว็บ

- [ ] เปิดหน้าเว็บได้
- [ ] กล้องแสดงภาพ
- [ ] นำ Green Dino มาอยู่หน้ากล้อง
- [ ] Bounding Box ปรากฏ
- [ ] แสดง Confidence
- [ ] กด AUTO FOLLOW
- [ ] Dino อยู่ซ้าย → TURN LEFT
- [ ] Dino อยู่ขวา → TURN RIGHT
- [ ] Dino อยู่กลาง → FORWARD (SIM ONLY) เมื่อกรอบยังไม่ถึงเกณฑ์หยุด
- [ ] Dino หาย → NO TARGET - STOP
- [ ] กล้องขาดหรือข้อมูลเก่า → STOP
- [ ] กด STOP → STOPPED
- [ ] ล้อหุ่นยนต์ไม่เคลื่อนที่

**หากล้อเคลื่อนที่ใน Dry Run ให้หยุดทดสอบทันที** เพราะขัดกับพฤติกรรมที่ออกแบบไว้

บันทึกภาพหน้าเว็บ, Terminal Log, FPS และวิดีโอสั้น ๆ

หยุดด้วย `Ctrl+C`

---

# PHASE 7 — ตรวจ Motor สำหรับการเคลื่อนที่จริง

**ต้องมีคนอยู่กับหุ่นยนต์ และมีวิธีตัดกำลังมอเตอร์ทันที**

ขั้นนี้ต้องมี `robot_teleop_yolo_robot.py` เวอร์ชันที่ทีมตรวจสอบแล้วอยู่ใน Repository

ไฟล์ Robot มีอยู่แล้ว แต่ยังต้องตรวจ Motor Library, Motor Direction และระบบหยุดตามคู่มือ T-MINI Plus ก่อน

## 7.1 ตรวจโปรแกรมก่อนใช้งาน

- [ ] ใช้ไฟล์ Robot จริง ไม่ใช่ Dry Run
- [ ] เริ่มต้นใน `STOPPED`
- [ ] Motor Backend เชื่อมกับอุปกรณ์ของ ROSMASTER ได้
- [ ] ใช้ความเร็วจำกัดสำหรับการทดสอบ
- [ ] ตรวจ Target Confidence อย่างเหมาะสม
- [ ] มีการยืนยัน Target ต่อเนื่องหลาย Frame
- [ ] หยุดเมื่อ Camera/YOLO Error
- [ ] หยุดเมื่อข้อมูล Detection หมดอายุ
- [ ] หยุดเมื่อขาด Web Control Heartbeat
- [ ] ปุ่ม STOP ใช้ได้
- [ ] มีวิธีหยุดหรือตัดกำลังมอเตอร์ที่ไม่ขึ้นอยู่กับหน้าเว็บ

หากไม่ผ่านข้อใด ห้ามทดลองบนพื้น

## 7.2 ทดสอบมอเตอร์แบบยกล้อพ้นพื้น

จัดวางหุ่นยนต์บนฐานที่มั่นคงเพื่อให้ล้อไม่สัมผัสพื้น

ทดสอบกับคนที่สามารถตัดกำลังมอเตอร์ได้ทันที:

- [ ] ล้อหยุดนิ่งตอนเริ่มโปรแกรม
- [ ] MANUAL FORWARD หมุนล้อในทิศทางเดินหน้า
- [ ] MANUAL LEFT หมุนในทิศทางเลี้ยวซ้าย
- [ ] MANUAL RIGHT หมุนในทิศทางเลี้ยวขวา
- [ ] ปล่อยปุ่มแล้วหยุด
- [ ] กด STOP แล้วหยุด
- [ ] ปิดหน้าเว็บหรือขาด Heartbeat แล้วหยุด
- [ ] กล้องหรือ Inference Error แล้วหยุด

หากทิศทางผิด ให้หยุดและตรวจการตั้งค่าควบคุมก่อนทดสอบต่อ

**ไม่ทดสอบการไล่ตาม Dino บนพื้นในขั้นนี้**

---

# PHASE 8 — ตรวจ LiDAR และระบบกันชน

การมี `/dev/rplidar` ไม่ได้หมายความว่าอ่านข้อมูลระยะได้แล้ว

ต้องยืนยันว่าระบบได้รับข้อมูลระยะจริงจาก LiDAR และข้อมูลใหม่เพียงพอสำหรับการหยุดรถ

## 8.1 ตรวจอุปกรณ์

```bash
ls -l /dev/serial/by-id/
```

```bash
lsusb
```

ตรวจว่าโปรแกรมอื่นจับอุปกรณ์อยู่หรือไม่:

```bash
sudo fuser -v /dev/rplidar
```

จากนั้นต้องทดสอบด้วย Driver หรือโปรแกรมอ่าน LiDAR ที่ตรงกับรุ่นอุปกรณ์จริง

## 8.2 สิ่งที่ต้องผ่าน

- [ ] ระบุรุ่น LiDAR ได้
- [ ] อ่านข้อมูลระยะจริงได้
- [ ] ตรวจสอบทิศหน้า Robot ได้
- [ ] แยกข้อมูล LiDAR ขาด/หมดอายุได้
- [ ] มีการกำหนดระยะหยุดจากการทดสอบจริง
- [ ] หยุดเมื่อมีสิ่งกีดขวาง
- [ ] หยุดเมื่อข้อมูล LiDAR ไม่พร้อม
- [ ] ทดสอบการหยุดโดยใช้สิ่งกีดขวางกับล้อที่ยกพ้นพื้นแล้ว
- [ ] Emergency Stop ผ่าน

**ถ้ายังไม่มี LiDAR Reader หรือยังไม่สามารถอ่านระยะได้จริง ห้ามเปิด AUTO FOLLOW แบบล้อสัมผัสพื้น**

Bounding-box area ไม่ใช่ตัวแทนระยะที่ปลอดภัย

---

# PHASE 9 — Physical AUTO FOLLOW Test

ทำได้ต่อเมื่อ PHASE 7–8 ผ่านและมีผู้ควบคุมดูแลจริง

## 9.1 เตรียมพื้นที่

- [ ] พื้นเรียบและไม่มีสิ่งกีดขวางอันตราย
- [ ] ไม่มีขอบบันไดหรือจุดตก
- [ ] ไม่มีคนหรือสัตว์เข้ามาอยู่ในทางวิ่ง
- [ ] กล้องมองเห็น Dino ได้ชัดเจน
- [ ] LiDAR อ่านข้อมูลได้
- [ ] มีคนพร้อมหยุดหุ่นยนต์
- [ ] ใช้ความเร็วต่ำสำหรับการทดสอบครั้งแรก

## 9.2 ลำดับการทดสอบ

1. เปิดโปรแกรม Robot จริงในโหมด STOPPED
2. ตรวจว่า Motor ไม่เคลื่อนที่
3. เปิดหน้าเว็บและตรวจกล้อง
4. วาง Dino หน้า Robot
5. ยืนยันว่า YOLO ตรวจจับถูกต้อง
6. ตรวจ LiDAR ว่าทางข้างหน้าปลอดภัย
7. เปิด AUTO FOLLOW ภายใต้การควบคุมดูแล
8. ขยับ Dino ทางซ้าย ตรวจว่าหุ่นยนต์เลี้ยวซ้าย
9. ขยับ Dino ทางขวา ตรวจว่าหุ่นยนต์เลี้ยวขวา
10. วาง Dino กลางภาพในระยะที่ปลอดภัย ตรวจว่าหุ่นยนต์เดินหน้า
11. ตรวจว่าหุ่นยนต์หยุดเมื่อเข้าใกล้เกณฑ์ที่กำหนด
12. นำ Dino ออกจากกล้อง ตรวจว่าหยุด
13. ทดสอบสิ่งกีดขวางภายใต้การควบคุมและระยะที่ปลอดภัย ตรวจว่าหยุด
14. กด STOP และตรวจว่าหยุดทันทีตามข้อกำหนดที่ทดสอบไว้

ถ้าพบพฤติกรรมผิดปกติ ให้หยุดการทดลองและเก็บ Log ก่อนแก้ไข

---

# PHASE 10 — Audio และ Final Demo

ทดสอบระบบเสียงแยกจาก Motor

- [ ] ตรวจพบอุปกรณ์เสียง
- [ ] เล่นเสียง WAV ผ่าน `aplay` ได้
- [ ] เล่น MP3 ผ่าน `mpg123` ได้ หากต้องใช้
- [ ] ปุ่ม Meow ทำงาน
- [ ] ปุ่ม Buzzer / SOS ทำงาน
- [ ] ระบบเสียงไม่ทำให้ Loop ควบคุมมอเตอร์ค้าง
- [ ] กด STOP ระหว่างมีเสียงแล้วมอเตอร์ยังหยุดได้

ไฟล์ Dry Run ที่ใช้ `winsound` ไม่ได้ยืนยันว่าเสียงแมวทำงานบน Pi

เมื่อผ่านทุกส่วน จึงบันทึกวิดีโอ Final Demo

---

# TROUBLESHOOTING

## A. Clone ไม่ได้

**อาการ:** `Could not resolve host: github.com`

สาเหตุที่เป็นไปได้: Raspberry Pi ไม่มีอินเทอร์เน็ตหรือ DNS ไม่พร้อม

ตรวจ:

```bash
ping -c 3 1.1.1.1
```

```bash
getent hosts github.com
```

ให้ดาวน์โหลด Code ขณะออนไลน์ก่อนเปลี่ยนไปใช้ Robot Wi-Fi

หาก Pi ไม่มีอินเทอร์เน็ตตั้งแต่แรก ต้องใช้วิธีโอนโค้ดจากคอมผ่าน USB หรือ LAN และเตรียม Dependencies สำหรับ Pi แยกต่างหาก

## B. `No module named ultralytics`

ตรวจว่าเปิด Environment ถูกต้อง:

```bash
source .venv/bin/activate
```

```bash
which python
```

```bash
python -m pip list
```

ถ้าติดตั้งไม่ครบ ให้แก้ตอนออนไลน์หรือใช้ Wheels ที่ผ่านการทดสอบแล้ว

## C. `No matching distribution found for torch`

ตรวจ:

```bash
uname -m
```

```bash
python3 --version
```

PyTorch ต้องตรงกับ Linux Architecture และ Python Version

อย่านำ Wheels จาก Windows มาใช้กับ Pi

## D. `libGL.so.1` not found

ขณะออนไลน์:

```bash
sudo apt install -y libgl1
```

หากยังผิดพลาด ให้เก็บข้อความ Error และตรวจ System Libraries เพิ่มเติมก่อนตัดเน็ต

## E. Camera เปิดไม่ได้

ตรวจ:

```bash
v4l2-ctl --list-devices
```

```bash
sudo fuser -v /dev/video0
```

อาจเกิดจากกล้องคนละ Index, กล้องถูกใช้งานอยู่, Permission หรือเป็น CSI Camera ที่ต้องใช้ Pipeline อื่น

อย่า Kill โปรแกรมที่ไม่รู้จัก

## F. `Address already in use`

ตรวจ:

```bash
sudo ss -ltnp | grep ':8080'
```

โปรแกรมอื่นอาจใช้ Port 8080 อยู่แล้ว

ปิดเฉพาะโปรแกรมที่ยืนยันได้ว่าเป็นของทีมและปลอดภัยที่จะหยุด

## G. เปิดหน้าเว็บไม่ได้

ตรวจ IP ล่าสุด:

```bash
hostname -I
```

ตรวจว่าโปรแกรมยังรันอยู่ และคอมกับ Raspberry Pi อยู่เครือข่ายเดียวกัน

หน้าเว็บนี้ไม่มี Authentication จึงควรใช้งานเฉพาะเครือข่ายภายในที่เชื่อถือได้

## H. YOLO จับเสื้อสีเขียวแทน Dino

ห้ามใช้การตรวจจับที่ผิดไปสั่งเดินหน้า

เก็บรูปหรือวิดีโอ พร้อม Confidence และตำแหน่ง Bounding Box แล้วรายงานกลับมา

สำหรับการใช้กับมอเตอร์จริงต้องมีเกณฑ์ตรวจสอบ Target ที่เข้มงวดกว่า Simulator

## I. AUTO FOLLOW ไม่เดิน

ตรวจสถานะ:

- ยังอยู่ STOPPED หรือไม่
- ขาด Web Heartbeat หรือไม่
- Detection เก่าเกินเวลาหรือไม่
- Confidence ผ่านเกณฑ์หรือไม่
- LiDAR อนุญาตให้เคลื่อนที่หรือไม่

ห้ามแก้ด้วยการปิด Safety Checks โดยไม่ได้ตรวจสาเหตุ

## J. Motor หมุนผิดทิศ

กด STOP แล้วตัดการทดสอบ

ตรวจทิศทางของมอเตอร์และค่าที่ส่งเข้า Backend โดยเริ่มใหม่จากการยกล้อพ้นพื้น

ห้ามทดลองกลับเครื่องหมายความเร็วบนพื้นที่มีคนหรือสิ่งกีดขวาง

## K. LiDAR ไม่มีข้อมูล

ตรวจอุปกรณ์, Serial Port, Permission และ Driver ให้ตรงกับรุ่น

ถ้าข้อมูลหายหรือหมดอายุ ให้ระบบอยู่ในสถานะห้ามเคลื่อนที่

ห้ามใช้ Bounding Box แทน LiDAR Safety

## L. Robot ไม่หยุดหรือวิ่งผิดปกติ

ใช้วิธีหยุดฉุกเฉินหรือตัดกำลังมอเตอร์ที่เตรียมไว้ทันที

ไม่พึ่งเฉพาะปุ่ม STOP บนหน้าเว็บ เพราะโปรแกรมหรือระบบสื่อสารอาจค้างได้

อย่าเริ่มทดสอบใหม่จนกว่าจะหาสาเหตุได้

---

# รายงานผลกลับให้ทีม

ทุกครั้งที่พบปัญหา ให้ส่ง:

1. Phase และหมายเลข Step ที่ทำ
2. คำสั่งที่พิมพ์
3. ผลลัพธ์หรือ Error แบบเต็ม
4. Python Version และ Architecture (หากเป็นปัญหาติดตั้ง)
5. รูปหน้าเว็บหรือหน้าจอ Terminal
6. วิดีโอสั้น ๆ หากเป็นปัญหากล้องหรือมอเตอร์
7. แจ้งว่าขณะเกิดปัญหาอยู่ใน MANUAL, AUTO หรือ STOPPED

## Final Completion Checklist

- [ ] Source Code บน Pi ครบ
- [ ] Online Dependencies ผ่าน
- [ ] Offline Backup ผ่าน
- [ ] YOLO V7.2 โหลดและ Inference ได้
- [ ] Camera และ Web UI ใช้ได้
- [ ] Dry Run ผ่าน
- [ ] Real Motor Backend ผ่าน
- [ ] Motor Direction ผ่าน
- [ ] Emergency Stop ผ่าน
- [ ] LiDAR Safety ผ่าน
- [ ] Physical AUTO FOLLOW ผ่าน
- [ ] Meow / Buzzer ผ่าน
- [ ] บันทึกวิดีโอ Demo และส่ง Log ให้ทีม

**หมายเหตุ:** จนกว่าไฟล์ Real Robot จะได้รับการตรวจสอบและผ่านการทดสอบ Motor/LiDAR ให้ถือว่างานพร้อมเฉพาะขั้น Dry Run ไม่ใช่พร้อมเดินตาม Dino บนพื้นจริง