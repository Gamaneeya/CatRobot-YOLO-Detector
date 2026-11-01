# CatRobot YOLO V6 Detector

Custom **YOLO11n object detection model** trained to detect a small green dinosaur plush toy for the **Interactive Cat Robot using ROSMASTER M1** project.

**Current Model:** YOLO V6  
**Detection Class:** `green_dino` (Class ID: 0)  
**Model File:** `models/best.pt`  
**Development Status:** V6 integration candidate; V7 under development.

This repository contains the trained model and inference code only. Training datasets, training scripts, and experiment files are not required for deployment.

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
| `models/best.pt` | YOLO V6 trained model |
| `toy_detector.py` | Loads the model and returns detection results |
| `test_video.py` | Tests detection using a local video |
| `ros2_toy_detector_node.py` | ROS 2 node that receives camera images and publishes detection results |
| `requirements.txt` | Python inference dependencies |
| `README.md` | Setup and integration instructions |

## 2. Test on Windows (Developer)

### 2.1 Clone the repository

```powershell
git clone https://github.com/YOUR_USERNAME/CatRobot-YOLO-Detector.git
cd CatRobot-YOLO-Detector
```

Replace `YOUR_USERNAME` with the repository owner's GitHub username.

If the repository is already cloned, use `git pull` after checking for local uncommitted changes.

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
.\.venv\Scripts\python.exe -c "from toy_detector import ToyDetector; d=ToyDetector(); print('YOLO V6 loaded successfully')"
```

Expected output:

```text
YOLO V6 loaded successfully
```

This verifies that the model can be loaded. It does not verify detection accuracy.

### 2.5 Test with a video

```powershell
.\.venv\Scripts\python.exe test_video.py --video "C:\path\to\test.mp4" --stride 5
```

Replace the example video path with an existing video.

Optional parameters:

- `--conf 0.5`: minimum detection confidence
- `--stride 5`: process every fifth frame

Example output:

```text
frame=1 detected=True confidence=0.920 x=0.48 y=0.53
```

The script prints detection results to the terminal. It does not display an annotated video window.

## 3. Raspberry Pi 5 and ROS 2 Humble Setup

**Target platform**

- Robot: ROSMASTER M1
- Computer: Raspberry Pi 5
- ROS: ROS 2 Humble
- Environment: Docker
- Team ROS Domain ID: `13`

Use the robot's existing ROS 2 Docker environment. Do not reinstall ROS 2 or replace existing containers unless necessary.

### 3.1 Connect to the robot

Power on the robot using the team's startup procedure.

Connect the development computer and robot to the same network.

```bash
ssh pi@ROBOT_IP
```

Replace `ROBOT_IP` with the robot's current IP address.

### 3.2 Check the Docker environment

On the Raspberry Pi host:

```bash
docker ps
```

Identify the existing ROS 2 Humble container.

To enter an already-running container:

```bash
docker exec -it CONTAINER_NAME /bin/bash
```

Replace `CONTAINER_NAME` with the actual container name.

If the container is not running, follow the team's existing Yahboom Docker startup instructions.

**Important:** Do not launch duplicate robot control containers unnecessarily.

### 3.3 Configure ROS 2

Inside Docker:

```bash
source /opt/ros/humble/setup.bash
echo $ROS_DISTRO
echo $ROS_DOMAIN_ID
python3 --version
```

Expected ROS distribution:

```text
humble
```

The team's assigned ROS Domain ID is `13`.

Ensure all communicating ROS nodes use the same domain ID. Where appropriate:

```bash
export ROS_DOMAIN_ID=13
```

Do not change only one side of the ROS network without checking other nodes.

### 3.4 Clone or update the repository

The repository must be accessible from inside the ROS 2 Docker container.

On the Raspberry Pi host, inspect the container's mounted directories:

```bash
docker inspect CONTAINER_NAME --format '{{json .Mounts}}'
```

Choose a persistent shared directory.

For a new installation:

```bash
git clone https://github.com/YOUR_USERNAME/CatRobot-YOLO-Detector.git
```

For an existing clone, after checking local changes:

```bash
git pull --ff-only origin main
```

Enter the actual project directory inside Docker.

Example only:

```bash
cd /root/yahboomcar_ws/CatRobot-YOLO-Detector
```

The path must be verified on the robot. Do not assume this example path is correct.

### 3.5 Check Python dependencies

Inside the ROS 2 Docker container:

```bash
uname -m
python3 --version
python3 -c "import torch; print(torch.__version__)"
python3 -c "import cv2; print(cv2.__version__)"
python3 -c "from cv_bridge import CvBridge; print('cv_bridge OK')"
python3 -c "from ultralytics import YOLO; print('YOLO OK')"
```

If all imports succeed, continue to Section 4.

If dependencies are missing, verify compatibility with the container's Python version and ARM64 architecture before installation.

For missing ROS image-conversion dependencies, the following packages may be needed:

```bash
apt update
apt install -y ros-humble-cv-bridge python3-opencv python3-numpy
```

**Do not blindly replace the existing NumPy, OpenCV, or PyTorch installation.** This could break ROS image conversion or other robot applications.

Installation of the project's Python requirements inside the team's Raspberry Pi Docker environment has not yet been verified.

## 4. Verify YOLO V6 on Raspberry Pi

Before connecting the camera, test whether the model loads.

From the repository directory inside Docker:

```bash
python3 -c "from toy_detector import ToyDetector; d=ToyDetector(); print('YOLO V6 loaded successfully')"
```

Expected output:

```text
YOLO V6 loaded successfully
```

This confirms that the model can be loaded through the available Python environment.

If a video file is accessible inside the container:

```bash
python3 test_video.py --video /path/to/test.mp4 --stride 5
```

Replace the path with an existing video.

Model-loading and inference performance on the Raspberry Pi must be verified on the actual device.

## 5. Find the ROS 2 Camera Topic

Ensure the camera driver is running.

Inside Docker:

```bash
ros2 node list
ros2 topic list -t
```

Look for an image topic using one of these message types:

- `sensor_msgs/msg/Image`
- `sensor_msgs/msg/CompressedImage`

Check the selected topic:

```bash
ros2 topic info /ACTUAL_CAMERA_TOPIC
ros2 topic hz /ACTUAL_CAMERA_TOPIC
```

Replace `/ACTUAL_CAMERA_TOPIC` with the actual discovered topic.

The detector's default camera topic is `/camera/image_raw`, but this has not yet been confirmed as the correct topic for the team's ROSMASTER M1.

## 6. Run the ROS 2 YOLO Detector

### 6.1 Standard image topic

```bash
python3 ros2_toy_detector_node.py --ros-args -p image_topic:=/ACTUAL_CAMERA_TOPIC
```

### 6.2 Compressed image topic

If the camera publishes `sensor_msgs/msg/CompressedImage`:

```bash
python3 ros2_toy_detector_node.py --ros-args -p image_topic:=/ACTUAL_COMPRESSED_TOPIC -p compressed:=true
```

Replace the placeholders with the actual topic names.

### 6.3 Verify detection output

Open a second SSH terminal, enter the same ROS 2 Docker environment, and run:

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=13
ros2 topic echo /toy_detection
```

