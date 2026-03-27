"""
Human-like mouse trajectory generator for slider captcha solving.

Generates realistic drag paths using:
  - Bezier curves for smooth, non-linear movement
  - Acceleration/deceleration (slow start, fast middle, slow end)
  - Random micro-jitter simulating hand tremor
  - Optional overshoot + correction
"""

import random
import math
from typing import List, Tuple


def _bezier_point(t: float, p0: float, p1: float, p2: float, p3: float) -> float:
    """Cubic Bezier interpolation at parameter t."""
    u = 1 - t
    return u*u*u*p0 + 3*u*u*t*p1 + 3*u*t*t*p2 + t*t*t*p3


def _ease_out_cubic(t: float) -> float:
    """Ease-out cubic: fast start, slow end."""
    return 1 - (1 - t) ** 3


def _ease_in_out_quad(t: float) -> float:
    """Ease in-out quadratic: slow start, fast middle, slow end."""
    if t < 0.5:
        return 2 * t * t
    return 1 - (-2 * t + 2) ** 2 / 2


def generate_trajectory(
    distance: int,
    start_x: int = 0,
    start_y: int = 0,
    duration_ms: int = None,
    overshoot: bool = True,
    jitter: float = 2.0,
) -> List[Tuple[int, int, int]]:
    """
    Generate a human-like drag trajectory.

    Args:
        distance: Horizontal pixels to drag
        start_x: Starting x position
        start_y: Starting y position
        duration_ms: Total drag duration in ms (default: auto 300-600ms)
        overshoot: Whether to overshoot then correct (more human-like)
        jitter: Max random y-deviation in pixels (hand tremor)

    Returns:
        List of (x, y, delay_ms) tuples representing the drag path.
        Each tuple is a point to move to, with delay before the next move.
    """
    if duration_ms is None:
        duration_ms = random.randint(350, 650)

    points = []
    num_steps = random.randint(25, 45)

    # Bezier control points for x-axis
    # P0 = start, P3 = end (with overshoot)
    overshoot_px = random.randint(3, 10) if overshoot else 0
    target_x = distance + overshoot_px

    # Randomized control points for natural curve
    cp1_x = target_x * random.uniform(0.2, 0.4)
    cp2_x = target_x * random.uniform(0.6, 0.85)

    # Y-axis: slight arc (not perfectly horizontal)
    y_arc = random.uniform(-3, 3)
    cp1_y = y_arc * random.uniform(0.5, 1.5)
    cp2_y = y_arc * random.uniform(0.3, 1.0)

    for i in range(num_steps):
        t = i / (num_steps - 1)

        # Use ease-in-out for timing (slow-fast-slow)
        eased_t = _ease_in_out_quad(t)

        # Bezier for position
        x = _bezier_point(eased_t, 0, cp1_x, cp2_x, target_x)
        y = _bezier_point(eased_t, 0, cp1_y, cp2_y, 0)

        # Add micro-jitter (hand tremor), less at start/end
        tremor_scale = math.sin(t * math.pi)  # peaks at middle
        jitter_x = random.gauss(0, jitter * 0.3 * tremor_scale)
        jitter_y = random.gauss(0, jitter * tremor_scale)

        # Time distribution: non-uniform (faster in middle)
        if t < 0.15:
            delay = duration_ms / num_steps * random.uniform(1.2, 1.8)
        elif t > 0.85:
            delay = duration_ms / num_steps * random.uniform(1.1, 1.6)
        else:
            delay = duration_ms / num_steps * random.uniform(0.5, 1.0)

        points.append((
            int(start_x + x + jitter_x),
            int(start_y + y + jitter_y),
            int(delay),
        ))

    # Overshoot correction: slide back to exact target
    if overshoot and overshoot_px > 0:
        correction_steps = random.randint(3, 6)
        for i in range(correction_steps):
            t = (i + 1) / correction_steps
            corr_x = target_x - overshoot_px * _ease_out_cubic(t)
            points.append((
                int(start_x + corr_x + random.gauss(0, 0.5)),
                int(start_y + random.gauss(0, 0.5)),
                int(random.uniform(15, 35)),
            ))

    # Final precise position
    points.append((start_x + distance, start_y, random.randint(10, 30)))

    return points


def trajectory_to_offsets(trajectory: List[Tuple[int, int, int]]) -> List[Tuple[int, int, int]]:
    """Convert absolute positions to relative offsets (dx, dy, delay_ms)."""
    offsets = []
    prev_x, prev_y = trajectory[0][0], trajectory[0][1]
    for x, y, delay in trajectory[1:]:
        offsets.append((x - prev_x, y - prev_y, delay))
        prev_x, prev_y = x, y
    return offsets
