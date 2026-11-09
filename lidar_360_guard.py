"""LiDAR-only circular proximity check. No camera/YOLO, motor or sound API."""
import math


def evaluate_circle(points, radius_m=0.22):
    """Check the available real 2D laser echoes against the sensor-origin radius.

    Missing echoes must not be interpreted as proof that a direction is clear.
    Caller must preserve the existing stale/insufficient-scan fail-closed gates.
    """
    if not (math.isfinite(radius_m) and 0.05 < radius_m <= 2.0):
        raise ValueError('Invalid LiDAR radius')
    nearest = None
    nearest_angle = None
    hits = 0
    for angle, distance in points:
        try:
            a, d = float(angle), float(distance)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(a) or not math.isfinite(d) or not 0.05 <= d <= 12.0:
            continue
        if nearest is None or d < nearest:
            nearest, nearest_angle = d, ((a + 180) % 360) - 180
        if d <= radius_m:
            hits += 1
    return {
        'circle_radius_m': radius_m,
        'circle_min_m': round(nearest, 3) if nearest is not None else None,
        'circle_min_angle_deg': round(nearest_angle, 1) if nearest_angle is not None else None,
        'circle_hits_inside': hits,
        'circle_obstacle': hits > 0,
    }
