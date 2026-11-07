# ROSMASTER M1 — Real Dino Follow (Raspberry Pi + YOLO + ROS2 Docker)

> คู่มือส่งต่อให้สมาชิกทีม | อัปเดต 7 พฤศจิกายน 2026 | ฮาร์ดแวร์เป้าหมาย: ROSMASTER M1, Raspberry Pi, USB camera, YDLIDAR T-MINI Plus
>
> **นี่คือชุดสั่งหุ่นยนต์จริง ไม่ใช่ dry run**. ต้องยกล้อพ้นพื้นและเตรียมตัดไฟมอเตอร์ได้ทันทีในการทดสอบขั้นแรก ห้ามถือว่า ROS2 log เป็นหลักฐานว่าล้อหยุดได้ปลอดภัยในสถานการณ์จริง

## 1. ระบบนี้ทำอะไร

- Web UI เดิมจาก `robot_teleop_yolo_robot.py` ที่ `http://<PI_IP>:8080`: Live camera, YOLO bounding box, MANUAL / AUTO FOLLOW / STOP, WASD, เสียงแมว, Buzzer, Camera Servo
- `run_teleop_yolo_real.py`: เรียกใช้ UI/YOLO เดิมและฟังก์ชันเสียงจาก `robot_teleop.py`, ใช้ Main Thread รัน YOLO และตรวจ LiDAR ก่อนส่งคำสั่งเคลื่อนที่
- `dino_motion.py`: เชื่อม Raspberry Pi ไปยัง ROS2 ภายใน **Docker container ที่มีอยู่เดิม** (`/cmd_vel`, `/Servo`, `/Buzzer`) โดยไม่ให้ Python บน Pi เปิด Serial Motor โดยตรง และอ่าน LiDAR ในอีก Process
- Docker ของ Yahboom รัน **driver-only** `ros2 run yahboomcar_bringup Mcnamu_driver_M1` บน ROS Domain 62; ตัว Driver เป็นผู้ครองพอร์ต Motor Controller

**ห้ามเปิด** `robot_teleop.py`, `robot_teleop_yolo_robot.py`, `dino_live.py`, `cat_robot_follow.py`, หรือ ROS2 launch motor-driver ตัวที่สอง **พร้อมกัน** กับ `run_teleop_yolo_real.py`.

## 2. ไฟล์ใน Repository

โครงสร้างขั้นต่ำที่ต้องมีบน Raspberry Pi:

```text
CatRobot-YOLO-Detector/
├── models/
│   └── best.pt
├── robot_teleop.py                # ไฟล์ออริจินัลของเพื่อน (ต้องอัปโหลดเพิ่มเติม)
├── robot_teleop_yolo_robot.py     # UI/YOLO เดิมใน Repository
├── run_teleop_yolo_real.py       # ตัวเริ่มระบบจริง
├── dino_motion.py                # ROS2 /cmd_vel, /Servo, /Buzzer + isolated LiDAR
├── tmini_plus_lidar.py           # YDLIDAR reader เดิม
├── requirements.txt
└── README_REAL_ROBOT_TH.md
```

ตรวจเมื่อ Clone เสร็จ:

```bash
ls -lh robot_teleop.py robot_teleop_yolo_robot.py run_teleop_yolo_real.py dino_motion.py tmini_plus_lidar.py models/best.pt
```

**ข้อสำคัญ:** ณ วันที่จัดคู่มือนี้ GitHub เดิม **ยังไม่มี `robot_teleop.py`**. ถ้าขาด โปรแกรมจะล้มด้วย `ModuleNotFoundError: No module named 'robot_teleop'` แม้ `py_compile` ของไฟล์อื่นผ่านก็ตาม ห้ามข้ามไฟล์นี้

## 3. คำสั่งสำหรับสมาชิกทีมที่ใช้ Raspberry Pi ตัวเดิม (แนะนำ)

บน Windows CMD / PowerShell:

```powershell
ssh pi@192.168.1.11
```

แทน IP ตาม IP Raspberry Pi ปัจจุบัน (อาจเปลี่ยนเมื่อเปลี่ยน Wi-Fi)

