import unittest

from tests.helpers import make_game

from doom import constants as C


# Player faces east (start angle 0); a zombie stands 3 tiles ahead in the clear.
LINE = [
    "##########",
    "#P..z....#",
    "##########",
]

# A wall sits between the player and the zombie.
BLOCKED = [
    "######",
    "#P#z.#",
    "######",
]


class TestCombat(unittest.TestCase):
    def test_fire_consumes_ammo_and_sets_cooldown(self):
        g = make_game(LINE)
        g.player.current_weapon = "pistol"
        start = g.player.ammo[C.AMMO_BULLETS]
        self.assertTrue(g.fire_weapon())
        self.assertEqual(g.player.ammo[C.AMMO_BULLETS], start - 1)
        self.assertGreater(g.player.weapon_cooldown, 0.0)

    def test_cooldown_blocks_immediate_refire(self):
        g = make_game(LINE)
        g.player.current_weapon = "pistol"
        g.fire_weapon()
        ammo = g.player.ammo[C.AMMO_BULLETS]
        self.assertFalse(g.fire_weapon())          # still cooling down
        self.assertEqual(g.player.ammo[C.AMMO_BULLETS], ammo)

    def test_out_of_ammo_autoswitches_to_fist(self):
        g = make_game(LINE)
        g.player.current_weapon = "pistol"
        g.player.ammo[C.AMMO_BULLETS] = 0
        self.assertFalse(g.fire_weapon())
        self.assertEqual(g.message, "OUT OF AMMO")
        self.assertEqual(g.player.current_weapon, "fist")

    def test_hitscan_damages_monster(self):
        g = make_game(LINE)
        g.player.current_weapon = "pistol"
        monster = g.monsters[0]
        before = monster.health
        g.fire_weapon()
        self.assertLess(monster.health, before)

    def test_kill_increments_counters(self):
        g = make_game(LINE)
        monster = g.monsters[0]
        g.damage_monster(monster, 999)
        self.assertFalse(monster.alive)
        self.assertEqual(g.kills, 1)
        self.assertEqual(g.total_kills, 1)
        self.assertEqual(monster.state, "dead")

    def test_shotgun_drops_zombie_in_one_blast(self):
        g = make_game(LINE)
        g.player.weapons.add("shotgun")
        g.player.current_weapon = "shotgun"
        g.player.ammo[C.AMMO_SHELLS] = 8
        monster = g.monsters[0]
        g.fire_weapon()
        self.assertEqual(g.player.ammo[C.AMMO_SHELLS], 7)  # one shell, many pellets
        self.assertFalse(monster.alive)

    def test_wall_blocks_hitscan(self):
        g = make_game(BLOCKED)
        g.player.current_weapon = "pistol"
        monster = g.monsters[0]
        before = monster.health
        g.fire_weapon()
        self.assertEqual(monster.health, before)

    def test_armor_absorbs_one_third(self):
        g = make_game(LINE)
        g.player.armor = 30
        g.player.take_damage(30)
        self.assertEqual(g.player.armor, 20)    # absorbed 10
        self.assertEqual(g.player.health, 80)   # took 20

    def test_player_death_sets_mode(self):
        g = make_game(LINE)
        g.player.take_damage(1000)
        g.update(0.016)
        self.assertEqual(g.mode, g.DEAD)


if __name__ == "__main__":
    unittest.main()
