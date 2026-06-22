# VIBE DOOM — Claude Opus 4.8 build

A from-scratch, **dependency-free** DOOM clone written in pure Python. The whole
game is split into a GUI-free rules engine (fully unit-tested) and a thin
tkinter renderer, so it both *plays* and *tests* with nothing but a stock Python
install — no pygame, no numpy, no pip, no internet.

## Play it

```bash
python play.py
```

Requires only Python 3.x with the standard `tkinter` module (bundled with the
official Windows/macOS installers).

### Controls

| Key | Action |
| --- | --- |
| `W` `S` | move forward / back |
| `A` `D` | strafe left / right |
| `←` `→` | turn (mouse also turns when locked) |
| `M` | toggle mouse-look |
| `Space` / `Ctrl` / left-click | fire |
| `E` | use — open doors, hit the exit switch |
| `1` `2` `3` `4` | fist / pistol / shotgun / chaingun |
| `Esc` | pause |
| `Enter` | start / restart |

**Goal:** clear the demons (or just survive), find the green **EXIT** switch on a
wall, face it and press `E`. Some exits sit behind a locked door — grab the red
keycard first.

## How it recreates DOOM

* **DDA raycaster** — the classic grid raycasting that powers the 2.5-D view,
  with fish-eye correction, per-column wall shading and distance fog.
* **Three weapons + fists** — pistol, 7-pellet shotgun and rapid chaingun, all
  using **hitscan** like the original (the imp's fireball is the one true
  projectile).
* **Three monster archetypes** — the weak hitscan *zombieman*, the fireball-
  lobbing *imp*, and the fast melee *pinky demon*, each with line-of-sight
  vision, chase/attack/pain/death states.
* **Doors & keycards** — sliding doors that auto-close, plus red-key-locked
  doors guarding the exit.
* **Pickups** — medikits, armor, bullets, shells, weapons and the keycard, with
  DOOM-style "don't pick it up if you're already full" behaviour.
* **The status bar** — health / armor / ammo, kill counter, and a procedural
  **DoomGuy face** that grimaces, bleeds and glances toward incoming fire as
  your health drops.
* **A 3-level campaign** — *Hangar → Nuclear Plant → Inferno* — your loadout
  carries between levels.

## Run the tests

The entire simulation is exercised by a standard-library `unittest` suite —
**60 tests, zero dependencies**:

```bash
python run_tests.py
# or:  python -m unittest discover -s tests
```

Coverage spans the map parser, the raycaster (known-distance assertions,
line-of-sight), movement & wall-sliding, hitscan combat & armor, monster AI,
doors & locked doors, every pickup, and level progression / win-lose flow.

Two extra developer checks live under `tools/`:

```bash
python tools/validate_maps.py   # every level is rectangular, has a reachable exit
python tools/smoke_render.py    # the tkinter renderer paints every UI state without error
```

## Project layout

```
doom/              ← pure game logic (no GUI import anywhere)
  constants.py       tunables, weapon/monster tables
  mathutil.py        angle/vector helpers
  maps.py            ASCII level data + parser
  raycaster.py       DDA ray casting + line-of-sight
  entities.py        Player, Monster, Projectile, Item
  game.py            the simulation: Game.update(dt, Input)
play.py            ← tkinter renderer + input (the only GUI file)
tests/             ← unittest suite (the "it can be tested" part)
tools/             ← validate_maps.py, smoke_render.py
run_tests.py       ← one-command test runner
```

The design rule: **`doom/` never imports a GUI toolkit.** That is what makes the
game logic deterministic (seeded RNG) and testable headlessly, while `play.py`
stays a pure view layer.