บน Pi:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
python --version
python -m py_compile robot_teleop.py robot_teleop_yolo_robot.py run_teleop_yolo_real.py dino_motion.py tmini_plus_lidar.py
python -c 'import torch, cv2, ultralytics, ydlidar; print("VISION + LIDAR IMPORT OK")'
python -c 'from ultralytics import YOLO; print(YOLO("models/best.pt").names)'
```

คาดว่าจะพบ `{0: 'green_dino'}`. ถ้า `.venv` ของ Pi เดิมทำงานอยู่แล้ว **ไม่ต้องติดตั้ง PyTorch หรือ YDLidar ใหม่**. ตรวจ `git status` ก่อน `git pull`; อย่า reset งานของเพื่อน

กรณีต้อง Clone ลงเครื่องใหม่จริง ๆ:

```bash
cd ~
git clone https://github.com/Gamaneeya/CatRobot-YOLO-Detector.git
cd ~/CatRobot-YOLO-Detector
sudo apt update
sudo apt install -y python3-venv python3-pip python3-dev git libgl1 libglib2.0-0 alsa-utils mpg123 v4l-utils
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**เครื่องใหม่ยังต้อง** ติดตั้งและตรวจ PyTorch/OpenCV ให้ตรงกับ OS/CPU และ YDLidar SDK (Python `ydlidar` + native shared library), ตั้งค่าอุปกรณ์ USB และเตรียม Yahboom ROS2 Docker/Motor Driver ให้ถูกก่อนใช้งานจริง ดูคู่มือ README.md เดิมในส่วนการติดตั้ง YDLidar SDK ได้ แต่ **อย่าใช้คำอธิบายเดิมที่ระบุว่าไม่ใช้ Docker กับโหมด Real ROS2 นี้**. Repository อย่างเดียว **ไม่ได้บรรจุ Docker image หรือ config ของบอร์ด** จึงไม่ใช่การติดตั้งหุ่นยนต์เครื่องใหม่แบบครบจบในคำสั่งเดียว

## 4. เช็กอุปกรณ์และ Docker (ยกล้อ / ตัดกำลังมอเตอร์ก่อน)

บน Pi:

```bash
ls -l /dev/video0 /dev/ttyUSB0 /dev/ttyUSB1
sudo ss -ltnp | grep ':8080' || echo 'PORT 8080 FREE'
sudo fuser -v /dev/video0 /dev/ttyUSB1
sudo docker ps -a
```

การต่อพอร์ต **ที่เคยตรวจพบในหุ่นยนต์ทีมนี้**: `/dev/video0` กล้อง, `/dev/ttyUSB1` LiDAR, `/dev/ttyUSB0` Motor Controller ใน Docker. **ตรวจจริงทุกครั้งเมื่อสลับสาย USB**. ไม่ควรมีโปรแกรมอื่นใช้กล้อง/ LiDAR ร่วมกัน

ถ้า Container `affectionate_lamport` เป็น `Exited` (และยืนยันว่าตั้งค่า driver-only ไว้แล้ว):

```bash
sudo docker start affectionate_lamport
sudo docker ps
```

หาก Docker มีชื่ออื่น ให้ตรวจและใช้ชื่อนั้นกับ `--container` ใน STEP 6. **ห้ามสร้าง Motor Driver ใหม่ทับ/ซ้อนตัวเดิม**. หากเห็นหลาย Container เช่น `unruffled_noyce` ให้ตรวจว่าไม่มี Driver อีกตัวใช้พอร์ตมอเตอร์:

```bash
sudo docker exec unruffled_noyce bash -lc 'ps -ef | grep -E "Mcnamu_driver_M1|yahboomcar_joy_launch" | grep -v grep || true'
```

คำสั่งด้านบนสำหรับ Container ที่มีชื่อนี้จริงเท่านั้น; ไม่ใช่คำสั่งให้หยุด Container นั้นโดยอัตโนมัติ

ตรวจ Startup ของ Container ที่เลือก:

```bash
sudo docker exec affectionate_lamport bash -lc 'cat /root/run_handle.sh'
```

**สำหรับหุ่นยนต์ทีมนี้** startup เคยตั้งเป็น `ROS_DOMAIN_ID=62 ROS_LOCALHOST_ONLY=1 ros2 run yahboomcar_bringup Mcnamu_driver_M1` (ภายในไฟล์มี `export ROS_DOMAIN_ID=61` ก่อนหน้า แต่คำสั่ง `ROS_DOMAIN_ID=62 ... ros2 run ...` จะ Override เฉพาะโปรเซส Driver). หากบนเครื่องใหม่ไม่ตรง ให้ผู้รับผิดชอบ ROS2 ตรวจและตั้งค่า **driver-only** ก่อน ไม่แก้ Docker แบบสุ่ม

