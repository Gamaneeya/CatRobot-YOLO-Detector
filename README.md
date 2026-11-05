# CatRobot YOLO V7.2 — ROSMASTER M1

Interactive Cat Robot using a custom YOLO11n model to detect and follow a green dinosaur toy.

## Additional Team TODO

Original team TODO document:

https://docs.google.com/document/d/10HqTygtLJ_eHqW0Ld5s-cQTaiufLqVcBtTM20mGjPLs/edit

## Project Goal

The robot should be able to:

1. Detect the green dinosaur using its camera.
2. Show the YOLO bounding box on the web interface.
3. Turn left or right to face the dinosaur.
4. Move forward when the dinosaur is centered and the path is safe.
5. Stop when the target is lost, too close, or an obstacle is detected.
6. Support manual control, emergency stopping, meow sounds, and buzzer controls.

**Important:** Some features are implemented in simulation but have not yet been validated on the physical robot.

## Model Information

| Property | Value |
|---|---|
| Architecture | YOLO11n |
| Custom model | V7.2 |
| Class | `green_dino` |
| Class ID | 0 |
| Weight file | `models/best.pt` |
| Input size | 640 |
| Framework | Ultralytics |

V7.2 is a custom training version of YOLO11n, not the separate YOLOv7 architecture.

The model was verified on Windows. Raspberry Pi inference speed and real-robot performance still require testing.

## Project Files

| File | Purpose |
|---|---|
| `models/best.pt` | Trained YOLO V7.2 model |
| `robot_teleop_yolo_sim.py` | Windows simulator with Mock Motor |
| `robot_teleop_yolo_pi_dryrun.py` | Raspberry Pi camera + YOLO + Mock Motor |
| `robot_teleop_yolo_robot.py` | Planned real-motor integration; not yet included in the verified release |
| `toy_detector.py` | YOLO detection utility |
| `test_video.py` | Video inference test |
| `ros2_toy_detector_node.py` | Experimental ROS2 detection integration |
| `requirements.txt` | Python dependencies |
| `docs/FRIEND_TODO_TH.md` | Main setup and testing checklist for the teammate |
| `docs/ROBOT_SETUP_TH.md` | Additional setup and troubleshooting reference |

The teammate's original `robot_teleop.py` already exists on the Raspberry Pi. It must not be overwritten.

## Current Development Status

| Component | Status |
|---|---|
| YOLO V7.2 on Windows | Verified |
| Windows Auto Follow simulation | Tested |
| Raspberry Pi Dry Run syntax | Passed |
| Raspberry Pi camera + YOLO | Pending hardware test |
| Real Motor integration | Pending validation |
| LiDAR obstacle detection | Not yet integrated |
| Automatic physical following | Not yet validated |
| Raspberry Pi meow audio | Pending integration test |

A Python syntax check does not guarantee that the program will run correctly on Raspberry Pi hardware.

## Deployment Approach

The current deployment uses Python directly on the Raspberry Pi host.

**Docker is not required.**

ROS2 integration remains optional and is not required for the initial OpenCV-based Dry Run.

The original robot program and the new YOLO programs must not run simultaneously if they share the same camera or port 8080.

## START HERE — For the Teammate

Follow this document in order:

**[Teammate Setup & Test Checklist](docs/FRIEND_TODO_TH.md)**

The checklist covers:

- Raspberry Pi hardware and environment checks
- Downloading the code while online
- Installing and verifying Python dependencies
- Preparing offline installation files
- Testing YOLO and the camera
- Switching to the robot network
- Raspberry Pi Dry Run
- Motor and LiDAR verification
- Supervised physical Auto Follow testing
- Troubleshooting and reporting results

**Do not disconnect from the internet until the online installation and offline verification steps have passed.**

## Quick Start — Raspberry Pi Dry Run

After completing the installation checklist:

```bash
cd ~/CatRobot-YOLO-Detector
source .venv/bin/activate
python robot_teleop_yolo_pi_dryrun.py
```

Open:

`http://ROBOT_IP:8080`

Replace `ROBOT_IP` with the current Raspberry Pi IP address.

Expected behavior:

- Camera stream appears in the browser.
- YOLO detects the green dinosaur.
- Bounding boxes and confidence are displayed.
- AUTO FOLLOW calculates LEFT / RIGHT / FORWARD / STOP.
- Motor commands are simulated.

**The Dry Run must never move the physical robot.**

## Real Robot Auto Follow

Real movement requires the separate `robot_teleop_yolo_robot.py` program.

Do not use the real-motor program until:

- The actual Motor Backend has been verified.
- The motor directions have been tested safely.
- The LiDAR produces valid distance readings.
- Obstacle stopping is implemented and tested.
- Target-loss and stale-camera stopping work.
- The system starts in STOPPED mode.
- The emergency stop procedure has been demonstrated.
- Someone is physically present to supervise the test.

A bounding box is not a reliable physical distance sensor.

## Controls

The web interface includes these modes:

| Control | Purpose |
|---|---|
| MANUAL | Manual driving controls |
| AUTO FOLLOW | Follow controller |
| STOP | Latched software stop |
| WASD | Manual movement |
| Arrow keys | Camera servo commands, if supported |
| C | Center camera, if supported |
| M / 6–0 | Meow sound variants |
| 1–5 | Buzzer patterns, including SOS |
| Space | STOPPED mode |

Some controls are simulated or disabled depending on the file being run.

Web STOP is not a substitute for a physical emergency stop.

## Audio

The original robot program uses Raspberry Pi audio utilities such as `aplay` and `mpg123`.

The current Dry Run includes Windows-specific `winsound` playback code and should not be treated as a verified Raspberry Pi audio implementation.

Audio must be tested separately before the final demonstration.

## Network and Security

Port 8080 serves the local web interface.

The current web control interface does not provide user authentication. Run it only on a trusted local network. Do not expose port 8080 to the public internet.

Keep the original robot program available as a fallback, and avoid configuring the new program to start automatically until testing is complete.

## Troubleshooting

For installation errors, camera problems, PyTorch issues, network disconnections, and motor or LiDAR test failures, see:

`docs/FRIEND_TODO_TH.md`

## Safety

The real robot must be supervised during all physical movement tests.

Start with wheels lifted securely, use low speed, keep a person ready to cut motor power, and test on a clear floor only after the safety checks pass.

If any stop condition or sensor verification fails, do not proceed to floor-level AUTO FOLLOW.