
# CatRobot YOLO V7.2 — ROSMASTER M1

Interactive Cat Robot project using a custom YOLO11n model to detect and follow a green dinosaur toy.

## Current Model

- Model: Custom YOLO11n V7.2
- Class: `green_dino` (ID 0)
- Weights: `models/best.pt`
- Image size: 640
- Development: Windows
- Target hardware: ROSMASTER M1 with Raspberry Pi

The V7.2 model has been verified to load on Windows. Raspberry Pi deployment and physical motor control are not yet validated.

## Main Files

| File | Purpose |
|---|---|
| `models/best.pt` | Trained YOLO V7.2 weights |
| `robot_teleop_yolo_sim.py` | Windows YOLO + Auto Follow simulator |
| `robot_teleop_yolo_pi_dryrun.py` | Raspberry Pi camera + YOLO dry run |
| `docs/ROBOT_SETUP_TH.md` | Thai step-by-step Raspberry Pi setup |
| `robot_teleop.py` | Teammate's original robot-control reference, not modified |
| `toy_detector.py` | YOLO detector utility |
| `ros2_toy_detector_node.py` | Separate experimental ROS2 integration |

## Deployment Method

The current deployment path runs Python directly on the Raspberry Pi.

Docker is NOT required for this setup.

The teammate's existing `robot_teleop.py` must not be overwritten.

Do not run the original robot teleoperation program and the new dry-run program simultaneously. Both may need the camera and port 8080.

## Before Disconnecting the Internet

1. Download the repository to the Raspberry Pi.
2. Check OS architecture and Python version.
3. Install Python dependencies in a project virtual environment.
4. Verify PyTorch, OpenCV and Ultralytics imports.
5. Verify the V7.2 model loads and runs inference.
6. Check the camera device.
7. Prepare and validate offline dependency files.
8. Follow `docs/ROBOT_SETUP_TH.md` for detailed commands and troubleshooting.

Do not assume Windows dependencies can run on Raspberry Pi.

## Raspberry Pi Dry Run

Once setup is completed, activate the project's Python environment and run:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
python robot_teleop_yolo_pi_dryrun.py
```

Open the web interface using the Raspberry Pi's current IP address:

`http://ROBOT_IP:8080`

Replace `ROBOT_IP` with the actual IP.

The dry-run program uses a MOCK motor. It must not move the real robot.

Expected dry-run capabilities:

- Camera video streaming
- YOLO Green Dino detection
- Bounding-box visualization
- Left / right / forward / stop decision simulation
- Manual / Auto / Stop web controls
- Mock motor output

Meow audio in this dry-run file is not yet supported on Raspberry Pi because it uses Windows audio code.

## Safety and Current Limitations

- Physical Auto Follow is NOT enabled.
- LiDAR obstacle avoidance is NOT integrated.
- Bounding-box area is not a reliable physical distance measurement.
- Low-confidence detections may include false positives.
- Real movement must not be enabled until motor, LiDAR and stop behavior are independently tested.

## Original Robot Program

The teammate's existing `robot_teleop.py` remains on the Raspberry Pi.

Our new programs are separate files. Do not overwrite or delete the original program.

## Legacy Documentation

Previous ROS2 and Docker research is archived in:

`docs/README_LEGACY_ROS2.md`

It is reference material only, not the current setup procedure.
