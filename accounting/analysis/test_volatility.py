import unittest
import pandas as pd
import numpy as np
from accounting.analysis.volatility import VolatilityAnalyzer

class TestVolatilityAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = VolatilityAnalyzer(z_threshold=2.0, min_shift_months=3)

    def test_ser_calculation(self):
        # actual: [100, 110, 120, 130, 140]
        # predicted: [100, 110, 120, 130, 140] (perfect prediction)
        actual = pd.Series([100, 110, 120, 130, 140])
        predicted = pd.Series([100, 110, 120, 130, 140])
        ser = self.analyzer.calculate_ser(actual, predicted)
        self.assertEqual(ser, 0.0)

        # with residuals: 10 each
        actual = pd.Series([110, 120, 130, 140, 150])
        predicted = pd.Series([100, 110, 120, 130, 140])
        # residuals = [10, 10, 10, 10, 10]
        # rss = 5 * 10^2 = 500
        # n = 5, n-2 = 3
        # ser = sqrt(500 / 3) = 12.9099
        ser = self.analyzer.calculate_ser(actual, predicted)
        self.assertAlmostEqual(ser, np.sqrt(500/3), places=4)

    def test_structural_break_50_increase(self):
        # 18 months of stable spending (100) + 4 months of 50% increase (150)
        historical = [100] * 18
        recent = [150] * 4
        series = pd.Series(historical + recent)
        
        result = self.analyzer.detect_structural_break(series)
        self.assertTrue(result["has_structural_break"])
        # All windows should confirm it as mean=100 and std=0 in history
        # (Actually std=0 gives huge Z)
        self.assertIn("6m", result["z_scores"])
        self.assertIn("12m", result["z_scores"])

    def test_steady_growth_no_break(self):
        # Continuous 2% growth: no sudden step-change
        # 24 months total
        series = pd.Series([100 * (1.02**t) for t in range(24)])
        
        result = self.analyzer.detect_structural_break(series)
        # Z-score will be positive but shouldn't exceed threshold significantly 
        # compared to the sliding historical mean and standard deviation.
        self.assertFalse(result["has_structural_break"])

    def test_high_variance_static_mean_no_break(self):
        # Random variance around 100
        np.random.seed(42)
        historical = np.random.normal(100, 20, 18).tolist()
        recent = np.random.normal(105, 20, 4).tolist() # slight noise increase
        series = pd.Series(historical + recent)
        
        result = self.analyzer.detect_structural_break(series)
        # Random noise shouldn't trigger a "confirmed" break unless it's sustained and extreme
        self.assertFalse(result["has_structural_break"])
        
    def test_ser_high_for_noisy_series(self):
        # Noisy series vs constant prediction
        np.random.seed(42)
        actual = pd.Series(np.random.normal(100, 20, 10))
        predicted = pd.Series([100] * 10)
        
        ser = self.analyzer.calculate_ser(actual, predicted)
        # SER should reflect the noise (approx 20)
        self.assertGreater(ser, 15)

if __name__ == '__main__':
    unittest.main()
