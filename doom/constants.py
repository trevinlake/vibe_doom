"""Tunable constants and shared enumerations for the engine.

Distances are measured in *tiles* (one map cell == 1.0 unit).  Time is measured
in seconds, so every speed below is "tiles per second" or "units per second"
and the engine is therefore frame-rate independent: ``Game.update(dt)`` scales
all motion by the real elapsed time.
"""

import math

# ── Tile codes stored in the integer grid ───────────────────────────────────
T_FLOOR = 0
T_WALL = 1          # plain brick
T_WALL2 = 2         # tech panel
T_WALL3 = 3         # blood marble
T_DOOR = 4          # sliding door (openable with USE)
T_DOOR_LOCKED = 5   # door that needs the red keycard
T_EXIT = 6          # exit switch (USE while facing it to finish the level)

WALL_TILES = (T_WALL, T_WALL2, T_WALL3)
DOOR_TILES = (T_DOOR, T_DOOR_LOCKED)

# ── Rendering geometry (used by the front-end, kept here so tests can share) ─
FOV = math.radians(66.0)          # DOOM's horizontal field of view
TEX_SIZE = 64                     # texture / sprite resolution

# ── Player tuning ────────────────────────────────────────────────────────────
PLAYER_RADIUS = 0.22
MOVE_SPEED = 3.4                  # tiles / second (run)
TURN_SPEED = math.radians(150)   # radians / second when using keyboard turn
USE_RANGE = 1.2                  # how far the USE action reaches
PLAYER_MAX_HEALTH = 100
PLAYER_MAX_ARMOR = 100

# ── Doors ────────────────────────────────────────────────────────────────────
DOOR_SPEED = 2.0                  # open/close fraction per second
DOOR_STAY_OPEN = 4.0             # seconds a door waits before auto-closing

# ── Ammunition types ──────────────────────────────────────────────────────────
AMMO_BULLETS = "bullets"
AMMO_SHELLS = "shells"

AMMO_MAX = {AMMO_BULLETS: 200, AMMO_SHELLS: 50}

# ── Keycards ───────────────────────────────────────────────────────────────────
KEY_RED = "red"

# ── Pickup kinds (also used as map "thing" codes, see maps.py) ─────────────────
ITEM_HEALTH = "health"
ITEM_ARMOR = "armor"
ITEM_BULLETS = "ammo_bullets"
ITEM_SHELLS = "ammo_shells"
ITEM_SHOTGUN = "weapon_shotgun"
ITEM_CHAINGUN = "weapon_chaingun"
ITEM_KEY_RED = "key_red"

# Amount each pickup grants.
HEALTH_PICKUP = 25
ARMOR_PICKUP = 25
BULLETS_PICKUP = 20
SHELLS_PICKUP = 8

ITEM_RADIUS = 0.45   # how close the player must be to grab an item

# ── Monster archetypes ─────────────────────────────────────────────────────────
# Stats deliberately echo the originals: the zombieman is a weak hitscanner, the
# imp lobs slow fireballs, the pinky demon is a fast melee bruiser.
MONSTERS = {
    "zombie": dict(
        health=20, speed=1.3, radius=0.30, damage=(3, 9),
        ranged=True, hitscan=True, melee=False,
        attack_range=8.0, attack_cooldown=1.1, sight=12.0, pain_chance=0.9,
    ),
    "imp": dict(
        health=60, speed=1.4, radius=0.30, damage=(6, 14),
        ranged=True, hitscan=False, melee=True, melee_damage=(3, 12),
        attack_range=9.0, attack_cooldown=1.4, sight=14.0, pain_chance=0.7,
        projectile_speed=5.0,
    ),
    "demon": dict(
        health=150, speed=2.6, radius=0.42, damage=(4, 40),
        ranged=False, hitscan=False, melee=True, melee_damage=(4, 40),
        attack_range=1.4, attack_cooldown=0.9, sight=12.0, pain_chance=0.5,
    ),
}

# Monster shared behaviour.
MONSTER_MELEE_REACH = 1.2
PROJECTILE_RADIUS = 0.25

# ── Weapons ────────────────────────────────────────────────────────────────────
# ``cooldown`` is the minimum seconds between shots; ``pellets`` lets the shotgun
# fire a spread; ``spread`` is the half-angle of random scatter in radians.
WEAPONS = {
    "fist": dict(
        name="Fist", ammo=None, damage=(2, 20), pellets=1, spread=0.0,
        cooldown=0.45, range=1.3, slot=1, melee=True,
    ),
    "pistol": dict(
        name="Pistol", ammo=AMMO_BULLETS, damage=(5, 15), pellets=1,
        spread=math.radians(2.8), cooldown=0.42, range=32.0, slot=2, melee=False,
    ),
    "shotgun": dict(
        name="Shotgun", ammo=AMMO_SHELLS, damage=(5, 15), pellets=7,
        spread=math.radians(9.0), cooldown=0.85, range=32.0, slot=3, melee=False,
    ),
    "chaingun": dict(
        name="Chaingun", ammo=AMMO_BULLETS, damage=(5, 15), pellets=1,
        spread=math.radians(4.5), cooldown=0.12, range=32.0, slot=4, melee=False,
    ),
}

# Default weapon-switch order (by slot).
WEAPON_ORDER = ["fist", "pistol", "shotgun", "chaingun"]
