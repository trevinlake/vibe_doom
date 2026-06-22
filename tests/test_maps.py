import unittest

from tests.helpers import make_game  # noqa: F401  (ensures sys.path is set)

from doom import constants as C
from doom.maps import LEVELS, parse_level


class TestMapParser(unittest.TestCase):
    def test_dimensions_and_floor(self):
        level = parse_level(["###", "#P#", "###"])
        self.assertEqual(level["width"], 3)
        self.assertEqual(level["height"], 3)
        # Player cell is converted to floor.
        self.assertEqual(level["grid"][1][1], C.T_FLOOR)
        self.assertEqual(level["player_start"], (1.5, 1.5, 0.0))

    def test_things_sit_on_floor(self):
        level = parse_level([
            "#####",
            "#Pz.#",
            "#h.g#",
            "#####",
        ])
        # Monster and item cells become floor in the grid.
        self.assertEqual(level["grid"][1][2], C.T_FLOOR)
        self.assertEqual(level["grid"][2][1], C.T_FLOOR)
        kinds = {m[0] for m in level["monsters"]}
        self.assertIn("zombie", kinds)
        items = {it[0] for it in level["items"]}
        self.assertEqual(items, {C.ITEM_HEALTH, C.ITEM_SHOTGUN})

    def test_door_and_exit_tiles(self):
        level = parse_level(["#####", "#PDX#", "#####"])
        self.assertEqual(level["grid"][1][2], C.T_DOOR)
        self.assertEqual(level["grid"][1][3], C.T_EXIT)

    def test_locked_door_tile(self):
        level = parse_level(["####", "#PL#", "####"])
        self.assertEqual(level["grid"][1][2], C.T_DOOR_LOCKED)

    def test_ragged_map_raises(self):
        with self.assertRaises(ValueError):
            parse_level(["###", "#P##", "###"])

    def test_missing_player_raises(self):
        with self.assertRaises(ValueError):
            parse_level(["###", "#.#", "###"])

    def test_duplicate_player_raises(self):
        with self.assertRaises(ValueError):
            parse_level(["####", "#PP#", "####"])

    def test_unknown_char_raises(self):
        with self.assertRaises(ValueError):
            parse_level(["####", "#P?#", "####"])

    def test_all_campaign_levels_parse(self):
        for lvl in LEVELS:
            parsed = parse_level(lvl["rows"])
            self.assertGreater(len(parsed["monsters"]), 0)
            # Every campaign level must contain exactly one exit switch.
            exits = sum(row.count(C.T_EXIT) for row in parsed["grid"])
            self.assertEqual(exits, 1, lvl["name"])


if __name__ == "__main__":
    unittest.main()
