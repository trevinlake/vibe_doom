"""Shared helpers for the test-suite."""

import os
import sys

# Make the repository root importable when tests are run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doom.game import Game  # noqa: E402


def make_game(rows, seed=1, name="Test"):
    """Build a Game on a tiny custom ASCII map (see doom/maps.py legend)."""
    g = Game(seed=seed)
    g.load_custom(rows, name=name)
    return g