The detector publishes JSON text inside a `std_msgs/msg/String` message.

**The detector does not publish motor movement commands.** Movement control must be handled by a separate ROS 2 controller.

## 7. Detection Output Format

Example JSON content:

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
| `status` | Current detection status |
| `detected` | Whether a detection is available |
| `confidence` | Model confidence score |
| `center_x` | Normalized horizontal center coordinate (0–1) |
| `center_y` | Normalized vertical center coordinate (0–1) |
| `bbox` | Bounding box `[x1, y1, x2, y2]` in pixels |

Possible status values:

- `detected`
- `no_detection`
- `no_camera_frame`
- `stale_camera_frame`
- `inference_error`

For a normal `no_detection` result, `center_x`, `center_y`, and `bbox` are `null`. Error statuses may contain only the status and detected fields.

**Integration note:** The robot controller should consume detection coordinates only when `detected` is true and the information is recent and valid.

## 8. Model Training and Evaluation

### 8.1 Current model

**YOLO V6 (YOLO11n)** was fine-tuned from V5 using images with and without the green dinosaur toy.

The V6 dataset contains **532 images**:

| Split | Images | Positive | Negative / Null |
|---|---:|---:|---:|
| Train | 392 | 257 | 135 |
| Validation | 133 | 129 | 4 |
| Test | 7 | 7 | 0 |
| **Total** | **532** | **393** | **139** |

Negative images are used to help the model learn that similar-looking backgrounds and objects are not the target toy.

### 8.2 Validation performance

Results from V6 `best.pt` on the 133-image validation set:

| Metric | Result |
|---|---:|
| Precision | 96.8% |
| Recall | 96.1% |
| mAP@50 | 95.5% |
| mAP@50–95 | 80.5% |

These metrics describe performance on the validation dataset. They do not independently establish real-world false positive rates or Raspberry Pi inference performance.

### 8.3 Previous improvement from negative training

In an earlier comparison using **V4 and V5**, the models were tested on `IMG_0521.MOV`, a video containing no dinosaur:

| Metric | V4 | V5 |
|---|---:|---:|
| Total frames | 1,898 | 1,898 |
| False positive frames | 332 | 127 |
| False positive frame rate | 17.49% | 6.69% |

V5 reduced false-positive frames by approximately **61.7% relative to V4** on this video.

This is a historical V4-to-V5 result, **not a measured V6 false-positive rate**. Frames from this video were subsequently added to V6 training, so it is no longer an independent test for V6.

