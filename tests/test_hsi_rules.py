import unittest

import numpy as np

import config
from analysis import extract_hotspots
from overlay_renderer import HAB_COLORS, HAB_LEVELS


class HSIRuleTests(unittest.TestCase):
    def test_habitat_classes_use_point_one_intervals(self):
        self.assertEqual(len(HAB_LEVELS), 11)
        self.assertEqual(len(HAB_COLORS), 10)
        np.testing.assert_allclose(np.diff(HAB_LEVELS), 0.1)
        self.assertEqual(HAB_LEVELS[0], 0.0)
        self.assertEqual(HAB_LEVELS[-1], 1.0)

    def test_recommendation_threshold_is_strictly_greater_than_point_five(self):
        self.assertEqual(config.HOTSPOT_PROB_THRESHOLD, 0.5)
        lats = np.array([36.0, 35.0])
        lons = np.array([145.0, 146.0])
        at_boundary = np.full((2, 2), 0.5)
        self.assertEqual(
            extract_hotspots(at_boundary, lats, lons, min_area_km2=0),
            [],
        )

        above_boundary = at_boundary.copy()
        above_boundary[0, 0] = 0.51
        spots = extract_hotspots(
            above_boundary, lats, lons, min_area_km2=0
        )
        self.assertEqual(len(spots), 1)
        self.assertGreater(spots[0]['mean_prob'], 0.5)


if __name__ == '__main__':
    unittest.main()
