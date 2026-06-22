"""Headless-ish smoke test for the tkinter front-end.

Creates the app, drives a handful of frames through every UI state and renders
each one, then tears down — all WITHOUT entering the blocking mainloop.  Catches
typos / bad canvas calls in play.py.  Run:  python tools/smoke_render.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tkinter as tk
except Exception as exc:  # pragma: no cover
    print("tkinter unavailable:", exc)
    raise SystemExit(0)

import play
from doom.game import Game, Input


def main():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print("No display available, skipping GUI smoke test:", exc)
        return 0

    app = play.DoomApp(root)            # renders the title screen once

    # Title screen already rendered in __init__.  Now play a few frames.
    app.state = play.DoomApp.PLAY
    app.game.new_game()
    moves = [
        Input(forward=True),
        Input(turn_right=True, fire=True),
        Input(strafe_right=True),
        Input(use=True),
        Input(weapon_slot=1, fire=True),
    ]
    for i in range(40):
        app.game.update(0.033, moves[i % len(moves)])
        app._render()

    # Force-render the remaining UI states.
    app.state = play.DoomApp.PAUSED
    app._render()

    app.state = play.DoomApp.PLAY
    app.game.player.take_damage(1000)
    app.game.update(0.033)
    app._render()                        # death overlay

    app.game.mode = Game.WON
    app._render()                        # victory overlay

    print("Smoke OK: rendered %d frames + title/pause/death/win states." % 40)
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