## 5. ตรวจ ROS2 Topic โดยไม่สั่งให้ล้อ/Servo เคลื่อน

```bash
sudo docker exec affectionate_lamport bash -lc '
source /opt/ros/humble/setup.bash
source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash
export ROS_DOMAIN_ID=62
export ROS_LOCALHOST_ONLY=1
ros2 topic info /cmd_vel -v
ros2 topic info /Servo -v
ros2 topic info /Buzzer -v
ros2 interface show yahboomcar_msgs/msg/ServoControl
'
```

ผลที่คาดหวังเมื่อ **ยังไม่ได้เปิด** โปรแกรมหลัก:

- `/cmd_vel`: `geometry_msgs/msg/Twist`; **Publisher count: 0**; `Subscription count: 1` จาก `driver_node`
- `/Servo`: `yahboomcar_msgs/msg/ServoControl`; `Subscription count: 1`; fields `int32 s1`, `int32 s2` (ตรวจพบแล้วบนหุ่นยนต์ทีมนี้)
- `/Buzzer`: `std_msgs/msg/Bool`; มี Driver Subscriber อย่างน้อย 1

**อย่าสับสน:** หลังเปิดโปรแกรมหลัก `/cmd_vel` จะมี Publisher 1 ตัวจาก Bridge เป็นปกติ ถ้ามีมากกว่า 1 ให้หยุดการทดลองและตรวจโปรแกรมที่ซ้ำ

หาก `/cmd_vel` แสดง Unknown topic ทันทีหลัง Start ให้ตรวจ `sudo docker logs --tail 60 affectionate_lamport` และลองตรวจ Topic อีกครั้งหลัง Driver เริ่มพร้อม; ไม่ต้องแก้ YOLO

## 6. คำสั่งรันหุ่นยนต์จริง — ทดสอบยกล้อก่อนเสมอ

ตัดกำลังมอเตอร์ระหว่างเตรียมระบบ จากนั้น **ยกล้อพ้นพื้นทั้งหมดบนฐานมั่นคง**, จัดพื้นที่กล้อง/ Servo ให้ไม่ติดขอบ และให้คนหนึ่งคนคุมสวิตช์ตัดกำลัง เมื่อพร้อมจึงเปิดไฟเลี้ยงมอเตอร์เพื่อทดสอบ

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
sudo -v
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -u run_teleop_yolo_real.py \
  --mode wheels-up \
  --ros-domain-id 62 \
  --lidar-port /dev/ttyUSB1 \
  --confirm-wheels-up \
  --confirm-emergency-stop
```

หากชื่อ Container ต่างจาก `affectionate_lamport` เพิ่ม `--container <ชื่อที่ตรวจแล้ว>`; ถ้าใช้ Domain อื่นต้องตั้ง Domain ของ Motor Driver และ Bridge ให้ตรงกัน (ไม่ใช่เปลี่ยนเฉพาะฝั่ง Python)

เปิด Browser บน Windows ที่อยู่ Robot Wi-Fi เดียวกัน:

```text
http://192.168.1.11:8080
```

ถ้า Pi เปลี่ยน IP รัน `hostname -I` เพื่อตรวจ IP ใหม่ อย่าใช้ `http://localhost:8080` บน Windows เพราะจะชี้ไปยัง Windows ไม่ใช่ Pi

ตรวจ Log เริ่มทำงาน ตัวอย่าง **ไม่ใช่การรับรองล้อเคลื่อน**:

```text
[VISION] YOLO warm-up OK
[CAMERA] Existing YOLO camera loop will run in MAIN thread
[MOTOR] READY /cmd_vel subscribers=1
[SERVO] SERVO_READY fields=s1,s2
[WEB] Original teleop UI + real YOLO: http://192.168.1.11:8080
[TMINI] Scanning: /dev/ttyUSB1
```

## 7. ปุ่มควบคุมเดิม (ต้องให้ Browser รับ Focus)

