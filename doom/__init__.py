"""vibe_doom — a from-scratch, dependency-free DOOM-like engine.

The :mod:`doom` package contains ONLY pure game logic.  It must never import a
GUI toolkit so that every rule of the game can be exercised by the unit tests in
``tests/`` without a display.  Rendering lives in ``play.py`` (tkinter).
"""

from .game import Game
from .maps import LEVELS, parse_level

__all__ = ["Game", "LEVELS", "parse_level"]
__version__ = "1.0.0"
