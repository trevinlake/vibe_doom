import unittest

from tests.helpers import make_game


CHASE = [
    "##########",
    "#P......d#",
    "##########",
]

ADJACENT = [
    "#####",
    "#Pd.#",
    "#####",
]

ZOMBIE_LINE = [
    "##########",
    "#P..z....#",
    "##########",
]

HIDDEN = [
    "#######",
    "#P#..d#",
    "#######",
]


class TestMonsters(unittest.TestCase):
    def test_monster_wakes_and_chases(self):
        g = make_game(CHASE)
        demon = g.monsters[0]
        x0 = demon.x
        for _ in range(10):
            g.update(0.1)
        self.assertTrue(demon.awake)
        self.assertLess(demon.x, x0)  # moved toward the player (west)

    def test_demon_melee_hurts_player(self):
        g = make_game(ADJACENT)
        self.assertEqual(g.player.health, 100)
        g.update(0.1)
        self.assertLess(g.player.health, 100)

    def test_zombie_ranged_attack_hits_over_time(self):
        g = make_game(ZOMBIE_LINE, seed=7)
        for _ in range(60):
            g.update(0.1)
            if g.player.health < 100:
                break
        self.assertLess(g.player.health, 100)

    def test_no_line_of_sight_keeps_monster_asleep(self):
        g = make_game(HIDDEN)
        demon = g.monsters[0]
        for _ in range(10):
            g.update(0.1)
        self.assertFalse(demon.awake)
        self.assertEqual(demon.x, 5.5)

    def test_damage_wakes_and_can_kill(self):
        g = make_game(CHASE)
        demon = g.monsters[0]
        g.damage_monster(demon, 5)
        self.assertTrue(demon.awake)
        self.assertGreater(demon.cfg["health"], demon.health)
        self.assertTrue(demon.alive)
        g.damage_monster(demon, 999)
        self.assertFalse(demon.alive)

    def test_dead_monster_does_not_act(self):
        g = make_game(ADJACENT)
        demon = g.monsters[0]
        demon.alive = False
        demon.state = "dead"
        g.update(0.1)
        self.assertEqual(g.player.health, 100)  # corpse can't attack


if __name__ == "__main__":
    unittest.main()
