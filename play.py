#!/usr/bin/env python3
"""vibe_doom — playable front-end (pure-Python, tkinter, zero dependencies).

    python play.py

Controls
--------
    W / S            move forward / back
    A / D            strafe left / right
    Left / Right     turn        (mouse also turns when locked)
    Space / Ctrl     fire
    E                use / open doors / hit exit switch
    1 2 3 4          fist / pistol / shotgun / chaingun
    M                toggle mouse-look
    Esc              pause            Enter   start / restart

All game rules live in the dependency-free :mod:`doom` package (see ``tests/``).
This file only reads that state and paints it with a column-based raycaster.
"""

import math
import time
import tkinter as tk
import tkinter.font as tkfont

from doom import constants as C
from doom.game import Game, Input
from doom.raycaster import cast_ray

# ── Display configuration ─────────────────────────────────────────────────────
WIDTH, HEIGHT = 720, 450
HUD_H = 70
VIEW_H = HEIGHT - HUD_H
HORIZON = VIEW_H // 2
NUM_RAYS = 180                       # vertical wall slices
COL_W = WIDTH / NUM_RAYS
FPS = 30
MOUSE_SENSITIVITY = 0.0025

# Base wall colours keyed by tile code (r, g, b).
WALL_COLORS = {
    C.T_WALL:  (150, 60, 45),
    C.T_WALL2: (70, 95, 120),
    C.T_WALL3: (135, 35, 45),
    C.T_DOOR:  (180, 150, 60),
    C.T_DOOR_LOCKED: (200, 50, 50),
    C.T_EXIT:  (40, 210, 80),
}
CEIL_COLOR = (28, 26, 34)
FLOOR_COLOR = (52, 42, 36)

MONSTER_COLORS = {
    "zombie": (110, 96, 78),
    "imp": (150, 70, 30),
    "demon": (190, 120, 170),
}
ITEM_COLORS = {
    C.ITEM_HEALTH: (235, 60, 60),
    C.ITEM_ARMOR: (70, 150, 235),
    C.ITEM_BULLETS: (210, 190, 90),
    C.ITEM_SHELLS: (210, 150, 70),
    C.ITEM_SHOTGUN: (170, 140, 90),
    C.ITEM_CHAINGUN: (150, 150, 160),
    C.ITEM_KEY_RED: (230, 40, 40),
}


def _hex(r, g, b):
    return "#%02x%02x%02x" % (
        max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))


def _shade(color, factor):
    return _hex(color[0] * factor, color[1] * factor, color[2] * factor)


