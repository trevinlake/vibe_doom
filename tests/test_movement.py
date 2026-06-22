import math
import unittest

from tests.helpers import make_game

from doom.game import Input


ROOM = [
    "#######",
    "#.....#",
    "#.....#",
    "#..P..#",
    "#.....#",
    "#.....#",
    "#######",
]


class TestMovement(unittest.TestCase):
    def test_forward_moves_along_facing(self):
        g = make_game(ROOM)
        g.player.angle = 0.0  # east
        x0 = g.player.x
        g.update(0.1, Input(forward=True))
        self.assertGreater(g.player.x, x0)
        self.assertAlmostEqual(g.player.y, 3.5, places=4)

    def test_wall_blocks_movement(self):
        g = make_game(["#####", "#P..#", "#####"])
        g.player.angle = math.pi  # face west, into the wall
        g.update(0.5, Input(forward=True))
        # Cannot pass through the west wall; stays within its cell.
        self.assertGreaterEqual(g.player.x, 1.0 + g.player.radius - 1e-6)

    def test_wall_sliding(self):
        # Facing into a corner at 45°: should slide along one axis.
        g = make_game(ROOM)
        g.player.x, g.player.y = 1.0 + g.player.radius, 3.5
        g.player.angle = math.radians(135)  # up-left, into the west wall
        y0 = g.player.y
        g.update(0.2, Input(forward=True))
        # Blocked on x (west wall) but free to slide on y.
        self.assertNotAlmostEqual(g.player.y, y0, places=3)

    def test_turning(self):
        g = make_game(ROOM)
        g.player.angle = 0.0
        g.update(0.1, Input(turn_right=True))
        self.assertGreater(g.player.angle, 0.0)
        g.player.angle = 0.0
        g.update(0.1, Input(turn_left=True))
        self.assertLess(g.player.angle, 0.0)

    def test_mouse_turn_applied(self):
        g = make_game(ROOM)
        g.player.angle = 0.0
        g.update(0.016, Input(turn=0.5))
        self.assertAlmostEqual(g.player.angle, 0.5, places=6)

    def test_strafe_is_perpendicular(self):
        g = make_game(ROOM)
        g.player.angle = 0.0  # facing east; strafe right => +y
        y0 = g.player.y
        g.update(0.1, Input(strafe_right=True))
        self.assertGreater(g.player.y, y0)


if __name__ == "__main__":
    unittest.main()
