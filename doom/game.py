"""The authoritative game simulation.

Everything that decides *what happens* lives here and nowhere else.  The class
is GUI-free: feed it an :class:`Input` snapshot and a time delta and it advances
the world.  The renderer only ever *reads* this state.

``Game.update(dt, inp)`` is the single entry point used by the front-end, but
every meaningful action (:meth:`fire_weapon`, :meth:`use`, :meth:`try_move`,
:meth:`pick_up_items`, ...) is also a public method so the tests can drive the
simulation one deterministic step at a time.
"""

import math
import random

from . import constants as C
from .entities import Item, Monster, Player, Projectile
from .maps import LEVELS, parse_level
from .mathutil import clamp, normalize_angle
from .raycaster import cast_ray, line_of_sight


class Input:
    """A snapshot of player intent for a single frame.

    ``turn`` is an absolute angular delta (radians) typically produced by the
    mouse; ``turn_left``/``turn_right`` are the keyboard equivalents scaled by
    :data:`constants.TURN_SPEED`.  ``use`` and ``weapon_slot`` are edge-triggered
    (set only on the frame the key is pressed).
    """

    __slots__ = (
        "forward", "back", "strafe_left", "strafe_right",
        "turn_left", "turn_right", "turn", "fire", "use", "weapon_slot",
    )

    def __init__(self, forward=False, back=False, strafe_left=False,
                 strafe_right=False, turn_left=False, turn_right=False,
                 turn=0.0, fire=False, use=False, weapon_slot=None):
        self.forward = forward
        self.back = back
        self.strafe_left = strafe_left
        self.strafe_right = strafe_right
        self.turn_left = turn_left
        self.turn_right = turn_right
        self.turn = turn
        self.fire = fire
        self.use = use
        self.weapon_slot = weapon_slot


class Door:
    """Animation/occupancy state for a single door cell."""

    def __init__(self, tile):
        self.tile = tile                       # T_DOOR or T_DOOR_LOCKED
        self.locked = tile == C.T_DOOR_LOCKED
        self.state = "closed"                  # closed|opening|open|closing
        self.openness = 0.0                    # 0 == shut, 1 == fully open
        self.stay_timer = 0.0

    @property
    def passable(self):
        return self.openness >= 0.999


