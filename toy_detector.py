from pathlib import Path
from ultralytics import YOLO

DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "best.pt"

class ToyDetector:
    def __init__(self, model_path=None, confidence=0.5):
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL
        self.confidence = float(confidence)
        self.model = YOLO(str(self.model_path))

    def detect(self, frame):
        height, width = frame.shape[:2]

        result = self.model.predict(
            source=frame,
            conf=self.confidence,
            iou=0.45,
            imgsz=640,
            max_det=1,
            verbose=False
        )[0]

        if len(result.boxes) == 0:
            return {
                "detected": False,
                "confidence": 0.0,
                "center_x": None,
                "center_y": None,
                "bbox": None
            }

        box = result.boxes[0]
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]

        return {
            "detected": True,
            "confidence": float(box.conf[0]),
            "center_x": ((x1 + x2) / 2) / width,
            "center_y": ((y1 + y2) / 2) / height,
            "bbox": [x1, y1, x2, y2]
        }
