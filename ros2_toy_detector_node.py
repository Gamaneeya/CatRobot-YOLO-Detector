import json
import time
import cv2
import rclpy

from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import String
from cv_bridge import CvBridge
from toy_detector import ToyDetector


class ToyDetectorNode(Node):
    def __init__(self):
        super().__init__("toy_detector_node")

        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("compressed", False)
        self.declare_parameter("confidence", 0.5)
        self.declare_parameter("inference_hz", 5.0)
        self.declare_parameter("max_frame_age", 1.0)

        topic = self.get_parameter("image_topic").value
        compressed = self.get_parameter("compressed").value
        confidence = self.get_parameter("confidence").value
        hz = float(self.get_parameter("inference_hz").value)
        self.max_age = float(
            self.get_parameter("max_frame_age").value
        )

        if hz <= 0 or self.max_age <= 0:
            raise ValueError("inference_hz and max_frame_age must be > 0")

        self.bridge = CvBridge()
        self.detector = ToyDetector(confidence=confidence)
        self.publisher = self.create_publisher(
            String, "/toy_detection", 10
        )

        self.latest_frame = None
        self.latest_time = None

        message_type = CompressedImage if compressed else Image

        self.subscription = self.create_subscription(
            message_type, topic, self.on_image, 10
        )

        self.timer = self.create_timer(1.0 / hz, self.process_frame)
        self.get_logger().info(f"Listening to {topic}")

    def on_image(self, msg):
        try:
            if isinstance(msg, CompressedImage):
                array = __import__("numpy").frombuffer(
                    msg.data, dtype="uint8"
                )
                frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
                if frame is None:
                    raise ValueError("Cannot decode compressed image")
            else:
                frame = self.bridge.imgmsg_to_cv2(
                    msg, desired_encoding="bgr8"
                )

            self.latest_frame = frame
            self.latest_time = time.monotonic()

        except Exception as exc:
            self.get_logger().error(f"Camera conversion: {exc}")
            self.latest_frame = None
            self.latest_time = None

    def publish(self, data):
        msg = String()
        msg.data = json.dumps(data)
        self.publisher.publish(msg)

    def process_frame(self):
        if self.latest_frame is None or self.latest_time is None:
            self.publish({
                "status": "no_camera_frame",
                "detected": False
            })
            return

        if time.monotonic() - self.latest_time > self.max_age:
            self.publish({
                "status": "stale_camera_frame",
                "detected": False
            })
            return

        try:
            result = self.detector.detect(self.latest_frame)
            result["status"] = (
                "detected" if result["detected"]
                else "no_detection"
            )
            self.publish(result)
        except Exception as exc:
            self.get_logger().error(f"Inference: {exc}")
            self.publish({
                "status": "inference_error",
                "detected": False
            })


def main():
    rclpy.init()
    node = None
    try:
        node = ToyDetectorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
