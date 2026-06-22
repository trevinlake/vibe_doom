"""Level definitions and the ASCII map parser.

A level is authored as a list of equal-length strings.  :func:`parse_level`
turns that into:

* ``grid``         – ``list[list[int]]`` of tile codes (see ``constants``)
* ``player_start`` – ``(x, y, angle)`` in world units
* ``monsters``     – ``list[(monster_type, x, y)]``
* ``items``        – ``list[(item_kind, x, y)]``

Map legend
----------
=====  ====================================================
char   meaning
=====  ====================================================
``#``  brick wall            ``1`` tech wall    ``2`` blood wall
``D``  door                  ``L`` locked door (needs red key)
``X``  exit switch           ``.`` / space  floor
``P``  player start
``z``  zombieman   ``i`` imp   ``d`` demon (pinky)
``h``  health  ``a`` armor  ``b`` bullets  ``s`` shells
``g``  shotgun  ``c`` chaingun  ``k`` red keycard
=====  ====================================================
"""

import math

from . import constants as C

# Characters that become geometry in the integer grid.
_TILE_CHARS = {
    "#": C.T_WALL,
    "1": C.T_WALL2,
    "2": C.T_WALL3,
    "D": C.T_DOOR,
    "L": C.T_DOOR_LOCKED,
    "X": C.T_EXIT,
    ".": C.T_FLOOR,
    " ": C.T_FLOOR,
}

# Characters that place a "thing" on an otherwise-floor cell.
_MONSTER_CHARS = {"z": "zombie", "i": "imp", "d": "demon"}
_ITEM_CHARS = {
    "h": C.ITEM_HEALTH,
    "a": C.ITEM_ARMOR,
    "b": C.ITEM_BULLETS,
    "s": C.ITEM_SHELLS,
    "g": C.ITEM_SHOTGUN,
    "c": C.ITEM_CHAINGUN,
    "k": C.ITEM_KEY_RED,
}


def parse_level(rows):
    """Parse a list of strings into a structured level description.

    Raises ``ValueError`` for ragged maps or a missing/duplicate player start so
    that broken levels fail loudly instead of producing a subtly wrong world.
    """
    if not rows:
        raise ValueError("level has no rows")
    width = len(rows[0])
    if width == 0:
        raise ValueError("level rows are empty")

    grid = []
    monsters = []
    items = []
    player_start = None

    for y, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(
                "ragged map: row %d has width %d, expected %d" % (y, len(row), width)
            )
        grid_row = []
        for x, ch in enumerate(row):
            cx, cy = x + 0.5, y + 0.5
            if ch == "P":
                if player_start is not None:
                    raise ValueError("map has more than one player start 'P'")
                player_start = (cx, cy, 0.0)
                grid_row.append(C.T_FLOOR)
            elif ch in _MONSTER_CHARS:
                monsters.append((_MONSTER_CHARS[ch], cx, cy))
                grid_row.append(C.T_FLOOR)
            elif ch in _ITEM_CHARS:
                items.append((_ITEM_CHARS[ch], cx, cy))
                grid_row.append(C.T_FLOOR)
            elif ch in _TILE_CHARS:
                grid_row.append(_TILE_CHARS[ch])
            else:
                raise ValueError("unknown map char %r at (%d,%d)" % (ch, x, y))
        grid.append(grid_row)

    if player_start is None:
        raise ValueError("map has no player start 'P'")

    return {
        "grid": grid,
        "player_start": player_start,
        "monsters": monsters,
        "items": items,
        "width": width,
        "height": len(rows),
    }


# ── The campaign ────────────────────────────────────────────────────────────
LEVEL_1 = {
    "name": "Hangar",
    "rows": [
        "##################",
        "#P....z..........#",
        "#......#####.....#",
        "#......#...#..b..#",
        "#..h...D...#.....#",
        "#......#...#..z..#",
        "#......#####.....#",
        "#...g......#######",
        "#.....z....#.....#",
        "#....k.....L....X#",
        "#..........#.....#",
        "#.d........#.....#",
        "##################",
    ],
}

LEVEL_2 = {
    "name": "Nuclear Plant",
    "rows": [
        "####################",
        "#P.......z....b....#",
        "#....##......##....#",
        "#....##..i...##....#",
        "#........DD........#",
        "#....##......##....#",
        "#g...##..z...##...s#",
        "######........######",
        "#.......i....h.....#",
        "#..####......####..#",
        "#..####..d...####.c#",
        "#.................X#",
        "#....z.......i....a#",
        "####################",
    ],
}

LEVEL_3 = {
    "name": "Inferno",
    # Exit sits in a small alcove sealed by a locked door (L); the red keycard
    # is out in the open arena, guarded by the horde.
    "rows": [
        "######################",
        "#P....s....d....i....#",
        "#.2222..........222..#",
        "#.2.......d......k...#",
        "#.2...i.........i..2.#",
        "#.....d.......h....2.#",
        "#.2........d.......###",
        "#.2...i........i...L.X",
        "#.2..........d.....###",
        "#.2222..........222..#",
        "#.....i....d.....i...#",
        "#.2.............d..2.#",
        "#c...z....dd......z..#",
        "######################",
    ],
}

LEVELS = [LEVEL_1, LEVEL_2, LEVEL_3]
