"""Sanity-check every campaign level: rectangular, has a reachable exit, and no
monster/item is embedded in a wall.  Run:  python tools/validate_maps.py
"""

import math
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doom import constants as C
from doom.maps import LEVELS, parse_level


def reachable_cells(grid, start):
    """Flood fill over floor + door cells (doors are openable, so passable)."""
    h, w = len(grid), len(grid[0])
    sx, sy = int(start[0]), int(start[1])
    seen = set()
    q = deque([(sx, sy)])
    passable = {C.T_FLOOR, C.T_DOOR, C.T_DOOR_LOCKED}
    while q:
        x, y = q.popleft()
        if (x, y) in seen:
            continue
        if not (0 <= x < w and 0 <= y < h):
            continue
        if grid[y][x] not in passable:
            continue
        seen.add((x, y))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q.append((x + dx, y + dy))
    return seen


def main():
    ok = True
    for i, lvl in enumerate(LEVELS):
        level = parse_level(lvl["rows"])
        grid = level["grid"]
        reach = reachable_cells(grid, level["player_start"])

        # Exit reachable? An exit cell counts as reached if a reachable floor
        # cell sits next to it.
        exits = [(x, y) for y, row in enumerate(grid)
                 for x, t in enumerate(row) if t == C.T_EXIT]
        exit_ok = any(
            (x + dx, y + dy) in reach
            for (x, y) in exits for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )

        # Things must stand on reachable floor.
        stray = []
        for kind, x, y in level["monsters"] + [(k, x, y) for k, x, y in level["items"]]:
            cell = (int(x), int(y))
            if cell not in reach:
                stray.append((kind, cell))

        status = "OK"
        if not exits or not exit_ok or stray:
            status = "PROBLEM"
            ok = False
        print("Level %d  %-16s  %dx%d  monsters=%d items=%d  exits=%d  %s"
              % (i + 1, lvl["name"], level["width"], level["height"],
                 len(level["monsters"]), len(level["items"]), len(exits), status))
        if not exits:
            print("   ! no exit switch")
        elif not exit_ok:
            print("   ! exit not reachable from player start")
        for kind, cell in stray:
            print("   ! %s at %s is walled off / not reachable" % (kind, cell))

    print("\nALL GOOD" if ok else "\nFIX REQUIRED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
