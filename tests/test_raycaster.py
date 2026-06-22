import math
import unittest

from tests.helpers import make_game  # noqa: F401 ensures sys.path

from doom.raycaster import cast_ray, line_of_sight


def grid_solid(grid):
    h, w = len(grid), len(grid[0])

    def is_solid(x, y):
        if 0 <= x < w and 0 <= y < h:
            return grid[y][x] == 1
        return True
    return is_solid


# A 5x5 box with solid border (1) and open interior (0).
BOX = [
    [1, 1, 1, 1, 1],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 1, 1, 1, 1],
]


class TestRaycaster(unittest.TestCase):
    def setUp(self):
        self.solid = grid_solid(BOX)

    def test_distance_east(self):
        # From (1.5,1.5) looking east: wall face is x==4, so distance 2.5.
        hit = cast_ray(self.solid, 1.5, 1.5, 1.0, 0.0)
        self.assertTrue(hit.hit)
        self.assertAlmostEqual(hit.dist, 2.5, places=6)
        self.assertEqual(hit.side, 0)  # vertical grid line

    def test_distance_north(self):
        # Looking "up" (negative y) the wall face is y==1, distance 0.5.
        hit = cast_ray(self.solid, 1.5, 1.5, 0.0, -1.0)
        self.assertTrue(hit.hit)
        self.assertAlmostEqual(hit.dist, 0.5, places=6)
        self.assertEqual(hit.side, 1)  # horizontal grid line

    def test_wall_x_coordinate(self):
        # Hitting the east wall at y=1.5 -> fractional 0.5 along the face.
        hit = cast_ray(self.solid, 1.5, 1.5, 1.0, 0.0)
        self.assertAlmostEqual(hit.wall_x, 0.5, places=6)

    def test_diagonal_distance(self):
        hit = cast_ray(self.solid, 1.5, 1.5, math.cos(math.radians(45)),
                       math.sin(math.radians(45)))
        # Corner of the box at (4,4) area; distance ~ sqrt(2)*2.5.
        self.assertAlmostEqual(hit.dist, math.hypot(2.5, 2.5), places=4)

    def test_max_dist_miss(self):
        # Truly empty space (nothing is ever solid) -> the ray reaches max_dist.
        empty = lambda x, y: False  # noqa: E731
        hit = cast_ray(empty, 1.5, 1.5, 1.0, 0.0, max_dist=5.0)
        self.assertFalse(hit.hit)
        self.assertEqual(hit.dist, 5.0)

    def test_line_of_sight_clear(self):
        self.assertTrue(line_of_sight(self.solid, 1.5, 1.5, 3.5, 3.5))

    def test_line_of_sight_blocked(self):
        # Put a pillar in the middle and check it blocks sight across it.
        grid = [row[:] for row in BOX]
        grid[2][2] = 1
        solid = grid_solid(grid)
        self.assertFalse(line_of_sight(solid, 1.5, 1.5, 3.5, 3.5))
        # But sight along an open lane is fine.
        self.assertTrue(line_of_sight(solid, 1.5, 1.5, 1.5, 3.5))


if __name__ == "__main__":
    unittest.main()
