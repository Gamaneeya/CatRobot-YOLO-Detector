# CatRobot YOLO V7 Detector

Custom **YOLO11n object detection model** trained to detect a small green dinosaur plush toy for the **Interactive Cat Robot using ROSMASTER M1** project.

> **Version note:** V7 is our seventh custom-trained version of **YOLO11n**, not the separate YOLOv7 architecture.

**Current Model:** Custom YOLO11n V7  
**Detection Class:** `green_dino` (Class ID: `0`)  
**Model File:** `models/best.pt`  
**Recommended Confidence Threshold:** `0.60`  
**Input Image Size:** `640 × 640`  
**Development Status:** V7 selected as the integration candidate; real Raspberry Pi / ROS 2 testing is pending.

This repository contains trained model weights and inference code for deployment. Training datasets and experimental scripts are not required on the robot.

## 1. Project Structure

```text
CatRobot-YOLO-Detector/
├── models/
│   └── best.pt
├── toy_detector.py
├── test_video.py
├── ros2_toy_detector_node.py
├── requirements.txt
├── README.md
└── .gitignore
```

| File | Description |
|---|---|
| `models/best.pt` | Custom YOLO11n V7 model weights |
| `toy_detector.py` | Loads the model and returns detection results |
| `test_video.py` | Tests detection using a local video |
| `ros2_toy_detector_node.py` | ROS 2 node that receives camera frames and publishes detections |
| `requirements.txt` | Python inference dependencies |
| `README.md` | Setup, evaluation, and integration instructions |

## 2. Test on Windows (Developer)

### 2.1 Clone or update the repository

```powershell
git clone https://github.com/Gamaneeya/CatRobot-YOLO-Detector.git
cd CatRobot-YOLO-Detector
```

If already cloned, check for local changes before pulling:

```powershell
git status
git pull --ff-only origin main
```

### 2.2 Create a virtual environment

```powershell
py -m venv .venv
```

### 2.3 Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2.4 Verify that the model loads

```powershell
.\.venv\Scripts\python.exe -c "from toy_detector import ToyDetector; d=ToyDetector(); print('YOLO V7 loaded successfully')"
```

Expected output: `YOLO V7 loaded successfully`.

This verifies that the weight file can load, not its accuracy or version. Before committing this release, ensure that `models/best.pt` was copied from `runs/green_dino_v7/weights/best.pt`.

### 2.5 Test with a video

```powershell
.\.venv\Scripts\python.exe test_video.py --video "C:\path\to\test.mp4" --conf 0.60 --stride 5
```

Replace the example file with an existing video. Options:

- `--conf 0.60`: recommended confidence threshold
- `--stride 5`: process every fifth frame; `--stride 1` processes every frame

Example terminal output:

```text
frame=1 detected=True confidence=0.920 x=0.48 y=0.53
```

The script prints detections but does not show annotated video. For V7 deployment, `toy_detector.py` and `test_video.py` should default to `0.60`.

## 3. Raspberry Pi 5 and ROS 2 Humble Setup

**Target platform:** ROSMASTER M1; Raspberry Pi 5; ROS 2 Humble; Docker; team ROS Domain ID `13`.

Reuse the team's existing ROS 2 Docker environment. Do not reinstall ROS 2 or replace working robot containers without coordination.

### 3.1 Connect to the robot

Power on the robot following the team procedure, with the computer and robot on the same network:

```bash
ssh pi@ROBOT_IP
```

Replace `ROBOT_IP` with the robot's address.

### 3.2 Check the Docker environment

On the Raspberry Pi host:

```bash
docker ps
```

Enter the existing ROS 2 Humble container:

```bash
docker exec -it CONTAINER_NAME /bin/bash
```

Replace `CONTAINER_NAME` with its actual name. If the container is stopped, follow the team's existing Yahboom startup procedure. Avoid launching duplicate control containers.

### 3.3 Configure ROS 2

Inside Docker:

```bash
source /opt/ros/humble/setup.bash
echo $ROS_DISTRO
echo $ROS_DOMAIN_ID
python3 --version
```

Expected distribution: `humble`. The team uses ROS Domain ID `13`:

```bash
export ROS_DOMAIN_ID=13
```

All communicating ROS nodes must use the same domain ID.

### 3.4 Clone or update the repository

