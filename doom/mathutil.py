"""Small, pure math helpers shared across the engine."""

import math

TAU = math.tau


def clamp(value, low, high):
    """Constrain ``value`` to the inclusive range ``[low, high]``."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def normalize_angle(angle):
    """Wrap an angle into the half-open range ``(-pi, pi]``."""
    angle = math.fmod(angle, TAU)
    if angle <= -math.pi:
        angle += TAU
    elif angle > math.pi:
        angle -= TAU
    return angle


def distance(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def angle_between(from_angle, to_angle):
    """Signed smallest difference ``to - from`` wrapped to ``(-pi, pi]``."""
    return normalize_angle(to_angle - from_angle)
