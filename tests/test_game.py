import unittest

from tests.helpers import make_game

from doom import constants as C
from doom.game import Game
from doom.maps import LEVELS


class TestGameFlow(unittest.TestCase):
    def test_new_game_initial_state(self):
        g = Game()
        self.assertEqual(g.mode, Game.PLAYING)
        self.assertEqual(g.level_index, 0)
        self.assertEqual(g.player.health, C.PLAYER_MAX_HEALTH)
        self.assertEqual(g.kills, 0)
        self.assertGreater(g.level_monsters, 0)

    def test_complete_level_advances(self):
        g = Game(start_level=0)
        g.complete_level()
        self.assertEqual(g.level_index, 1)
        self.assertEqual(g.mode, Game.PLAYING)

    def test_complete_last_level_wins(self):
        g = Game(start_level=len(LEVELS) - 1)
        g.complete_level()
        self.assertEqual(g.mode, Game.WON)

    def test_loadout_carries_between_levels(self):
        g = Game(start_level=0)
        g.player.health = 37
        g.player.armor = 22
        g.player.weapons.add("chaingun")
        g.player.current_weapon = "chaingun"
        g.player.ammo[C.AMMO_BULLETS] = 111
        g.player.keys.add(C.KEY_RED)
        g.complete_level()
        self.assertEqual(g.player.health, 37)
        self.assertEqual(g.player.armor, 22)
        self.assertIn("chaingun", g.player.weapons)
        self.assertEqual(g.player.ammo[C.AMMO_BULLETS], 111)
        # Keys are level-local in this engine.
        self.assertNotIn(C.KEY_RED, g.player.keys)

    def test_use_exit_switch_completes_level(self):
        g = Game(start_level=len(LEVELS) - 1)
        g.load_custom(["####", "#PX#", "####"])
        self.assertTrue(g.use())
        self.assertEqual(g.mode, Game.WON)

    def test_new_game_resets_after_death(self):
        g = Game()
        g.player.take_damage(1000)
        g.update(0.016)
        self.assertEqual(g.mode, Game.DEAD)
        g.new_game()
        self.assertEqual(g.mode, Game.PLAYING)
        self.assertEqual(g.player.health, C.PLAYER_MAX_HEALTH)
        self.assertEqual(g.level_index, 0)

    def test_update_is_noop_when_not_playing(self):
        g = Game()
        g.mode = Game.WON
        before = (g.player.x, g.player.y)
        g.update(0.1, None)
        self.assertEqual((g.player.x, g.player.y), before)

    def test_weapon_switch_only_to_owned(self):
        g = Game()
        # Slot 3 is the shotgun, which the player does not own yet.
        self.assertFalse(g.switch_weapon(3))
        self.assertEqual(g.player.current_weapon, "pistol")
        # Slot 1 (fist) is always owned.
        self.assertTrue(g.switch_weapon(1))
        self.assertEqual(g.player.current_weapon, "fist")


if __name__ == "__main__":
    unittest.main()
