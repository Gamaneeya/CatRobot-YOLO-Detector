
import time
import unittest

from tmini_plus_lidar import TminiPlusReader


def clear_points():
    return [
        (angle, 2.0)
        for angle in range(-180, 181, 5)
    ]


class TestTminiSafety(unittest.TestCase):
    def setUp(self):
        self.reader = TminiPlusReader(
            port="/dev/fake"
        )

    def test_no_scan_blocks_motion(self):
        self.assertFalse(
            self.reader.is_clear()
        )

    def test_open_sectors_allow_motion(self):
        self.reader._accept_scan(
            clear_points()
        )

        self.assertTrue(
            self.reader.is_clear()
        )

    def test_front_obstacle_blocks_motion(self):
        points = clear_points()
        points.append((0.0, 0.30))

        self.reader._accept_scan(points)

        self.assertFalse(
            self.reader.is_clear()
        )

        self.assertIn(
            "FRONT OBSTACLE",
            self.reader.snapshot()["reason"]
        )

    def test_left_obstacle_blocks_motion(self):
        points = clear_points()
        points.append((70.0, 0.30))

        self.reader._accept_scan(points)

        self.assertFalse(
            self.reader.is_clear()
        )

    def test_right_obstacle_blocks_motion(self):
        points = clear_points()
        points.append((-70.0, 0.30))

        self.reader._accept_scan(points)

        self.assertFalse(
            self.reader.is_clear()
        )

    def test_missing_coverage_blocks_motion(self):
        self.reader._accept_scan([
            (0.0, 2.0)
        ])

        self.assertFalse(
            self.reader.is_clear()
        )

    def test_stale_scan_blocks_motion(self):
        self.reader._accept_scan(
            clear_points()
        )

        with self.reader._lock:
            self.reader._last_scan = (
                time.monotonic() - 2.0
            )

        self.assertFalse(
            self.reader.is_clear()
        )

        self.assertEqual(
            self.reader.snapshot()["reason"],
            "STALE LIDAR DATA"
        )

    def test_front_angle_rotation(self):
        rotated = TminiPlusReader(
            port="/dev/fake",
            front_angle_deg=90.0
        )

        points = clear_points()
        points.append((90.0, 0.30))

        rotated._accept_scan(points)

        self.assertFalse(
            rotated.is_clear()
        )


if __name__ == "__main__":
    unittest.main()
