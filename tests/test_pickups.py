import unittest

from tests.helpers import make_game

from doom import constants as C


def grab(item_char, mutate=None, seed=1):
    """Build a 1-tile-away pickup scenario and collect it.  Returns the game."""
    g = make_game(["#####", "#P%s.#" % item_char, "#####"], seed=seed)
    if mutate:
        mutate(g)
    g.player.x = 2.0          # within reach of the item at cell-centre 2.5
    g.pick_up_items()
    return g


class TestPickups(unittest.TestCase):
    def test_health(self):
        g = grab("h", mutate=lambda g: setattr(g.player, "health", 50))
        self.assertEqual(g.player.health, 75)
        self.assertFalse(g.items[0].active)

    def test_health_not_taken_when_full(self):
        g = grab("h")  # starts at 100
        self.assertEqual(g.player.health, 100)
        self.assertTrue(g.items[0].active)   # left on the floor

    def test_armor(self):
        g = grab("a")
        self.assertEqual(g.player.armor, C.ARMOR_PICKUP)

    def test_bullets(self):
        start = make_game(["###", "#P#", "###"]).player.ammo[C.AMMO_BULLETS]
        g = grab("b")
        self.assertEqual(g.player.ammo[C.AMMO_BULLETS], start + C.BULLETS_PICKUP)

    def test_shells(self):
        g = grab("s")
        self.assertEqual(g.player.ammo[C.AMMO_SHELLS], C.SHELLS_PICKUP)

    def test_shotgun_weapon(self):
        g = grab("g")
        self.assertIn("shotgun", g.player.weapons)
        self.assertEqual(g.player.current_weapon, "shotgun")
        self.assertGreater(g.player.ammo[C.AMMO_SHELLS], 0)

    def test_chaingun_weapon(self):
        g = grab("c")
        self.assertIn("chaingun", g.player.weapons)
        self.assertEqual(g.player.current_weapon, "chaingun")

    def test_red_key(self):
        g = grab("k")
        self.assertIn(C.KEY_RED, g.player.keys)

    def test_far_item_not_collected(self):
        g = make_game(["######", "#P..h#", "######"])
        g.pick_up_items()
        self.assertTrue(g.items[0].active)


if __name__ == "__main__":
    unittest.main()
