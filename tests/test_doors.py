import unittest

from tests.helpers import make_game

from doom import constants as C


DOOR = [
    "#####",
    "#PD.#",
    "#####",
]

LOCKED = [
    "#####",
    "#PL.#",
    "#####",
]


def open_fully(game, cell):
    for _ in range(200):
        game._update_doors(0.05)
        if game.doors[cell].passable:
            return True
    return False


class TestDoors(unittest.TestCase):
    def test_closed_door_is_solid(self):
        g = make_game(DOOR)
        self.assertTrue(g.is_solid(2, 1))

    def test_use_opens_door(self):
        g = make_game(DOOR)
        self.assertTrue(g.use())
        self.assertEqual(g.doors[(2, 1)].state, "opening")
        self.assertTrue(open_fully(g, (2, 1)))
        self.assertFalse(g.is_solid(2, 1))

    def test_locked_door_needs_key(self):
        g = make_game(LOCKED)
        self.assertFalse(g.use())
        self.assertIn("RED KEYCARD", g.message)
        self.assertTrue(g.is_solid(2, 1))
        # Grant the key, now it opens.
        g.player.keys.add(C.KEY_RED)
        self.assertTrue(g.use())
        self.assertEqual(g.doors[(2, 1)].state, "opening")

    def test_open_door_auto_closes(self):
        g = make_game(DOOR)
        g.use()
        open_fully(g, (2, 1))
        self.assertTrue(g.doors[(2, 1)].passable)
        # Player is not standing in the doorway, so it should re-close.
        for _ in range(int((C.DOOR_STAY_OPEN + 2.0) / 0.1)):
            g._update_doors(0.1)
        self.assertEqual(g.doors[(2, 1)].state, "closed")

    def test_occupant_keeps_door_open(self):
        g = make_game(DOOR)
        g.use()
        open_fully(g, (2, 1))
        g.player.x, g.player.y = 2.5, 1.5     # stand in the doorway
        for _ in range(int((C.DOOR_STAY_OPEN + 2.0) / 0.1)):
            g._update_doors(0.1)
        self.assertTrue(g.doors[(2, 1)].passable)

    def test_player_passes_through_open_door(self):
        g = make_game(DOOR)
        g.use()
        open_fully(g, (2, 1))
        self.assertFalse(g._blocked(2.5, 1.5, g.player.radius))


if __name__ == "__main__":
    unittest.main()