| บนเว็บ/คีย์บอร์ด Windows | ความหมาย |
| --- | --- |
| คลิก **MANUAL** | เปิดรับคำสั่งเดินแบบ Manual |
| กดค้าง **W / A / S / D** | เดินหน้า / เลี้ยวซ้าย / ถอยหลัง / เลี้ยวขวา |
| ปล่อย WASD | ต้องหยุดเมื่อไม่กด; ตรวจบนล้อจริง |
| **Space** หรือปุ่ม **STOP** | กลับ STOPPED, สั่งความเร็ว 0 |
| **ลูกศร ← →** | Camera Servo S1 แพนซ้าย/ขวา |
| **ลูกศร ↑ ↓** | Camera Servo S2 เงย/ก้ม |
| **C** | กลับมุมอ้างอิง Servo S1=90°, S2=35° (ค่าอ้างอิงในโค้ดนี้) |
| **H ค้าง** / Horn บนเว็บ | Buzzer ของบอร์ด (หยุดเมื่อปล่อย) |
| **1–5** | Buzzer 5 Patterns เดิม |
| **M, 6–0** | เสียงแมวจาก Raspberry Pi USB Speaker |
| ปุ่ม **AUTO FOLLOW** | ให้ YOLO ตรวจ Dino แล้วส่งคำสั่งเลี้ยว/เดินหน้า ตาม LiDAR |

เสียงแมวกับ Buzzer เป็นคนละอุปกรณ์:
- **Meow** ผ่าน ALSA / USB Speaker โดย `robot_teleop.py` ออริจินัล; เครื่องทีมนี้พบ `plughw:2,0`, เครื่องอื่นอาจไม่ใช่หมายเลขเดียวกัน ตรวจ `aplay -l`
- **Buzzer** ผ่าน `/Buzzer` ใน Docker; `/Buzzer` ต้องมี Subscriber

Servo เริ่มจากมุม *สมมุติ* ที่ S1 90°, S2 35° (ตาม Docker Startup ที่เคยบันทึกไว้), ไม่ได้อ่านมุมปัจจุบันจริงจากเซนเซอร์ ควบคุมไว้ช่วง S1 **65–115°**, S2 **25–65°** ในการเริ่มทดลอง กล้องต้องไม่ชนโครงเมื่อกดลูกศรหรือ C

### ลำดับการทดสอบหุ่นยนต์จริง (ยกล้อ)

1. เปิดหน้าเว็บเห็นภาพสดและ Bounding Box รอบ Dino; ทดลองขยับตุ๊กตา
2. ตรวจ LiDAR แจ้งระยะถูกด้านด้วยการวางวัตถุจริงหน้า/ซ้าย/ขวาที่ระดับเลเซอร์
3. ทดสอบเสียงแมว (M, 6–0) และ Buzzer (H, 1–5) บนตัวหุ่นยนต์จริง
4. ทดสอบ Servo ทีละแกนด้วยลูกศรสั้น ๆ, กด C และดูการเคลื่อนจริง
5. MANUAL: กด W/A/S/D ทีละปุ่ม, ปล่อยแล้วล้อต้องหยุด, Space หยุดจริง
6. AUTO: เห็น Dino ซ้าย → หุ่นยนต์เลี้ยวซ้าย; กลาง → ขยับหน้า; ขวา → เลี้ยวขวา; Dino หาย → หยุด (ตรวจที่ล้อจริง ไม่ใช่แค่ข้อความ)
7. ตรวจ STOP เมื่อตัดการเชื่อมต่อ Browser/SSH, LiDAR ไม่พร้อม และ Motor Bridge ขาดการเชื่อมต่อ; หากล้อไม่หยุดจริงให้ตัดกำลังทันที

**ห้ามทดสอบบนพื้น** จนกว่าล้อและระบบหยุดฉุกเฉินทุกกรณีจะผ่าน, LiDAR คาลิเบรตด้านหน้า/ระยะหยุดตามขนาดหุ่นยนต์จริงแล้ว และมีผู้ควบคุมกำลังมอเตอร์อยู่ตลอด

## 8. คำสั่งหยุดระบบ

ขณะอยู่หน้าเว็บให้กด **STOP** และดูว่าล้อหยุดจริงก่อน จากนั้นตัดกำลังมอเตอร์ แล้วกด `Ctrl+C` ใน Terminal ที่เปิดโปรแกรม

```bash
sudo ss -ltnp | grep ':8080' || echo 'PORT 8080 FREE'
```

**หาก SSH หลุด:** เชื่อมกลับแล้วตรวจ `sudo ss -ltnp | grep ':8080'` และตรวจว่าล้อหยุดจริง; อย่าถือว่าข้อความ `client_loop: send disconnect: Connection reset` ยืนยันโปรแกรมหยุดเองแล้ว

