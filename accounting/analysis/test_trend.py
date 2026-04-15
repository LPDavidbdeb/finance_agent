import unittest
import pandas as pd
import numpy as np
from accounting.analysis.trend import TrendAnalyzer, TrendResult

class TestTrendAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = TrendAnalyzer()

    def test_consistent_growth_12m(self):
        # 12-month series with consistent growth in ln(y+1) space
        # ln(y+1) = intercept + t * slope
        slope_val = 0.05
        intercept = 4.0
        # y = exp(intercept + t * slope) - 1
        series = pd.Series([np.exp(intercept + t * slope_val) - 1 for t in range(12)])
        
        result = self.analyzer.analyze(series)
        
        self.assertAlmostEqual(result.slope, slope_val, places=4)
        self.assertTrue(result.is_significant)
        self.assertFalse(result.is_nonlinear)

    def test_short_series_significance(self):
        # n = 4, 3% slope -> Significant based on Effect Size (> 0.02)
        slope_val = 0.03
        intercept = 4.0
        series = pd.Series([np.exp(intercept + t * slope_val) - 1 for t in range(4)])
        
        result = self.analyzer.analyze(series)
        
        self.assertAlmostEqual(result.slope, 0.03, places=4)
        self.assertTrue(result.is_significant) # Effect Size > 0.02

    def test_non_linearity_36m(self):
        # 36 months total
        # Year 1 (0-11): Growing VERY sharply (slope = 0.8)
        # Year 2 & 3 (12-35): Completely flat (slope = 0.0)
        slope_y1 = 0.8
        intercept = 4.0
        y_y1 = [np.exp(intercept + t * slope_y1) - 1 for t in range(12)]
        last_val = y_y1[-1]
        y_y23 = [last_val] * 24
        series = pd.Series(y_y1 + y_y23)
        
        result = self.analyzer.analyze(series)
        
        # Difference should now be > 0.15
        self.assertTrue(result.is_nonlinear)
        
    def test_linear_36m(self):
        # Consistent growth should not trigger non-linearity
        slope_val = 0.02
        intercept = 4.0
        series = pd.Series([np.exp(intercept + t * slope_val) - 1 for t in range(36)])
        result = self.analyzer.analyze(series)
        self.assertFalse(result.is_nonlinear)

if __name__ == '__main__':
    unittest.main()