The code must be accessible inside the ROS 2 container. Inspect persistent mounts from the Pi host:

```bash
docker inspect CONTAINER_NAME --format '{{json .Mounts}}'
```

Clone into a suitable shared directory if needed:

```bash
git clone https://github.com/Gamaneeya/CatRobot-YOLO-Detector.git
```

For an existing clone, check for local changes, then run:

```bash
git pull --ff-only origin main
```

Enter the actual repository directory inside Docker. **Example only:**

```bash
cd /root/yahboomcar_ws/CatRobot-YOLO-Detector
```

Do not assume this path exists on the robot.

### 3.5 Check dependencies

Inside the ROS 2 Docker container:

```bash
uname -m
python3 --version
python3 -c "import torch; print(torch.__version__)"
python3 -c "import cv2; print(cv2.__version__)"
python3 -c "from cv_bridge import CvBridge; print('cv_bridge OK')"
python3 -c "from ultralytics import YOLO; print('YOLO OK')"
```

If dependencies are missing, verify ARM64 and the container Python version before installation. Missing ROS image dependencies may require:

```bash
apt update
apt install -y ros-humble-cv-bridge python3-opencv python3-numpy
```

**Do not blindly replace NumPy, OpenCV, or PyTorch** in the team's existing container. Dependencies and inference on the actual Raspberry Pi have not yet been verified.

## 4. Verify YOLO V7 on Raspberry Pi

Before using the camera, check that the model loads inside the ROS 2 container:

```bash
python3 -c "from toy_detector import ToyDetector; d=ToyDetector(); print('YOLO V7 loaded successfully')"
```

Expected output: `YOLO V7 loaded successfully`.

If a recorded video is available in the container:

```bash
python3 test_video.py --video /path/to/test.mp4 --conf 0.60 --stride 5
```

Model loading and runtime inference speed still need verification on the actual Raspberry Pi. Offline Windows timing is not a Raspberry Pi benchmark.

## 5. Find the ROS 2 Camera Topic

Ensure that the camera driver is running. Inside Docker:

```bash
ros2 node list
ros2 topic list -t
```

Look for `sensor_msgs/msg/Image` or `sensor_msgs/msg/CompressedImage`, then check the selected topic:

```bash
ros2 topic info /ACTUAL_CAMERA_TOPIC
ros2 topic hz /ACTUAL_CAMERA_TOPIC
```

The default topic configured in the detection node is `/camera/image_raw`, but this has **not** been confirmed as the correct ROSMASTER M1 camera topic. Replace placeholders with the actual topics.

## 6. Run the ROS 2 YOLO Detector

The ROS 2 node should default to `confidence = 0.60`. The commands below also pass the setting explicitly.

### 6.1 Standard image topic

```bash
python3 ros2_toy_detector_node.py --ros-args -p image_topic:=/ACTUAL_CAMERA_TOPIC -p confidence:=0.60
```

### 6.2 Compressed image topic

If the camera publishes `sensor_msgs/msg/CompressedImage`:

```bash
python3 ros2_toy_detector_node.py --ros-args -p image_topic:=/ACTUAL_COMPRESSED_TOPIC -p compressed:=true -p confidence:=0.60
```

### 6.3 Verify detection output

