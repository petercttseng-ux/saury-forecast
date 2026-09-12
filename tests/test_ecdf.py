import unittest
from datetime import datetime
from pathlib import Path

import numpy as np

from ecdf_analyzer import HabitatPredictor, SauryECDFAnalyzer


ROOT = Path(__file__).resolve().parents[1]


class ECDFAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analyzer = SauryECDFAnalyzer()
        assert cls.analyzer.load_data(ROOT / 'Saury-csv.txt')
        cls.results = cls.analyzer.analyze_all()

    def test_all_environment_parameters_are_analyzed(self):
        self.assertEqual(set(self.results), set(self.analyzer.PARAMETERS))
        self.assertTrue(all(result['n'] == 2879 for result in self.results.values()))
        self.assertAlmostEqual(self.results['sst']['percentiles']['low'], 13.5, places=1)
        self.assertAlmostEqual(self.results['sst']['percentiles']['high'], 16.6, places=1)

    def test_ecdf_is_monotonic_and_weighted(self):
        for result in self.results.values():
            self.assertTrue(np.all(np.diff(result['cdf']) >= 0))
            self.assertTrue(np.all(np.diff(result['weighted_cdf']) >= 0))
            self.assertAlmostEqual(result['cdf'][-1], 1.0)
            self.assertAlmostEqual(result['weighted_cdf'][-1], 1.0)
            self.assertGreaterEqual(result['d_max_abs'], 0.0)

    def test_frontend_curve_payload_is_aligned(self):
        curves = self.analyzer.get_curve_data(max_points=80)
        self.assertEqual(set(curves), set(self.analyzer.PARAMETERS))
        for curve in curves.values():
            self.assertEqual(len(curve['v']), len(curve['cdf']))
            self.assertEqual(len(curve['v']), len(curve['weightedCdf']))
            self.assertLessEqual(len(curve['v']), 80)
            self.assertLess(curve['p10'], curve['p90'])

    def test_trapezoid_suitability_has_expected_boundaries(self):
        result = self.results['sst']
        p = result['percentiles']
        values = np.array([
            p['very_low'], p['low'], p['moderate'], p['high'], p['very_high'], np.nan
        ])
        scores = self.analyzer._calculate_prob_score(
            values, result['sorted_values'], result['weighted_cdf']
        )
        np.testing.assert_allclose(scores[:5], [0, 1, 1, 1, 0], atol=1e-10)
        self.assertTrue(np.isnan(scores[-1]))

    def test_stale_subsurface_data_falls_back_to_sst_only(self):
        predictor = HabitatPredictor(self.analyzer)
        sst = np.array([[13.5, 15.0], [16.6, 20.0]])
        sst_data = {
            'sst': sst,
            'lats': np.array([36.0, 35.0]),
            'lons': np.array([145.0, 146.0]),
            'date': datetime(2026, 9, 10),
        }
        sub_data = {
            'temp_100m': np.full((2, 2), 4.0),
            'lats': sst_data['lats'],
            'lons': sst_data['lons'],
            'date': datetime(2026, 9, 1),
        }
        prediction = predictor.predict(sst_data, sub_data, max_subsurface_lag_days=3)
        expected = self.analyzer._calculate_prob_score(
            sst,
            self.results['sst']['sorted_values'],
            self.results['sst']['weighted_cdf'],
        )
        self.assertEqual(prediction['variables'], ['SST'])
        self.assertEqual(prediction['subtemp_lag_days'], 9)
        np.testing.assert_allclose(prediction['probability'], expected)


if __name__ == '__main__':
    unittest.main()