## 9. แก้ปัญหาเบื้องต้น

| อาการ | ตรวจก่อน |
| --- | --- |
| `No module named robot_teleop` | ยังไม่ได้ใส่ `robot_teleop.py` ออริจินัลไว้ข้างไฟล์เริ่มระบบ |
| `Port 8080 is busy` | มีโปรแกรม CatRobot เก่าเปิด Web Server อยู่, ห้ามเปิดสองตัว |
| `/cmd_vel Unknown topic` | Docker/Driver ยังไม่พร้อม หรือ Domain 62 ไม่ตรง |
| `ERROR OTHER_CMD_VEL_PUBLISHERS` | มีโปรแกรมอีกตัวสั่งล้อใน Domain เดียวกัน; ห้ามข้ามการตรวจนี้ |
| `LIDAR NOT READY`, `INSUFFICIENT`, `STALE` | เช็ก `/dev/ttyUSB1`, สาย, SDK, ทิศติดตั้ง และสิ่งกีดขวาง ห้าม bypass |
| เสียงแมวไม่ออก | `aplay -l`; สาย USB Speaker; mixer; device ที่เลือก |
| Buzzer ไม่ออก | ตรวจ `/Buzzer` subscriber และเสียงจริงบนบอร์ด |
| Servo ไม่หมุน | ตรวจ `/Servo` subscriber, `int32 s1/s2`, Servo power และมุมทดสอบ |
| ภาพค้าง | ตรวจโปรแกรมกล้องตัวอื่น, `/dev/video0`, PyTorch threads; ห้ามเปิด `dino_live.py` ซ้อน |
| Log `v=...` แต่ล้อไม่หมุน | ตรวจ Motor Driver/ไฟเลี้ยง/ล้อจริง ไม่ถือว่า Log แปลว่าล้อเคลื่อน |

## 10. สถานะ ณ วันที่ส่งต่อ (จาก Log ที่ทีมมี)

**ยืนยันจาก Log:** YOLO warm-up, LiDAR scanning, ROS2 `/cmd_vel` subscriber, `/Servo` subscriber และคำสั่ง Servo, AUTO/MANUAL คำสั่งความเร็ว, audio playback บน USB Speaker; มีการสั่ง STOPED/STOP และ Motor velocity = 0

**ยังต้องยืนยันจากฮาร์ดแวร์ก่อนเรียกว่า Fully Validated:** ล้อหมุนและหยุดจริงทุกโหมด, Servo ขยับตามแกนถูกต้องและไม่ชนโครง, Buzzer/Meow ดังครบทุกปุ่ม, fail-safe เมื่อ Bridge/SSH หลุด และการวิ่งบนพื้นโดยไม่มีการชน

โปรแกรมมีความเร็วจริงที่ส่งผ่าน Bridge จำกัดประมาณ ±0.055 m/s และ ±0.19 rad/s ในโหมดทดลอง (ตามโค้ด) ไม่ใช่ความเร็วสูงสุดของหุ่นยนต์; การหยุดเมื่อเข้าใกล้ Dino ใช้ขนาด Bounding Box เป็นเพียงตัวช่วย ไม่ใช่การวัดระยะจริง และ LiDAR ยังต้องคาลิเบรตทิศและระยะหยุด

---

## 11. หมายเหตุสำหรับผู้ดูแล GitHub

`README.md` เดิมใน GitHub บอกว่า "ไม่ใช้ Docker" ซึ่ง **ไม่ถูกต้องสำหรับโหมด Real ROS2 นี้**. แนะนำให้เพิ่มข้อความที่ส่วนต้น README หลักว่า:

> **Real hardware mode:** Use [`README_REAL_ROBOT_TH.md`](README_REAL_ROBOT_TH.md). This mode uses an existing Yahboom ROS2 Docker driver-only container (Domain 62), rather than the direct `Rosmaster_Lib` motor backend. Do not run both drivers at the same time.

อย่าอัปโหลด `.venv/`, `__pycache__/`, cache, ไฟล์ backup, log, ข้อมูลส่วนตัว หรือ credentials. `models/best.pt` ที่มีใน Repository อยู่แล้วให้ใช้ต่อ ไม่ต้องอัปโหลดซ้ำหากไฟล์ยังตรงรุ่น
