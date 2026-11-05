
#!/usr/bin/env python3

import argparse
import sys
import time

from tmini_plus_lidar import TminiPlusReader


def print_scan_status(reader):
    status = reader.snapshot()

    print(
        "[LiDAR]",
        status["reason"],
        "| age:", status["scan_age_s"],
        "| points:", status["valid_points"],
        "| front:", status["front_min_m"],
        "| left:", status["left_min_m"],
        "| right:", status["right_min_m"]
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        required=True,
        choices=[
            "scan-only",
            "manual-wheels-up",
            "auto-supervised"
        ]
    )

    parser.add_argument(
        "--port",
        default="/dev/ttyUSB0"
    )

    parser.add_argument(
        "--front-angle",
        type=float,
        default=0.0
    )

    parser.add_argument(
        "--confirm-wheels-up",
        action="store_true"
    )

    parser.add_argument(
        "--confirm-orientation",
        action="store_true"
    )

    parser.add_argument(
        "--confirm-supervised",
        action="store_true"
    )

    args = parser.parse_args()

    if args.mode == "manual-wheels-up":
        if not args.confirm_wheels_up:
            parser.error(
                "Manual motor test requires "
                "--confirm-wheels-up"
            )

    if args.mode == "auto-supervised":
        if not (
            args.confirm_orientation
            and args.confirm_supervised
        ):
            parser.error(
                "AUTO requires "
                "--confirm-orientation and "
                "--confirm-supervised"
            )

    lidar = None

    if args.mode in (
        "scan-only",
        "auto-supervised"
    ):
        lidar = TminiPlusReader(
            port=args.port,
            front_angle_deg=args.front_angle
        )
        lidar.start()

    if args.mode == "scan-only":
        print("LiDAR only. Robot motors are NOT opened.")
        print("Press Ctrl+C to stop.")

        try:
            while True:
                print_scan_status(lidar)
                time.sleep(1.0)

        except KeyboardInterrupt:
            pass

        finally:
            lidar.close()

        return

    import robot_teleop_yolo_robot as robot

    if args.mode == "manual-wheels-up":
        robot.ENABLE_REAL_MOTOR = True
        robot.ENABLE_AUTO_FOLLOW = False
        robot.lidar_clear_for_motion = lambda: False

        print("MANUAL MOTOR TEST")
        print("WHEELS MUST BE LIFTED")
        print("AUTO FOLLOW DISABLED")

    elif args.mode == "auto-supervised":
        robot.ENABLE_REAL_MOTOR = True
        robot.ENABLE_AUTO_FOLLOW = True

        robot.lidar_clear_for_motion = lidar.is_clear
        robot.MANUAL_LIDAR_REQUIRED = True

        print("SUPERVISED MANUAL + AUTO TEST")
        print("Web mode switching: ENABLED")
        print("Both modes require LiDAR clearance")
        print("LiDAR port:", args.port)
        print("Calibrated front angle:", args.front_angle)
        print("Physical emergency stop required.")

    original_get_status = robot.get_status

    def status_with_lidar():
        status = original_get_status()

        if lidar is None:
            status["lidar_reason"] = (
                "NOT USED IN MANUAL WHEELS-UP TEST"
            )
            status["lidar_front_m"] = None
            status["lidar_left_m"] = None
            status["lidar_right_m"] = None

        else:
            scan = lidar.snapshot()
            status["lidar_reason"] = scan["reason"]
            status["lidar_front_m"] = scan["front_min_m"]
            status["lidar_left_m"] = scan["left_min_m"]
            status["lidar_right_m"] = scan["right_min_m"]

        return status

    robot.get_status = status_with_lidar

    original_page = robot.page

    def page_with_lidar():
        page = original_page()

        page = page.replace(
            '<p id="notice"',
            '<p id="lidar_info" '
            'style="color:#8fdfac">'
            'LiDAR: checking...</p>'
            '<p id="notice"',
            1
        )

        script = """
setInterval(async () => {
    try {
        const response = await fetch("/status");
        const status = await response.json();
        const element = document.getElementById("lidar_info");

        if (element) {
            element.textContent =
                "LiDAR: " + status.lidar_reason +
                " | Front: " + status.lidar_front_m +
                "m | Left: " + status.lidar_left_m +
                "m | Right: " + status.lidar_right_m + "m";
        }
    } catch (error) {}
}, 500);
"""

        page = page.replace(
            "</script>",
            script + "</script>",
            1
        )

        return page

    robot.page = page_with_lidar

    try:
        robot.main()

    finally:
        if lidar is not None:
            lidar.close()


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        sys.exit(0)