Open a second SSH terminal, enter the same ROS 2 Docker environment, and run:

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=13
ros2 topic echo /toy_detection
```

The detector publishes JSON encoded in `std_msgs/msg/String`. **This detector publishes no motor movement commands.** A separate controller handles movement and safety.

## 7. Detection Output Format

Example JSON payload:

```json
{
  "status": "detected",
  "detected": true,
  "confidence": 0.92,
  "center_x": 0.48,
  "center_y": 0.53,
  "bbox": [100.0, 80.0, 230.0, 250.0]
}
```

| Field | Description |
|---|---|
| `status` | Detection or error state |
| `detected` | Whether a toy detection is available |
| `confidence` | Model confidence score |
| `center_x` | Normalized horizontal center coordinate (0–1) |
| `center_y` | Normalized vertical center coordinate (0–1) |
| `bbox` | Pixel bounding box `[x1, y1, x2, y2]` |

Possible statuses: `detected`, `no_detection`, `no_camera_frame`, `stale_camera_frame`, and `inference_error`.

For `no_detection`, coordinates and `bbox` are `null`. Camera or inference errors may provide only `status` and `detected`.

**Integration note:** The controller should use coordinates only when detection information is valid, recent, and stable. Do not authorize movement from a single unverified detection.

## 8. Model Training and Evaluation

### 8.1 Current model and dataset

Custom **YOLO11n V7** was fine-tuned from V6 using **128 additional positive training images** selected from robot-camera footage, particularly difficult frontal silhouettes and moving/blurred views.

The V7 dataset contains **660 images**:

| Split | Images | Positive | Negative / Null |
|---|---:|---:|---:|
| Train | 520 | 385 | 135 |
| Validation | 133 | 129 | 4 |
| Test | 7 | 7 | 0 |
| **Total** | **660** | **521** | **139** |

All 532 V6 images were retained in their original splits; the 128 added images went into **Train**. Negative/null images teach the detector not to recognize certain backgrounds and objects as the green dinosaur.

### 8.2 Validation performance

Metrics for the **133-image validation split**:

| Metric | V6 (reference) | V7 (selected) |
|---|---:|---:|
| Precision | 96.80% | **96.85%** |
| Recall | **96.10%** | 95.18% |
| mAP@50 | 95.50% | **95.61%** |
| mAP@50–95 | **80.50%** | 78.80% |

V7 was selected for its **robot-camera behavior and the desired false-positive trade-off**, not because it won on every validation metric. Validation metrics alone do not demonstrate real-world false-positive rates or Raspberry Pi speed.

### 8.3 Robot-camera video tests (confidence = 0.60)

The following offline comparisons used matching inference settings:

| Video | Scene / interpretation | V6 | V7 |
|---|---|---:|---:|
| `robot_video_03.mp4` | Positive/mixed; frames with detection | 775 / 1,373 | **831 / 1,373** |
| `robot_video_04.mp4` | Positive/mixed; frames with detection | 196 / 592 | **204 / 592** |
| `IMG_0228.MOV` | No dinosaur; false-positive frames | 55 / 254 | **6 / 254** |
| `IMG_0521.MOV` | No dinosaur; false-positive frames | 19 / 1,898 | **16 / 1,898** |

V7 detected more frames in the robot-camera recordings and fewer false-positive frames in these recorded negatives than V6. Previous visual review confirmed that the examined V7-only detections in `robot_video_03` correctly localized the dinosaur.

**Evaluation limitations:**

- A detected-frame rate in positive/mixed videos is **not recall**; the dinosaur may not appear in every frame.
- `IMG_0521` contributed images to earlier training, and `IMG_0228` later contributed hard-negative examples when developing V8. These recordings should be treated as **regression checks**, not independent measurements of generalization.
- Evaluate the selected V7 model with **new, never-trained positive and negative recordings** before using it for autonomous tracking.

### 8.4 Why V7 was selected instead of V8

V8 was fine-tuned after adding approximately **10 hard-negative images**. It detected more frames in the recorded positive/mixed videos, but also introduced new false positives in `IMG_0228` that V7 did not produce. At confidence `0.60`:

| Video | V7 | V8 |
|---|---:|---:|
| `IMG_0228.MOV` (negative; FP frames) | **6** | 15 |
| `IMG_0521.MOV` (negative; FP frames) | 16 | **14** |
| `robot_video_03.mp4` (frames with detection) | 831 | **884** |
| `robot_video_04.mp4` (frames with detection) | 204 | **219** |

V7 was selected as the **more conservative integration candidate** under the current evidence. V8 is retained as an experimental model outside this deployment repository. The choice should be reviewed again after new independent tests.

### 8.5 Historical negative-training result

An earlier V4-to-V5 comparison on the negative `IMG_0521.MOV` recording gave:

| Metric | V4 | V5 |
|---|---:|---:|
| Total frames | 1,898 | 1,898 |
| False-positive frames | 332 | 127 |
| False-positive frame rate | 17.49% | 6.69% |

This represented approximately a **61.7% relative reduction** in FP frames for V5 versus V4 on that recording. It is **not a V7 performance figure**, and the recording is no longer independent of later training.

## 9. Known Model Limitations

- **Frontal views:** Narrow/oval silhouettes can still cause missed detections despite V7 improvements.
- **Fast motion:** Motion blur and orientation changes may cause intermittent missed detections.
- **False positives:** Green cloth, similar colors, and unfamiliar backgrounds may be falsely recognized as the dinosaur.
- **Confidence:** A detection confidence of `0.60` or above does not guarantee correctness.
- **Dataset/video overlap:** Some video frames have been used during training across model iterations. Use unseen videos for independent evaluation.
- **Raspberry Pi performance:** Live inference FPS, CPU load, and memory consumption have not yet been measured.
- **ROS 2 integration:** The camera-to-detection pipeline has not yet been verified in the team's actual Docker environment.

## 10. Robot Safety Warnings

### 10.1 Physical safety

- Place the robot on a secure stand with wheels off the ground during initial movement tests.
- Maintain at least 2 meters of clear space during floor tests.
- Keep hands, hair, and cables away from moving components and LiDAR.
- Do not manually rotate the powered camera head.

### 10.2 Detection and movement safety

**The YOLO detector does not directly control the robot's motors.** A separate movement controller must:

- Stop when detection data is missing, invalid, or outdated.
- Implement a watchdog timeout and publish zero velocity when tracking is unsafe.
- Avoid moving based on a single unverified detection.
- Handle temporary detection gaps conservatively.
- Keep LiDAR obstacle avoidance independent of the toy detector.
- Provide an emergency stopping mechanism independent of detection.

The robot may retain the last motor-speed command until a new one is received. **Stopping the detection node alone does not guarantee that the robot stops.**

### 10.3 Emergency stop

If the robot behaves unexpectedly, use the team's physical emergency stop procedure. If software control is still available, stop the controller and publish zero velocity from a working ROS environment:

```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" -r 10 --times 20
```

Switch off main power if movement cannot be stopped safely. Confirm `/cmd_vel` is the correct velocity topic in the team's configuration.

### 10.4 Battery safety

Check battery voltage using the team's procedure. The original robot instructions specify:

```bash
ros2 topic echo /voltage
```

For the configuration in those instructions, the minimum operating voltage is **10.3 V**. Use the supplied charger and do not leave charging unattended.

### 10.5 ROS Domain safety

The team's ROS Domain ID is `13`; confirm that all relevant nodes use the intended domain to avoid interference with other robots.

## 11. Troubleshooting

| Problem | What to check |
|---|---|
| `best.pt` not found | Confirm `models/best.pt` exists |
| `No module named ultralytics` | Check the active Python environment |
| `No module named rclpy` | Use the correct ROS 2 environment |
| `No module named cv_bridge` | Check the ROS Humble image-bridge package |
| No camera frames | Check camera driver, topic, message type, and ROS Domain ID |
| `/toy_detection` does not appear | Check node execution and ROS communication |
| Low inference speed | Measure Raspberry Pi CPU and memory usage |
| False positives | Inspect green/background objects and the confidence threshold |
| Frontal-view misses | Check silhouette, orientation, and image quality |
| Misses during motion | Check motion blur and temporary tracking loss |
| Model updated but behavior unchanged | Confirm V7 `best.pt` was committed, pull changes, and restart the node |

## 12. Integration Status

| Component | Status |
|---|---|
| YOLO V7 training | **Completed** |
| Windows offline inference and recorded-video comparisons | **Completed** |
| V7 selected as integration candidate | **Completed** |
| Confidence threshold `0.60` | **Configured as V7 release default** |
| Raspberry Pi model loading | Not yet verified |
| Live ROS 2 camera integration | Not yet verified |
| `/toy_detection` publishing on Raspberry Pi | Not yet verified |
| New, fully unseen positive/negative video safety testing | Recommended |
| Autonomous robot movement | Not included in this repository |

**Recommended first integration test:** Load V7, receive real camera frames, and inspect `/toy_detection` output **without enabling autonomous movement**. Then verify that the separate controller stops safely when detections are missing or stale.

## References

- [Ultralytics Documentation](https://docs.ultralytics.com/)
- [Ultralytics Raspberry Pi Guide](https://docs.ultralytics.com/guides/raspberry-pi/)
- [ROS 2 Humble Documentation](https://docs.ros.org/en/humble/)
- [Yahboom ROSMASTER M1](https://www.yahboom.net/study/ROSMASTER-M1/16900)
