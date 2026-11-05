
from pathlib import Path


ROOT = Path(__file__).resolve().parent
README = ROOT / "README.md"
TODO = ROOT / "docs" / "FRIEND_TODO_TH.md"


def update_readme():
    content = README.read_text(encoding="utf-8")

    content = content.replace(
        "Planned real-motor integration; not yet included in the verified release",
        "Real-motor controller with safety locks; hardware validation pending"
    )

    content = content.replace(
        "| LiDAR obstacle detection | Not yet integrated |",
        "| LiDAR obstacle detection | Experimental T-MINI Plus integration added; Pi validation pending |"
    )

    extra = """
## Experimental T-MINI Plus LiDAR Integration

The repository now includes an experimental Python integration
for YDLIDAR T-MINI Plus.

New files:

- `tmini_plus_lidar.py` - Official SDK reader and conservative scan checking
- `robot_teleop_yolo_lidar.py` - Entry point for scan, motor, and supervised AUTO tests
- `tests/test_tmini_plus_lidar.py` - Safety logic unit tests
- `docs/TMINI_PLUS_SETUP_TH.md` - Full teammate setup and test instructions

Start with the guide:

**[T-MINI Plus LiDAR Setup](docs/TMINI_PLUS_SETUP_TH.md)**

The original `robot_teleop_yolo_robot.py` is retained.
The LiDAR-aware entry point connects to it without requiring Docker or ROS2.

Modes:

```bash
python robot_teleop_yolo_lidar.py --mode scan-only --port /dev/ttyUSB0 --front-angle 0
```

```bash
python robot_teleop_yolo_lidar.py --mode manual-wheels-up --confirm-wheels-up
```

The last mode, `auto-supervised`, requires calibrated orientation,
verified stopping, physical supervision, and additional command-line confirmations.

**This is experimental integration, not an autonomous safety certification.**
The LiDAR is 2D and may miss low objects, including the dinosaur toy.
Physical emergency stopping and supervised testing remain mandatory.

"""

    marker = "## Real Robot Auto Follow"

    if (
        "## Experimental T-MINI Plus LiDAR Integration"
        not in content
    ):
        if marker in content:
            content = content.replace(
                marker,
                extra + marker,
                1
            )
        else:
            content += "\n" + extra

    README.write_text(
        content,
        encoding="utf-8"
    )

    print("UPDATED:", README)


def update_todo():
    content = TODO.read_text(encoding="utf-8")

    content = content.replace(
        "ไฟล์ `robot_teleop_yolo_robot.py` จะต้องมีเพิ่มเติมก่อนเริ่มทดสอบมอเตอร์ผ่านโปรแกรม YOLO จริง",
        "ไฟล์ `robot_teleop_yolo_robot.py` มีอยู่ใน Repository แล้ว แต่ยังไม่ได้รับการยืนยันการทำงานบนฮาร์ดแวร์จริง"
    )

    content = content.replace(
        "ถ้าไม่มีไฟล์นี้ **ทำได้ถึง Dry Run เท่านั้น** ห้ามใช้ Dry Run แทนไฟล์มอเตอร์จริง",
        "การทดสอบมอเตอร์และ LiDAR ต้องทำตาม `docs/TMINI_PLUS_SETUP_TH.md` ก่อน และห้ามใช้ Dry Run แทนไฟล์มอเตอร์จริง"
    )

    content = content.replace(
        "หากยังไม่มี ให้หยุดที่ PHASE 6 และรายงานว่า `REAL ROBOT FILE NOT READY`",
        "ไฟล์ Robot มีอยู่แล้ว แต่ยังต้องตรวจ Motor Library, Motor Direction และระบบหยุดตามคู่มือ T-MINI Plus ก่อน"
    )

    content = content.replace(
        "ls -l /dev/rplidar",
        "ls -l /dev/serial/by-id/"
    )

    notice = """
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

"""

    marker = "# PHASE 0 — ก่อนเริ่ม"

    if "> **UPDATE — T-MINI Plus LiDAR**" not in content:
        if marker in content:
            content = content.replace(
                marker,
                notice + marker,
                1
            )
        else:
            content = notice + content

    TODO.write_text(
        content,
        encoding="utf-8"
    )

    print("UPDATED:", TODO)


if __name__ == "__main__":
    if not README.is_file():
        raise FileNotFoundError(README)

    if not TODO.is_file():
        raise FileNotFoundError(TODO)

    update_readme()
    update_todo()

    print("README AND TODO UPDATE COMPLETE")
