"""Grid raycasting using the classic DDA algorithm.

The functions here are deliberately decoupled from the rest of the engine: they
operate purely on an ``is_solid(map_x, map_y)`` predicate plus an optional
``tile_at`` accessor.  That keeps them trivially unit-testable and lets the
renderer, the line-of-sight checks and the hitscan weapons all share one
well-tested implementation.
"""

import math
from collections import namedtuple

# dist      : Euclidean distance along the ray to the wall (dir must be a unit
#             vector).  The renderer multiplies by cos(angle) to remove fish-eye.
# side      : 0 if a vertical (NS) grid line was hit, 1 if horizontal (EW)
# map_x/y   : the solid cell that was hit
# tile      : tile code of that cell (None if no tile_at was supplied)
# wall_x    : fractional [0,1) coordinate along the wall face, for texturing
RayHit = namedtuple("RayHit", "dist side map_x map_y tile wall_x hit")

_INF = float("inf")


def cast_ray(is_solid, px, py, dir_x, dir_y, max_dist=64.0, tile_at=None):
    """Cast a single ray from ``(px, py)`` along the unit vector ``(dir_x, dir_y)``.

    Returns a :class:`RayHit`.  ``hit`` is ``False`` (and ``dist`` is
    ``max_dist``) when nothing solid is reached inside ``max_dist``.
    """
    map_x = int(math.floor(px))
    map_y = int(math.floor(py))

    delta_x = abs(1.0 / dir_x) if dir_x != 0 else _INF
    delta_y = abs(1.0 / dir_y) if dir_y != 0 else _INF

    if dir_x < 0:
        step_x = -1
        side_x = (px - map_x) * delta_x
    else:
        step_x = 1
        side_x = (map_x + 1.0 - px) * delta_x
    if dir_y < 0:
        step_y = -1
        side_y = (py - map_y) * delta_y
    else:
        step_y = 1
        side_y = (map_y + 1.0 - py) * delta_y

    side = 0
    while True:
        if side_x < side_y:
            side_x += delta_x
            map_x += step_x
            side = 0
            travelled = side_x - delta_x
        else:
            side_y += delta_y
            map_y += step_y
            side = 1
            travelled = side_y - delta_y

        if travelled > max_dist:
            return RayHit(max_dist, side, map_x, map_y, None, 0.0, False)

        if is_solid(map_x, map_y):
            perp = side_x - delta_x if side == 0 else side_y - delta_y
            if side == 0:
                wall_x = py + perp * dir_y
            else:
                wall_x = px + perp * dir_x
            wall_x -= math.floor(wall_x)
            tile = tile_at(map_x, map_y) if tile_at else None
            return RayHit(perp, side, map_x, map_y, tile, wall_x, True)


def line_of_sight(is_solid, ax, ay, bx, by):
    """Return ``True`` when nothing solid lies on the segment ``a -> b``.

    Used for monster vision and hitscan target validation.
    """
    dx = bx - ax
    dy = by - ay
    dist = math.hypot(dx, dy)
    if dist < 1e-9:
        return True
    hit = cast_ray(is_solid, ax, ay, dx / dist, dy / dist, max_dist=dist)
    # A hit strictly closer than the target means the view is blocked.
    return (not hit.hit) or hit.dist >= dist - 1e-6
