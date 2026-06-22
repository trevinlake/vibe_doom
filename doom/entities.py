"""Game entities: the player, monsters, their projectiles and pickups.

These classes hold state and a little self-contained behaviour (taking damage,
granting pickups).  Anything that needs to query the world — vision, movement,
AI decisions — is driven from :mod:`doom.game`.
"""

import math

from . import constants as C


def _scale_range(rng, mult):
    """Scale a (lo, hi) damage range by ``mult``, keeping at least 1."""
    lo, hi = rng
    return (max(1, round(lo * mult)), max(1, round(hi * mult)))


class Player:
    def __init__(self, x, y, angle=0.0):
        self.x = x
        self.y = y
        self.angle = angle
        self.health = C.PLAYER_MAX_HEALTH
        self.armor = 0
        self.radius = C.PLAYER_RADIUS
        # Start with fists + pistol, exactly like the original.
        self.weapons = {"fist", "pistol"}
        self.current_weapon = "pistol"
        self.ammo = {C.AMMO_BULLETS: 50, C.AMMO_SHELLS: 0}
        self.keys = set()
        self.weapon_cooldown = 0.0
        # Cosmetic timers consumed by the renderer.
        self.muzzle_flash = 0.0
        self.bob = 0.0
        self.damage_flash = 0.0
        self.last_damage_dir = 0.0  # angle from player to the hit source

    @property
    def alive(self):
        return self.health > 0

    # ── combat ──────────────────────────────────────────────────────────────
    def take_damage(self, amount, source_angle=None):
        """Apply ``amount`` damage, letting green armor soak ~1/3 like DOOM."""
        if amount <= 0:
            return
        absorbed = 0
        if self.armor > 0:
            absorbed = min(self.armor, int(amount / 3))
            self.armor -= absorbed
        self.health -= (amount - absorbed)
        if self.health < 0:
            self.health = 0
        self.damage_flash = min(1.0, self.damage_flash + 0.6)
        if source_angle is not None:
            self.last_damage_dir = source_angle

    # ── pickups ─────────────────────────────────────────────────────────────
    def give_health(self, amount):
        if self.health >= C.PLAYER_MAX_HEALTH:
            return False
        self.health = min(C.PLAYER_MAX_HEALTH, self.health + amount)
        return True

    def give_armor(self, amount):
        if self.armor >= C.PLAYER_MAX_ARMOR:
            return False
        self.armor = min(C.PLAYER_MAX_ARMOR, self.armor + amount)
        return True

    def give_ammo(self, ammo_type, amount):
        cap = C.AMMO_MAX[ammo_type]
        if self.ammo.get(ammo_type, 0) >= cap:
            return False
        self.ammo[ammo_type] = min(cap, self.ammo.get(ammo_type, 0) + amount)
        return True

    def give_weapon(self, weapon_key):
        had = weapon_key in self.weapons
        self.weapons.add(weapon_key)
        # Auto-switch to a freshly collected weapon, as DOOM does.
        self.current_weapon = weapon_key
        return not had

    def give_key(self, key):
        had = key in self.keys
        self.keys.add(key)
        return not had

    def current_ammo(self):
        ammo_type = C.WEAPONS[self.current_weapon]["ammo"]
        if ammo_type is None:
            return None
        return self.ammo.get(ammo_type, 0)


class Monster:
    STATES = ("idle", "chase", "attack", "pain", "dead")

    def __init__(self, mtype, x, y, difficulty=None):
        self.type = mtype
        # Work on a private copy so per-level difficulty scaling never mutates
        # the shared constant table.
        cfg = dict(C.MONSTERS[mtype])
        scale = difficulty or C.NEUTRAL_DIFFICULTY
        cfg["health"] = max(1, round(cfg["health"] * scale["health"]))
        cfg["speed"] = cfg["speed"] * scale["speed"]
        cfg["attack_cooldown"] = cfg["attack_cooldown"] * scale["cooldown"]
        cfg["damage"] = _scale_range(cfg["damage"], scale["damage"])
        if "melee_damage" in cfg:
            cfg["melee_damage"] = _scale_range(cfg["melee_damage"], scale["damage"])
        self.cfg = cfg
        self.x = x
        self.y = y
        self.angle = 0.0
        self.health = cfg["health"]
        self.radius = cfg["radius"]
        self.speed = cfg["speed"]
        self.state = "idle"
        self.state_time = 0.0    # seconds spent in the current state
        self.anim_time = 0.0     # free-running clock for walk animation
        self.attack_cooldown = 0.0
        self.alive = True
        self.awake = False       # has the monster noticed the player yet?

    @property
    def dead(self):
        return not self.alive

    def take_damage(self, amount, rng):
        if not self.alive:
            return
        self.health -= amount
        self.awake = True
        if self.health <= 0:
            self.health = 0
            self.alive = False
            self.state = "dead"
            self.state_time = 0.0
            return
        # Chance to flinch into a brief pain state.
        if rng.random() < self.cfg["pain_chance"]:
            self.state = "pain"
            self.state_time = 0.0


class Projectile:
    """A travelling fireball (imp) or similar."""

    def __init__(self, x, y, dir_x, dir_y, speed, damage, owner="imp"):
        self.x = x
        self.y = y
        self.dir_x = dir_x
        self.dir_y = dir_y
        self.speed = speed
        self.damage = damage
        self.owner = owner
        self.radius = C.PROJECTILE_RADIUS
        self.alive = True


class Item:
    def __init__(self, kind, x, y):
        self.kind = kind
        self.x = x
        self.y = y
        self.active = True