### 8.4 Testing on robot-camera recordings

V6 has undergone preliminary offline visual testing using additional recorded footage from the ROSMASTER M1 camera. Initial observations were encouraging.

However, testing a recorded robot video on a Windows computer is not equivalent to running the detector live in the robot's ROS 2 environment.

## 9. Known Model Limitations

- **Frontal view false negatives:** The dinosaur may be missed when facing the camera directly because its silhouette becomes narrow or oval-shaped.
- **Fast movement:** Motion blur or rapid orientation changes can cause intermittent missed detections.
- **False positives:** Unfamiliar backgrounds or objects may still be incorrectly detected as the dinosaur.
- **Confidence scores:** High confidence does not guarantee that a detection is correct.
- **Dataset overlap:** Some previously reviewed videos include frames related to training or validation data.
- **Hardware performance:** Live inference speed and resource usage on Raspberry Pi 5 have not yet been confirmed.
- **ROS 2 deployment:** The full camera-to-detection pipeline must still be verified in the team's actual Docker environment.

### Planned V7 improvement

V7 is under development to address missed detections during frontal views and fast movement.

The planned training improvements emphasize hard-positive examples from robot-camera footage, especially frames showing frontal silhouettes and motion blur.

**V7 is not the deployed model in this repository unless `models/best.pt` is explicitly updated and tested.**

## 10. Robot Safety Warnings

### 10.1 Physical safety

- Place the robot securely on a stand with its wheels off the ground for initial movement tests.
- Maintain at least 2 meters of clear space during floor testing.
- Keep hands, hair, and cables away from moving components and LiDAR.
- Do not manually rotate the powered camera head.

### 10.2 Detection and movement safety

**The YOLO detector does not directly control the robot's motors.**

A separate robot controller must:

- Stop movement when detection information is missing, invalid, or outdated.
- Implement a watchdog timeout.
- Publish zero velocity when tracking is no longer safe.
- Avoid responding to a single unverified detection.
- Handle brief detection gaps conservatively.
- Provide an emergency stopping mechanism independent of the detection system.

The robot may retain its last motor-speed command until another command is received. Stopping the detector alone does not guarantee that the robot will stop.

### 10.3 Emergency stop

If the robot behaves unexpectedly, use the team's physical emergency stopping procedure immediately when needed.

If software control is still available, stop the controller and publish zero velocity from a working ROS environment:

```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" -r 10 --times 20
```

Switch off the robot's main power if movement cannot be stopped safely.

Verify that `/cmd_vel` is the correct velocity command topic for the running robot configuration.

### 10.4 Battery safety

Check the robot's battery voltage using the team's monitoring procedure.

For the configuration described in the original project instructions:

```bash
ros2 topic echo /voltage
```

The team's robot instructions specify a minimum operating voltage of **10.3 V**.

Use the supplied charger and do not leave charging unattended.

### 10.5 ROS Domain safety

The team's assigned ROS Domain ID is `13`.

Confirm that all relevant nodes use the correct domain ID to avoid interference with other robots.

## 11. Troubleshooting

| Problem | What to check |
|---|---|
| `best.pt` cannot be found | Confirm `models/best.pt` exists |
| `No module named ultralytics` | Check the active Python environment |
| `No module named rclpy` | Use the correct ROS 2 environment |
| `No module named cv_bridge` | Check the ROS Humble image-bridge package |
| No camera frames | Check the camera driver, topic, message type, and ROS Domain ID |
| `/toy_detection` does not appear | Check node execution and ROS communication |
| Low inference speed | Measure Raspberry Pi CPU and memory usage |
| False positives | Inspect the camera scene and confidence threshold |
| False negatives during frontal views | Inspect the dinosaur's orientation and image quality |
| False negatives during fast movement | Inspect motion blur and temporary tracking loss |
| Model updated but results unchanged | Confirm the correct `best.pt` is loaded and restart the detector |

## 12. Integration Status

| Component | Status |
|---|---|
| YOLO V6 training | Completed |
| Windows offline inference | Tested |
| Recorded robot-camera video testing | Preliminary testing completed |
| Raspberry Pi model loading | Not yet verified |
| Live ROS 2 camera integration | Not yet verified |
| `/toy_detection` publishing on Raspberry Pi | Not yet verified |
| Autonomous robot movement | Not included in this repository |
| V7 frontal-view improvements | In development |

**Recommended first integration test:** Verify that the detector loads, receives camera images, and publishes detection results correctly **without enabling autonomous movement**.

## References

- [Ultralytics Documentation](https://docs.ultralytics.com/)
- [Ultralytics Raspberry Pi Guide](https://docs.ultralytics.com/guides/raspberry-pi/)
- [ROS 2 Humble Documentation](https://docs.ros.org/en/humble/)
- [Yahboom ROSMASTER M1](https://www.yahboom.net/study/ROSMASTER-M1/16900)
