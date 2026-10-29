# CatRobot YOLO V3 Detector

Custom YOLO11n object detection model trained to detect a **small green dinosaur plush toy** for the CatRobot project using ROSMASTER M1.

This repository contains the trained model and inference code only. Training datasets, training scripts, and experiment files are not required.

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
| `models/best.pt` | Trained YOLO V3 model |
| `toy_detector.py` | Loads the model and returns detection results |
| `test_video.py` | Tests the model using a local video |
| `ros2_toy_detector_node.py` | ROS 2 node that receives camera images and publishes detection results |
| `requirements.txt` | Python inference dependency |
| `README.md` | Setup and integration instructions |

## 2. Test on Windows (Developer)

### 2.1 Clone the repository

```powershell
git clone https://github.com/YOUR_USERNAME/CatRobot-YOLO-Detector.git
cd CatRobot-YOLO-Detector
```

Replace `YOUR_USERNAME` with the repository owner's GitHub username.

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
.\.venv\Scripts\python.exe -c "from toy_detector import ToyDetector; d=ToyDetector(); print('YOLO V3 loaded successfully')"
```

Expected output:

```text
YOLO V3 loaded successfully
```

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

Use the robot's existing ROS 2 Docker environment. Do not reinstall ROS 2 or replace the existing container unless necessary.

### 3.1 Connect to the robot

Power on the ROSMASTER M1 using the team's robot startup procedure.

Connect the development computer and robot to the same network.

Open a terminal on the development computer:

```bash
ssh pi@ROBOT_IP
```

Replace `ROBOT_IP` with the current IP shown on the robot's OLED display.

### 3.2 Check the Docker environment

On the Raspberry Pi host:

```bash
docker ps
```

Check the available containers and identify the existing ROS 2 Humble container.

To enter an already-running container:

```bash
docker exec -it CONTAINER_NAME /bin/bash
```

Replace `CONTAINER_NAME` with the actual container name.

If the robot's container is not running, follow the team's existing Yahboom Docker startup instructions.

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

Check that the detector and other communicating ROS 2 nodes use the same domain ID. If the team has configured the robot to domain 13, set the detector environment accordingly:

```bash
export ROS_DOMAIN_ID=13
```

Do not change only one side of the ROS network without checking the other nodes.

### 3.4 Clone the repository

On the Raspberry Pi, the project must be placed in a directory accessible from the ROS 2 Docker container.

Check the container's mounted directories on the Raspberry Pi host:

```bash
docker inspect CONTAINER_NAME --format '{{json .Mounts}}'
```

Choose a persistent shared directory from the results.

Clone the repository into that directory:

```bash
git clone https://github.com/YOUR_USERNAME/CatRobot-YOLO-Detector.git
```

Enter the repository directory from inside Docker using its actual mounted path.

For example, if the project is visible under `/root/yahboomcar_ws`:

```bash
cd /root/yahboomcar_ws/CatRobot-YOLO-Detector
```

This path is an example and must be verified on the robot.

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

If dependencies are missing, first identify the missing packages and verify compatibility with the container's Python version and ARM64 architecture.

For missing ROS image conversion dependencies, the following packages may be needed:

```bash
apt update
apt install -y ros-humble-cv-bridge python3-opencv python3-numpy
```

If PyTorch or Ultralytics is missing, choose a compatible installation for the container's actual Python version and architecture.

**Do not blindly replace the existing NumPy, OpenCV, or PyTorch installation.** This could break ROS image conversion or other robot applications.

The `requirements.txt` file is suitable for Python inference setup, but its installation inside the robot's ROS 2 container has not yet been verified.

## 4. Verify YOLO V3 on Raspberry Pi

Before connecting the camera, test whether the model can load.

From the repository directory inside Docker:

```bash
python3 -c "from toy_detector import ToyDetector; d=ToyDetector(); print('YOLO V3 loaded successfully')"
```

Expected output:

```text
YOLO V3 loaded successfully
```

This confirms that Python can access the model and load it through Ultralytics.

If a test video is available inside the container, run:

```bash
python3 test_video.py --video /path/to/test.mp4 --stride 5
```

Replace the video path with an existing file.

## 5. Find the ROS 2 Camera Topic

Make sure the robot's camera driver is running.

Inside Docker:

```bash
ros2 node list
ros2 topic list -t
```

Look for a camera topic with one of these message types:

- `sensor_msgs/msg/Image`
- `sensor_msgs/msg/CompressedImage`

Check the selected topic:

```bash
ros2 topic info /ACTUAL_CAMERA_TOPIC
ros2 topic hz /ACTUAL_CAMERA_TOPIC
```

Replace `/ACTUAL_CAMERA_TOPIC` with the actual discovered topic.

The detector's default camera topic is `/camera/image_raw`, but this has not yet been verified on the ROSMASTER M1.

## 6. Run the ROS 2 YOLO Detector

### 6.1 Standard image topic

From the repository directory inside Docker:

```bash
python3 ros2_toy_detector_node.py --ros-args -p image_topic:=/ACTUAL_CAMERA_TOPIC
```

### 6.2 Compressed image topic

If the camera publishes `sensor_msgs/msg/CompressedImage`:

```bash
python3 ros2_toy_detector_node.py --ros-args -p image_topic:=/ACTUAL_COMPRESSED_TOPIC -p compressed:=true
```

Replace the placeholder with the correct topic.

### 6.3 Verify detection output

Open a second SSH terminal.

Enter the same running ROS 2 Docker container and source ROS 2:

```bash
source /opt/ros/humble/setup.bash
```

Ensure that the second terminal uses the same ROS Domain ID.

Run:

```bash
ros2 topic echo /toy_detection
```

The detector publishes detection information as JSON text inside a `std_msgs/msg/String` message.

The detector **does not publish motor movement commands**.

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

Field descriptions:

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

When no object is detected, `center_x`, `center_y`, and `bbox` are `null` for a normal `no_detection` result. Other error statuses may contain only the status and detected fields.

## 8. Known Model Limitations

YOLO V3 has been tested on recorded videos and selected test images.

However, some limitations remain:

- The model can incorrectly detect green grass or similar backgrounds as the dinosaur toy.
- A high confidence score does not guarantee a correct prediction.
- Detection may be unstable when the toy is very small, partially hidden, or moving quickly.
- Some previously reviewed videos contain frames that overlap with the training dataset.
- Performance on the Raspberry Pi camera has not been verified.

Additional tests using new footage from the ROSMASTER M1 camera are recommended before enabling movement control.

## 9. Robot Safety Warnings

### 9.1 Physical Safety

- Place the robot securely on a stand with its wheels off the ground for initial movement tests.
- Maintain at least 2 meters of clear space during floor testing.
- Keep hands, hair, and cables away from moving components and LiDAR.
- Do not manually rotate the powered camera head.

### 9.2 Detection and Movement Safety

**The detector does not control the robot's motors.**

A separate robot controller must:

- Stop movement when detection is missing, invalid, or outdated.
- Implement a watchdog timeout.
- Send zero velocity when a tracking command is no longer safe.
- Avoid responding to a single unverified detection.
- Provide an emergency stop independent of the detection system.

The robot may retain its last motor speed command until another command is received. Stopping the detector alone does not guarantee that the robot will stop.

### 9.3 Emergency Stop

If the robot behaves unexpectedly, use the physical emergency stopping method immediately when necessary.

If software control is still available:

1. Stop the active controller using `Ctrl+C`, when safe.
2. Publish zero velocity from a working ROS environment:

```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" -r 10 --times 20
```

3. Switch off the robot's main power if movement cannot be stopped safely.

### 9.4 Battery Safety

Check the robot's battery voltage:

```bash
ros2 topic echo /voltage
```

The team's robot instructions specify a minimum operating voltage of **10.3 V**.

Only use the supplied charger and do not leave charging unattended.

### 9.5 ROS Domain Safety

The team's assigned domain ID is `13`.

Confirm that the robot's ROS nodes and the detector use the intended domain ID to avoid interference with other robots on the network.

## 10. Troubleshooting

| Problem | What to check |
|---|---|
| `best.pt` cannot be found | Confirm `models/best.pt` exists |
| `No module named ultralytics` | Verify Python environment and installation |
| `No module named rclpy` | Run inside the correct ROS 2 environment |
| `No module named cv_bridge` | Check ROS Humble image bridge package |
| Camera frames not received | Check camera driver, topic name, message type, and ROS Domain ID |
| `/toy_detection` does not appear | Check whether the node is running and whether both terminals use the same ROS environment |
| Low inference speed | Measure Raspberry Pi performance before adjusting model settings |
| False detections | Inspect camera frames; green grass is a known source of false positives |

## 11. Integration Status

| Component | Status |
|---|---|
| YOLO V3 training | Completed |
| Windows offline inference | Previously tested |
| Raspberry Pi model loading | Not yet verified |
| ROS 2 camera integration | Not yet verified |
| `/toy_detection` on Raspberry Pi | Not yet verified |
| Robot movement integration | Not included in this repository |

**Recommended first integration test:** Verify that the model loads, receives camera images, and publishes detection results correctly **without enabling autonomous movement**.

## 12. References

- [Ultralytics Documentation](https://docs.ultralytics.com/)
- [Ultralytics Raspberry Pi Guide](https://docs.ultralytics.com/guides/raspberry-pi/)
- [ROS 2 Documentation](https://docs.ros.org/en/humble/)
- [Yahboom ROSMASTER M1](https://www.yahboom.net/study/ROSMASTER-M1/16900)