class Game:
    # Game-wide mode.
    PLAYING = "playing"
    DEAD = "dead"
    WON = "won"

    def __init__(self, seed=1234, start_level=0):
        self.rng = random.Random(seed)
        self.start_level = start_level
        self.new_game()

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def new_game(self):
        self.mode = Game.PLAYING
        self.kills = 0
        self.total_kills = 0
        self.time = 0.0
        self.message = ""
        self.message_time = 0.0
        self._player_template = None
        self.load_level(self.start_level, carry_player=False)

    def load_level(self, index, carry_player=True):
        self.level_index = index
        self._install_level(parse_level(LEVELS[index]["rows"]),
                            LEVELS[index]["name"], carry_player,
                            C.difficulty_for(index))

    def load_custom(self, rows, name="Test", carry_player=False, difficulty=None):
        """Load an arbitrary ASCII map.  Used by the tests to build tiny,
        fully-controlled worlds; ``level_index`` is left untouched and monsters
        spawn at neutral difficulty unless one is supplied."""
        self._install_level(parse_level(rows), name, carry_player,
                            difficulty or C.NEUTRAL_DIFFICULTY)

    def _install_level(self, level, name, carry_player, difficulty):
        self.level_name = name
        self.difficulty = difficulty
        self.grid = level["grid"]
        self.width = level["width"]
        self.height = level["height"]

        px, py, pa = level["player_start"]
        if carry_player and getattr(self, "player", None) is not None:
            # Preserve the player's loadout between levels, reposition them.
            old = self.player
            self.player = Player(px, py, pa)
            self.player.health = old.health
            self.player.armor = old.armor
            self.player.weapons = set(old.weapons)
            self.player.current_weapon = old.current_weapon
            self.player.ammo = dict(old.ammo)
            # Keys do NOT carry between levels (each level is self-contained).
        else:
            self.player = Player(px, py, pa)

        self.doors = {}
        for y in range(self.height):
            for x in range(self.width):
                if self.grid[y][x] in C.DOOR_TILES:
                    self.doors[(x, y)] = Door(self.grid[y][x])

        self.monsters = [Monster(mt, mx, my, difficulty)
                         for (mt, mx, my) in level["monsters"]]
        self.items = [Item(kind, ix, iy) for (kind, ix, iy) in level["items"]]
        self.projectiles = []
        self.level_monsters = len(self.monsters)
        self.kills = 0

    # ── world queries ─────────────────────────────────────────────────────────
    def tile_at(self, x, y):
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.grid[y][x]
        return C.T_WALL

    def is_solid(self, x, y):
        """True if cell ``(x, y)`` blocks movement and rays right now."""
        t = self.tile_at(x, y)
        if t in C.WALL_TILES or t == C.T_EXIT:
            return True
        if t in C.DOOR_TILES:
            door = self.doors.get((x, y))
            return not (door and door.passable)
        return False

    def _blocked(self, x, y, r):
        """Circle/grid overlap test for an entity of radius ``r`` at ``(x, y)``."""
        for cx in (x - r, x + r):
            for cy in (y - r, y + r):
                if self.is_solid(int(math.floor(cx)), int(math.floor(cy))):
                    return True
        return False

    def try_move(self, ent, dx, dy):
        """Move ``ent`` by ``(dx, dy)`` with wall sliding.  Returns True if it
        moved on at least one axis."""
        moved = False
        r = ent.radius
        nx = ent.x + dx
        if not self._blocked(nx, ent.y, r):
            ent.x = nx
            moved = True
        ny = ent.y + dy
        if not self._blocked(ent.x, ny, r):
            ent.y = ny
            moved = True
        return moved

    # ── top-level update ────────────────────────────────────────────────────
    def update(self, dt, inp=None):
        if self.mode != Game.PLAYING:
            return
        if dt <= 0:
            return
        inp = inp or Input()
        self.time += dt

        if self.message_time > 0:
            self.message_time = max(0.0, self.message_time - dt)
            if self.message_time == 0:
                self.message = ""

        self._update_player(dt, inp)
        self._update_doors(dt)
        self._update_monsters(dt)
        self._update_projectiles(dt)
        self.pick_up_items()

        if self.player.weapon_cooldown > 0:
            self.player.weapon_cooldown = max(0.0, self.player.weapon_cooldown - dt)
        for t in ("muzzle_flash", "damage_flash"):
            v = getattr(self.player, t)
            if v > 0:
                setattr(self.player, t, max(0.0, v - dt * 3.0))

        if not self.player.alive:
            self.mode = Game.DEAD

    # ── player ────────────────────────────────────────────────────────────────
    def _update_player(self, dt, inp):
        p = self.player

        if inp.weapon_slot is not None:
            self.switch_weapon(inp.weapon_slot)

        # Rotation: keyboard turn + raw mouse delta.
        p.angle = normalize_angle(
            p.angle
            + (inp.turn_right - inp.turn_left) * C.TURN_SPEED * dt
            + inp.turn
        )

        # Movement relative to facing.
        fwd = (inp.forward - inp.back)
        strafe = (inp.strafe_right - inp.strafe_left)
        if fwd or strafe:
            cos_a, sin_a = math.cos(p.angle), math.sin(p.angle)
            move_x = (cos_a * fwd - sin_a * strafe)
            move_y = (sin_a * fwd + cos_a * strafe)
            mag = math.hypot(move_x, move_y)
            if mag > 0:
                move_x, move_y = move_x / mag, move_y / mag
            step = C.MOVE_SPEED * dt
            self.try_move(p, move_x * step, move_y * step)
            p.bob += step

        if inp.use:
            self.use()
        if inp.fire:
            self.fire_weapon()

    def switch_weapon(self, slot):
        for key, cfg in C.WEAPONS.items():
            if cfg["slot"] == slot and key in self.player.weapons:
                if self.player.current_weapon != key:
                    self.player.current_weapon = key
                    self.player.weapon_cooldown = max(self.player.weapon_cooldown, 0.2)
                return True
        return False

    def fire_weapon(self):
        """Fire the current weapon if it is ready.  Returns True if it fired."""
        p = self.player
        if not p.alive or p.weapon_cooldown > 0:
            return False
        w = C.WEAPONS[p.current_weapon]
        ammo_type = w["ammo"]
        if ammo_type is not None:
            if p.ammo.get(ammo_type, 0) <= 0:
                self.set_message("OUT OF AMMO")
                # Fall back to the pistol/fist if we can.
                self._auto_switch_on_empty()
                return False
            p.ammo[ammo_type] -= 1

        p.weapon_cooldown = w["cooldown"]
        p.muzzle_flash = 1.0

        for _ in range(w["pellets"]):
            spread = w["spread"]
            angle = p.angle + (self.rng.uniform(-spread, spread) if spread else 0.0)
            self._hitscan(angle, w["range"], w["damage"])
        return True

    def _auto_switch_on_empty(self):
        p = self.player
        for key in ("chaingun", "pistol", "fist"):
            if key in p.weapons and key != p.current_weapon:
                ammo = C.WEAPONS[key]["ammo"]
                if ammo is None or p.ammo.get(ammo, 0) > 0:
                    p.current_weapon = key
                    return

    def _hitscan(self, angle, max_range, damage_range):
        """Trace a bullet; damage the nearest monster the ray reaches first."""
        p = self.player
        dir_x, dir_y = math.cos(angle), math.sin(angle)
        wall = cast_ray(self.is_solid, p.x, p.y, dir_x, dir_y, max_dist=max_range)
        reach = min(wall.dist, max_range)

        best = None
        best_t = reach
        for m in self.monsters:
            if not m.alive:
                continue
            ox, oy = m.x - p.x, m.y - p.y
            t = ox * dir_x + oy * dir_y           # projection onto the ray
            if t <= 0 or t > best_t:
                continue
            # Perpendicular distance from the monster centre to the ray.
            perp = abs(ox * dir_y - oy * dir_x)
            if perp <= m.radius:
                best = m
                best_t = t
        if best is not None:
            dmg = self.rng.randint(*damage_range)
            self.damage_monster(best, dmg)

    def damage_monster(self, monster, dmg):
        was_alive = monster.alive
        monster.take_damage(dmg, self.rng)
        if was_alive and not monster.alive:
            self.kills += 1
            self.total_kills += 1
            self.set_message("MONSTER DOWN")

    # ── USE: doors & exit switch ───────────────────────────────────────────────
    def use(self):
        """Activate whatever solid surface the player faces (door or exit)."""
        p = self.player
        dir_x, dir_y = math.cos(p.angle), math.sin(p.angle)
        hit = cast_ray(self.is_solid, p.x, p.y, dir_x, dir_y,
                       max_dist=C.USE_RANGE, tile_at=self.tile_at)
        if not hit.hit:
            return False
        key = (hit.map_x, hit.map_y)
        if hit.tile in C.DOOR_TILES:
            return self._open_door(key)
        if hit.tile == C.T_EXIT:
            self.complete_level()
            return True
        return False

    def _open_door(self, key):
        door = self.doors.get(key)
        if door is None:
            return False
        if door.locked and C.KEY_RED not in self.player.keys:
            self.set_message("YOU NEED THE RED KEYCARD")
            return False
        if door.state in ("closed", "closing"):
            door.state = "opening"
            self.set_message("")
        return True

    def _update_doors(self, dt):
        for (x, y), door in self.doors.items():
            if door.state == "opening":
                door.openness = min(1.0, door.openness + C.DOOR_SPEED * dt)
                if door.openness >= 1.0:
                    door.state = "open"
                    door.stay_timer = C.DOOR_STAY_OPEN
            elif door.state == "open":
                door.stay_timer -= dt
                if door.stay_timer <= 0 and not self._cell_occupied(x, y):
                    door.state = "closing"
            elif door.state == "closing":
                if self._cell_occupied(x, y):       # don't crush anyone
                    door.state = "opening"
                    continue
                door.openness = max(0.0, door.openness - C.DOOR_SPEED * dt)
                if door.openness <= 0.0:
                    door.state = "closed"

    def _cell_occupied(self, x, y):
        for ent in [self.player] + [m for m in self.monsters if m.alive]:
            if int(math.floor(ent.x)) == x and int(math.floor(ent.y)) == y:
                return True
        return False

    # ── monsters ────────────────────────────────────────────────────────────
    def _update_monsters(self, dt):
        p = self.player
        for m in self.monsters:
            m.anim_time += dt
            if not m.alive:
                m.state_time += dt
                continue
            if m.attack_cooldown > 0:
                m.attack_cooldown = max(0.0, m.attack_cooldown - dt)

            dx, dy = p.x - m.x, p.y - m.y
            dist = math.hypot(dx, dy)
            sees = dist <= m.cfg["sight"] and line_of_sight(self.is_solid, m.x, m.y, p.x, p.y)
            if sees:
                m.awake = True
            if not m.awake:
                continue

            m.angle = math.atan2(dy, dx)

            if m.state == "pain":
                m.state_time += dt
                if m.state_time > 0.18:
                    m.state = "chase"
                    m.state_time = 0.0
                continue

            self._monster_act(m, dt, dist, sees)

    def _monster_act(self, m, dt, dist, sees):
        cfg = m.cfg
        p = self.player
        melee_reach = C.MONSTER_MELEE_REACH + p.radius

        # Melee attack (demon always, imp up close).
        if cfg["melee"] and dist <= melee_reach and m.attack_cooldown <= 0:
            m.state = "attack"
            m.state_time = 0.0
            m.attack_cooldown = cfg["attack_cooldown"]
            lo, hi = cfg.get("melee_damage", cfg["damage"])
            self._hurt_player(self.rng.randint(lo, hi), m)
            return

        # Ranged attack (zombie hitscan, imp fireball).
        if cfg["ranged"] and sees and dist <= cfg["attack_range"] and m.attack_cooldown <= 0:
            m.state = "attack"
            m.state_time = 0.0
            m.attack_cooldown = cfg["attack_cooldown"]
            if cfg["hitscan"]:
                self._monster_hitscan(m, dist)
            else:
                self._spawn_fireball(m)
            return

        # Otherwise close the distance.
        m.state = "chase"
        self._chase(m, dt)

    def _chase(self, m, dt):
        p = self.player
        dx, dy = p.x - m.x, p.y - m.y
        dist = math.hypot(dx, dy) or 1.0
        step = m.speed * dt
        moved = self.try_move(m, dx / dist * step, dy / dist * step)
        if not moved:
            # Nudge around a corner by trying a perpendicular slide.
            perp = self.rng.choice((1.0, -1.0))
            self.try_move(m, -dy / dist * step * perp, dx / dist * step * perp)

    def _monster_hitscan(self, m, dist):
        # Accuracy falls off with range; armor still mitigates on the player side.
        acc = clamp(1.0 - dist / (m.cfg["attack_range"] * 1.6), 0.25, 0.92)
        if self.rng.random() <= acc:
            lo, hi = m.cfg["damage"]
            self._hurt_player(self.rng.randint(lo, hi), m)

    def _spawn_fireball(self, m):
        p = self.player
        dx, dy = p.x - m.x, p.y - m.y
        d = math.hypot(dx, dy) or 1.0
        speed = m.cfg.get("projectile_speed", 5.0)
        lo, hi = m.cfg["damage"]
        # Damage is rolled on impact; store the range mid-point bound now.
        proj = Projectile(m.x, m.y, dx / d, dy / d, speed,
                          damage=(lo, hi), owner=m.type)
        self.projectiles.append(proj)

    def _hurt_player(self, dmg, source):
        ang = math.atan2(source.y - self.player.y, source.x - self.player.x)
        self.player.take_damage(dmg, ang)

    # ── projectiles ───────────────────────────────────────────────────────────
    def _update_projectiles(self, dt):
        p = self.player
        alive = []
        for pr in self.projectiles:
            if not pr.alive:
                continue
            # Sub-step the motion so fast fireballs cannot tunnel through walls.
            steps = max(1, int(pr.speed * dt / 0.1) + 1)
            sub = dt / steps
            for _ in range(steps):
                pr.x += pr.dir_x * pr.speed * sub
                pr.y += pr.dir_y * pr.speed * sub
                if self.is_solid(int(math.floor(pr.x)), int(math.floor(pr.y))):
                    pr.alive = False
                    break
                if math.hypot(pr.x - p.x, pr.y - p.y) <= pr.radius + p.radius:
                    lo, hi = pr.damage
                    self._hurt_player(self.rng.randint(lo, hi), pr)
                    pr.alive = False
                    break
            if pr.alive:
                alive.append(pr)
        self.projectiles = alive

    # ── items ───────────────────────────────────────────────────────────────
    def pick_up_items(self):
        p = self.player
        reach = C.ITEM_RADIUS + p.radius
        for it in self.items:
            if not it.active:
                continue
            if math.hypot(it.x - p.x, it.y - p.y) > reach:
                continue
            if self._grant_item(it.kind):
                it.active = False

    def _grant_item(self, kind):
        p = self.player
        if kind == C.ITEM_HEALTH:
            if p.give_health(C.HEALTH_PICKUP):
                self.set_message("PICKED UP A MEDIKIT")
                return True
            return False
        if kind == C.ITEM_ARMOR:
            if p.give_armor(C.ARMOR_PICKUP):
                self.set_message("PICKED UP ARMOR")
                return True
            return False
        if kind == C.ITEM_BULLETS:
            if p.give_ammo(C.AMMO_BULLETS, C.BULLETS_PICKUP):
                self.set_message("PICKED UP BULLETS")
                return True
            return False
        if kind == C.ITEM_SHELLS:
            if p.give_ammo(C.AMMO_SHELLS, C.SHELLS_PICKUP):
                self.set_message("PICKED UP SHELLS")
                return True
            return False
        if kind == C.ITEM_SHOTGUN:
            p.give_weapon("shotgun")
            p.give_ammo(C.AMMO_SHELLS, C.SHELLS_PICKUP)
            self.set_message("YOU GOT THE SHOTGUN")
            return True
        if kind == C.ITEM_CHAINGUN:
            p.give_weapon("chaingun")
            p.give_ammo(C.AMMO_BULLETS, C.BULLETS_PICKUP)
            self.set_message("YOU GOT THE CHAINGUN")
            return True
        if kind == C.ITEM_KEY_RED:
            p.give_key(C.KEY_RED)
            self.set_message("PICKED UP THE RED KEYCARD")
            return True
        return False

    # ── level flow ────────────────────────────────────────────────────────────
    def complete_level(self):
        if self.level_index + 1 < len(LEVELS):
            self.load_level(self.level_index + 1, carry_player=True)
            self.set_message("ENTERING %s" % self.level_name.upper())
        else:
            self.mode = Game.WON

    def set_message(self, text, duration=3.0):
        self.message = text
        self.message_time = duration if text else 0.0
