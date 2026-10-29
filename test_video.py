import argparse
import cv2
from toy_detector import ToyDetector

parser = argparse.ArgumentParser()
parser.add_argument("--video", required=True)
parser.add_argument("--conf", type=float, default=0.5)
parser.add_argument("--stride", type=int, default=1)
args = parser.parse_args()

if not 0 < args.conf <= 1:
    parser.error("--conf must be between 0 and 1")
if args.stride < 1:
    parser.error("--stride must be >= 1")

detector = ToyDetector(confidence=args.conf)
cap = cv2.VideoCapture(args.video)

if not cap.isOpened():
    raise RuntimeError(f"Cannot open video: {args.video}")

frame_number = 0

try:
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame_number += 1
        if (frame_number - 1) % args.stride != 0:
            continue

        result = detector.detect(frame)

        print(
            f"frame={frame_number} "
            f"detected={result['detected']} "
            f"confidence={result['confidence']:.3f} "
            f"x={result['center_x']} "
            f"y={result['center_y']}",
            flush=True
        )
finally:
    cap.release()