class DoomApp:
    TITLE, PLAY, PAUSED = "title", "play", "paused"

    def __init__(self, root):
        self.root = root
        root.title("vibe_doom — Opus 4.8")
        root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT,
                                bg="black", highlightthickness=0)
        self.canvas.pack()

        self.font = tkfont.Font(family="Courier New", size=12, weight="bold")
        self.bigfont = tkfont.Font(family="Courier New", size=40, weight="bold")
        self.midfont = tkfont.Font(family="Courier New", size=18, weight="bold")
        self.hudnum = tkfont.Font(family="Courier New", size=22, weight="bold")

        self.game = Game(seed=int(time.time() * 1000) & 0xFFFFFFFF)
        self.state = DoomApp.TITLE
        self.zbuf = [C.WEAPONS["pistol"]["range"]] * NUM_RAYS

        # Input bookkeeping.
        self.pressed = set()
        self.edge_use = False
        self.edge_slot = None
        self.mouse_look = False
        self.mouse_dx = 0.0
        self._ignore_motion = False

        # Persistent canvas items for the static background + wall slices.
        self._build_static_items()

        self._bind()
        self.last = time.perf_counter()
        self.frames = 0
        self.fps_shown = 0
        self.fps_t = self.last
        self._tick()

    # ── canvas item setup ──────────────────────────────────────────────────
    def _build_static_items(self):
        c = self.canvas
        # Ceiling and floor as gradient bands (persistent).
        self.bg_items = []
        bands = 10
        for i in range(bands):
            y0 = HORIZON * i / bands
            y1 = HORIZON * (i + 1) / bands
            f = 0.5 + 0.5 * (i / bands)
            c.create_rectangle(0, y0, WIDTH, y1, width=0,
                               fill=_shade(CEIL_COLOR, f))
        for i in range(bands):
            y0 = HORIZON + VIEW_H / 2 * i / bands
            y1 = HORIZON + VIEW_H / 2 * (i + 1) / bands
            f = 1.0 - 0.5 * (i / bands)
            c.create_rectangle(0, y0, WIDTH, y1, width=0,
                               fill=_shade(FLOOR_COLOR, f))
        # Wall slices: one reusable rectangle per ray.
        self.wall_items = []
        for col in range(NUM_RAYS):
            x = col * COL_W
            item = c.create_rectangle(x, HORIZON, x + COL_W + 1, HORIZON,
                                      width=0, fill="black", state="hidden")
            self.wall_items.append(item)

    # ── input ────────────────────────────────────────────────────────────────
    def _bind(self):
        r = self.root
        r.bind("<KeyPress>", self._on_key_press)
        r.bind("<KeyRelease>", self._on_key_release)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<ButtonRelease-1>", lambda e: self.pressed.discard("fire"))
        self.canvas.bind("<Motion>", self._on_motion)
        # Releasing the OS focus (alt-tab etc.) should drop the mouse lock.
        self.root.bind("<FocusOut>", lambda e: self._set_mouse_look(False))

    def _set_mouse_look(self, on):
        """Lock/unlock mouse-look and reflect it in the cursor."""
        self.mouse_look = on
        self.mouse_dx = 0.0
        try:
            self.canvas.config(cursor="none" if on else "")
        except tk.TclError:
            pass
        if on:
            # Recentre so the first frame doesn't jump.
            self._ignore_motion = True
            self.canvas.event_generate("<Motion>", warp=True,
                                       x=WIDTH // 2, y=VIEW_H // 2)

    def _on_click(self, e):
        # First click locks the mouse (like a browser pointer-lock); once locked
        # a click fires the weapon.
        if self.state == DoomApp.PLAY and not self.mouse_look:
            self._set_mouse_look(True)
        else:
            self.pressed.add("fire")

    def _on_key_press(self, e):
        k = e.keysym.lower()
        if k == "return":
            if self.state == DoomApp.TITLE:
                self._start_game()
            elif self.game.mode in (Game.DEAD, Game.WON):
                self._start_game()
            return
        if k == "escape":
            if self.state == DoomApp.PLAY:
                self._set_mouse_look(False)     # release the mouse on pause
                self.state = DoomApp.PAUSED
            elif self.state == DoomApp.PAUSED:
                self.state = DoomApp.PLAY
            return
        if k == "m":
            self._set_mouse_look(not self.mouse_look)
            return
        if k in ("1", "2", "3", "4"):
            self.edge_slot = int(k)
        if k == "e":
            self.edge_use = True
        self.pressed.add(k)

    def _on_key_release(self, e):
        self.pressed.discard(e.keysym.lower())

    def _on_motion(self, e):
        if self._ignore_motion:
            self._ignore_motion = False
            return
        if self.mouse_look and self.state == DoomApp.PLAY:
            cx = WIDTH // 2
            self.mouse_dx += (e.x - cx)
            # Re-centre the pointer so it never escapes the window.
            self._ignore_motion = True
            self.canvas.event_generate("<Motion>", warp=True, x=cx, y=e.y)

    def _collect_input(self, dt):
        p = self.pressed
        turn = self.mouse_dx * MOUSE_SENSITIVITY
        self.mouse_dx = 0.0
        inp = Input(
            forward="w" in p or "up" in p,
            back="s" in p or "down" in p,
            strafe_left="a" in p,
            strafe_right="d" in p,
            turn_left="left" in p,
            turn_right="right" in p,
            turn=turn,
            fire=("space" in p or "fire" in p or "control_l" in p or "control_r" in p),
            use=self.edge_use,
            weapon_slot=self.edge_slot,
        )
        self.edge_use = False
        self.edge_slot = None
        return inp

    # ── main loop ────────────────────────────────────────────────────────────
    def _start_game(self):
        self.game.new_game()
        self.state = DoomApp.PLAY

    def _tick(self):
        now = time.perf_counter()
        dt = min(now - self.last, 0.1)
        self.last = now

        if self.state == DoomApp.PLAY and self.game.mode == Game.PLAYING:
            self.game.update(dt, self._collect_input(dt))

        self._render()

        self.frames += 1
        if now - self.fps_t >= 1.0:
            self.fps_shown = self.frames
            self.frames = 0
            self.fps_t = now

        self.root.after(int(1000 / FPS), self._tick)

    # ── rendering ────────────────────────────────────────────────────────────
    def _render(self):
        c = self.canvas
        c.delete("overlay")           # dynamic items (sprites, weapon, hud, menus)

        if self.state == DoomApp.TITLE:
            self._hide_walls()
            self._draw_title()
            return

        # Drop the mouse lock automatically whenever we're not actively playing.
        if self.mouse_look and (self.state != DoomApp.PLAY
                                or self.game.mode != Game.PLAYING):
            self._set_mouse_look(False)

        self._render_world()
        self._draw_weapon()
        self._draw_hud()
        self._draw_mouse_hint()

        if self.state == DoomApp.PAUSED:
            self._draw_center_panel("PAUSED", "Press ESC to resume", (200, 200, 60))
        elif self.game.mode == Game.DEAD:
            self._draw_center_panel("YOU DIED", "Press ENTER to try again", (220, 40, 40))
        elif self.game.mode == Game.WON:
            self._draw_center_panel("VICTORY!", "All levels cleared — ENTER to replay",
                                    (60, 220, 90))

    def _draw_mouse_hint(self):
        if self.state != DoomApp.PLAY or self.game.mode != Game.PLAYING:
            return
        c = self.canvas
        if not self.mouse_look:
            c.create_rectangle(WIDTH / 2 - 150, VIEW_H - 40, WIDTH / 2 + 150,
                               VIEW_H - 14, fill="#000000", stipple="gray50",
                               width=0, tags="overlay")
            c.create_text(WIDTH / 2, VIEW_H - 27,
                          text="CLICK TO LOCK MOUSE   ·   M toggles   ·   ←/→ also turn",
                          fill="#e0c040", font=self.font, tags="overlay")
        else:
            c.create_text(WIDTH - 14, 16, text="MOUSE LOCKED — ESC to release",
                          fill="#9a9aa5", font=self.font, anchor="e", tags="overlay")

    def _hide_walls(self):
        for item in self.wall_items:
            self.canvas.itemconfig(item, state="hidden")

    def _render_world(self):
        g = self.game
        p = g.player
        c = self.canvas
        half_fov = C.FOV / 2
        tan_half = math.tan(half_fov)

        # 1) Walls — one DDA ray per slice, flat-shaded by distance/side/type.
        for col in range(NUM_RAYS):
            cam_x = 2.0 * col / NUM_RAYS - 1.0       # -1 .. 1 across the screen
            ray_ang = p.angle + math.atan(cam_x * tan_half)
            dir_x, dir_y = math.cos(ray_ang), math.sin(ray_ang)
            hit = cast_ray(g.is_solid, p.x, p.y, dir_x, dir_y,
                           max_dist=40.0, tile_at=g.tile_at)
            # Remove fish-eye: project onto the camera forward axis.
            perp = max(0.05, hit.dist * math.cos(ray_ang - p.angle))
            self.zbuf[col] = perp

            item = self.wall_items[col]
            if not hit.hit:
                c.itemconfig(item, state="hidden")
                continue
            wall_h = min(VIEW_H * 3, VIEW_H / perp)
            y0 = HORIZON - wall_h / 2
            y1 = HORIZON + wall_h / 2
            base = WALL_COLORS.get(hit.tile, (160, 160, 160))
            fog = max(0.18, min(1.0, 3.4 / (perp + 0.4)))
            if hit.side == 1:
                fog *= 0.7                            # darken EW faces
            x = col * COL_W
            c.coords(item, x, y0, x + COL_W + 1, y1)
            c.itemconfig(item, fill=_shade(base, fog), state="normal")

        # 2) Sprites — monsters, items, projectiles — far to near, z-tested.
        sprites = []
        for m in g.monsters:
            sprites.append(("monster", m))
        for it in g.items:
            if it.active:
                sprites.append(("item", it))
        for pr in g.projectiles:
            sprites.append(("proj", pr))

        def dist2(s):
            e = s[1]
            return (e.x - p.x) ** 2 + (e.y - p.y) ** 2
        sprites.sort(key=dist2, reverse=True)

        for kind, e in sprites:
            self._draw_sprite(kind, e, p, tan_half)

    def _draw_sprite(self, kind, e, p, tan_half):
        c = self.canvas
        dx, dy = e.x - p.x, e.y - p.y
        dist = math.hypot(dx, dy)
        if dist < 0.2:
            return
        rel = math.atan2(dy, dx) - p.angle
        while rel > math.pi:
            rel -= 2 * math.pi
        while rel < -math.pi:
            rel += 2 * math.pi
        if abs(rel) > C.FOV / 2 + 0.4:
            return
        screen_x = WIDTH / 2 * (1 + math.tan(rel) / tan_half)
        col = int(screen_x / COL_W)
        if 0 <= col < NUM_RAYS and self.zbuf[col] < dist - 0.1:
            return                                    # occluded by a wall

        if kind == "monster":
            self._draw_monster(e, dist, screen_x)
        elif kind == "item":
            self._draw_item(e, dist, screen_x)
        else:
            self._draw_projectile(e, dist, screen_x)

    def _draw_monster(self, m, dist, sx):
        c = self.canvas
        h = min(VIEW_H * 2.5, VIEW_H / dist)
        w = h * 0.6
        bottom = HORIZON + h / 2
        fog = max(0.25, min(1.0, 3.4 / (dist + 0.4)))
        base = MONSTER_COLORS.get(m.type, (180, 180, 180))
        if not m.alive:
            # Corpse: a flattened dark heap on the floor.
            color = _shade(base, fog * 0.45)
            c.create_oval(sx - w / 2, bottom - h * 0.18, sx + w / 2, bottom,
                          fill=color, width=0, tags="overlay")
            return
        body = _shade(base, fog)
        # Flash white briefly when in the pain state.
        if m.state == "pain":
            body = "#ffffff"
        top = bottom - h
        # Torso.
        c.create_rectangle(sx - w / 2, top + h * 0.30, sx + w / 2, bottom,
                           fill=body, width=0, tags="overlay")
        # Head.
        c.create_oval(sx - w * 0.32, top, sx + w * 0.32, top + h * 0.34,
                      fill=body, width=0, tags="overlay")
        # Glowing eyes.
        eye = _shade((255, 230, 40) if m.type != "demon" else (255, 80, 80), 1.0)
        ew = max(1, w * 0.10)
        ey = top + h * 0.14
        c.create_oval(sx - w * 0.18 - ew, ey, sx - w * 0.18 + ew, ey + ew * 2,
                      fill=eye, width=0, tags="overlay")
        c.create_oval(sx + w * 0.18 - ew, ey, sx + w * 0.18 + ew, ey + ew * 2,
                      fill=eye, width=0, tags="overlay")

    def _draw_item(self, it, dist, sx):
        c = self.canvas
        h = min(VIEW_H, VIEW_H / dist) * 0.45
        bottom = HORIZON + min(VIEW_H * 2.5, VIEW_H / dist) / 2
        fog = max(0.35, min(1.0, 3.4 / (dist + 0.4)))
        color = _shade(ITEM_COLORS.get(it.kind, (220, 220, 220)), fog)
        top = bottom - h
        c.create_rectangle(sx - h * 0.35, top, sx + h * 0.35, bottom,
                           fill=color, width=0, tags="overlay")
        # A little highlight pip so pickups read as "glowing".
        c.create_rectangle(sx - h * 0.12, top + h * 0.2, sx + h * 0.12, top + h * 0.5,
                           fill="#ffffff", width=0, tags="overlay")

    def _draw_projectile(self, pr, dist, sx):
        c = self.canvas
        r = max(2, min(VIEW_H * 0.4, VIEW_H / dist) * 0.12)
        c.create_oval(sx - r, HORIZON - r, sx + r, HORIZON + r,
                      fill="#ffcc33", width=0, tags="overlay")
        c.create_oval(sx - r * 0.5, HORIZON - r * 0.5, sx + r * 0.5, HORIZON + r * 0.5,
                      fill="#ff6611", width=0, tags="overlay")

    # ── weapon viewmodel ──────────────────────────────────────────────────────
    def _draw_weapon(self):
        c = self.canvas
        g = self.game
        p = g.player
        cx = WIDTH / 2
        bob = math.sin(p.bob * 6.0) * 6
        base_y = VIEW_H + 8 + abs(bob)
        wk = p.current_weapon

        # Muzzle flash.
        if p.muzzle_flash > 0:
            fr = 26 * p.muzzle_flash
            c.create_oval(cx - fr, base_y - 150, cx + fr, base_y - 150 + 2 * fr,
                          fill="#ffe066", width=0, tags="overlay")

        if wk == "fist":
            c.create_oval(cx + 40, base_y - 40, cx + 120, base_y + 60,
                          fill="#caa48b", width=0, tags="overlay")
        elif wk == "shotgun":
            c.create_rectangle(cx - 14, base_y - 150, cx + 14, base_y,
                               fill="#6b5436", width=0, tags="overlay")
            c.create_rectangle(cx - 8, base_y - 150, cx + 8, base_y - 60,
                               fill="#3a3a3a", width=0, tags="overlay")
        elif wk == "chaingun":
            for off in (-12, 0, 12):
                c.create_rectangle(cx + off - 4, base_y - 150, cx + off + 4, base_y - 40,
                                   fill="#888", width=0, tags="overlay")
            c.create_rectangle(cx - 26, base_y - 50, cx + 26, base_y,
                               fill="#444", width=0, tags="overlay")
        else:  # pistol
            c.create_rectangle(cx - 8, base_y - 130, cx + 8, base_y - 30,
                               fill="#555", width=0, tags="overlay")
            c.create_rectangle(cx - 14, base_y - 40, cx + 14, base_y + 20,
                               fill="#333", width=0, tags="overlay")

        # Crosshair.
        c.create_line(cx - 9, HORIZON, cx + 9, HORIZON, fill="#ffffff", tags="overlay")
        c.create_line(cx, HORIZON - 9, cx, HORIZON + 9, fill="#ffffff", tags="overlay")

        # Damage flash tint over the whole viewport.
        if p.damage_flash > 0:
            alpha = min(1.0, p.damage_flash)
            stipple = "gray50" if alpha > 0.5 else "gray25"
            c.create_rectangle(0, 0, WIDTH, VIEW_H, fill="#aa0000",
                               stipple=stipple, width=0, tags="overlay")

        if g.message:
            c.create_text(WIDTH / 2, 24, text=g.message, fill="#ffe066",
                          font=self.midfont, tags="overlay")

    # ── status bar + DOOM face ────────────────────────────────────────────────
    def _draw_hud(self):
        c = self.canvas
        g = self.game
        p = g.player
        y = VIEW_H
        c.create_rectangle(0, y, WIDTH, HEIGHT, fill="#1b1b22", width=0, tags="overlay")
        c.create_line(0, y, WIDTH, y, fill="#000000", tags="overlay")

        def label(x, title, value, color):
            c.create_text(x, y + 18, text=title, fill="#9a9aa5",
                          font=self.font, anchor="w", tags="overlay")
            c.create_text(x, y + 44, text=value, fill=_hex(*color),
                          font=self.hudnum, anchor="w", tags="overlay")

        hp = p.health
        hp_color = (90, 220, 90) if hp > 50 else (230, 200, 60) if hp > 25 else (230, 50, 50)
        label(20, "HEALTH", "%d%%" % hp, hp_color)
        label(150, "ARMOR", "%d%%" % p.armor, (120, 170, 235))

        ammo = p.current_ammo()
        ammo_txt = "--" if ammo is None else str(ammo)
        label(300, C.WEAPONS[p.current_weapon]["name"].upper(), ammo_txt, (235, 200, 90))

        # Kills / level on the right.
        c.create_text(WIDTH - 20, y + 18,
                      text="LEVEL %d/%d  %s" % (g.level_index + 1, 3, g.level_name.upper()),
                      fill="#9a9aa5", font=self.font, anchor="e", tags="overlay")
        c.create_text(WIDTH - 20, y + 44,
                      text="KILLS %d/%d" % (g.kills, g.level_monsters),
                      fill="#cfcfd6", font=self.font, anchor="e", tags="overlay")

        # Red keycard indicator.
        if C.KEY_RED in p.keys:
            c.create_rectangle(WIDTH - 150, y + 10, WIDTH - 130, y + 28,
                               fill="#e02828", width=0, tags="overlay")

        self._draw_face(WIDTH / 2 + 40, y + HUD_H / 2, hp, p)

    def _draw_face(self, cx, cy, hp, p):
        """A tiny procedural DoomGuy whose mood tracks remaining health."""
        c = self.canvas
        s = 26
        # Skin.
        skin = "#d7a06a" if hp > 0 else "#7a5a3a"
        c.create_rectangle(cx - s, cy - s, cx + s, cy + s, fill=skin,
                           width=0, tags="overlay")
        # Hair.
        c.create_rectangle(cx - s, cy - s, cx + s, cy - s + 8, fill="#5a3a1a",
                           width=0, tags="overlay")
        # Eyes — look toward the last damage direction.
        look = 0
        if p.damage_flash > 0:
            look = 4 if math.sin(p.last_damage_dir) > 0 else -4
        for ex in (-10, 10):
            c.create_rectangle(cx + ex - 5 + look, cy - 6, cx + ex + 5 + look, cy + 2,
                               fill="#ffffff", width=0, tags="overlay")
            c.create_rectangle(cx + ex - 2 + look, cy - 4, cx + ex + 2 + look, cy,
                               fill="#0a0a0a", width=0, tags="overlay")
        # Mouth: grin when healthy, grimace when hurt.
        if hp > 66:
            c.create_rectangle(cx - 10, cy + 8, cx + 10, cy + 13, fill="#5a2a2a",
                               width=0, tags="overlay")
        elif hp > 33:
            c.create_rectangle(cx - 8, cy + 9, cx + 8, cy + 12, fill="#3a1a1a",
                               width=0, tags="overlay")
        else:
            c.create_oval(cx - 7, cy + 7, cx + 7, cy + 15, fill="#2a0a0a",
                          width=0, tags="overlay")
        # Blood when badly hurt.
        if hp <= 40 and hp > 0:
            c.create_rectangle(cx - s, cy - s, cx - s + 6, cy + 4, fill="#aa1010",
                               width=0, tags="overlay")
        c.create_rectangle(cx - s - 2, cy - s - 2, cx + s + 2, cy + s + 2,
                           outline="#000000", width=2, tags="overlay")

    # ── menus / overlays ──────────────────────────────────────────────────────
    def _draw_title(self):
        c = self.canvas
        c.create_rectangle(0, 0, WIDTH, HEIGHT, fill="#0a0608", width=0, tags="overlay")
        c.create_text(WIDTH / 2, HEIGHT / 2 - 90, text="VIBE DOOM", fill="#c0392b",
                      font=self.bigfont, tags="overlay")
        c.create_text(WIDTH / 2, HEIGHT / 2 - 48, text="recreated by Claude Opus 4.8",
                      fill="#6a6a6a", font=self.font, tags="overlay")
        lines = [
            "WASD move    ←/→ turn    CLICK to lock mouse-look (M or ESC to release)",
            "SPACE/CTRL/CLICK fire    E use/open    1-4 weapons",
            "Reach the green EXIT switch and USE it to advance.",
            "",
            "PRESS ENTER TO START",
        ]
        for i, ln in enumerate(lines):
            col = "#cfcfd6" if i < 3 else "#e0c040"
            c.create_text(WIDTH / 2, HEIGHT / 2 + i * 26, text=ln, fill=col,
                          font=self.font, tags="overlay")

    def _draw_center_panel(self, title, subtitle, color):
        c = self.canvas
        c.create_rectangle(0, VIEW_H / 2 - 70, WIDTH, VIEW_H / 2 + 70,
                           fill="#000000", stipple="gray50", width=0, tags="overlay")
        c.create_text(WIDTH / 2, VIEW_H / 2 - 20, text=title, fill=_hex(*color),
                      font=self.bigfont, tags="overlay")
        c.create_text(WIDTH / 2, VIEW_H / 2 + 30, text=subtitle, fill="#dddddd",
                      font=self.font, tags="overlay")


def main():
    root = tk.Tk()
    DoomApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
