import unittest
import pandas as pd
import numpy as np
from accounting.analysis.sanity import SanityLayer

class TestSanityLayer(unittest.TestCase):
    def setUp(self):
        # Using a very low threshold for easier testing
        self.sl = SanityLayer(percentile_threshold=0.90, persistence_threshold=3, std_threshold=2.0)

    def test_winsorization_single_spike(self):
        # Stochastic series with a single massive 1-month spike
        series = pd.Series([100, 110, 105, 95, 1000, 100, 110, 105, 95, 100])
        cleaned = self.sl.apply_conditional_winsorization(series)
        
        # Spike at index 4 should be capped
        self.assertLess(cleaned.iloc[4], 1000)
        # Other values should remain untouched
        self.assertEqual(cleaned.iloc[0], 100)
        self.assertEqual(cleaned.iloc[5], 100)

    def test_persistence_preservation(self):
        # Persistent spike (4 consecutive months)
        series = pd.Series([100, 110, 105, 1000, 1000, 1000, 1000, 100, 110, 105])
        cleaned = self.sl.apply_conditional_winsorization(series)
        
        # Spikes should NOT be capped because they persist for 4 months (>= threshold 3)
        self.assertEqual(cleaned.iloc[3], 1000)
        self.assertEqual(cleaned.iloc[4], 1000)
        self.assertEqual(cleaned.iloc[5], 1000)
        self.assertEqual(cleaned.iloc[6], 1000)

    def test_missing_period_imputation(self):
        # Dense series with a single 0 in the middle
        series = pd.Series([100, 110, 0, 110, 100])
        cleaned = self.sl.impute_missing_periods(series)
        
        # Isolated zero at index 2 should be interpolated
        self.assertEqual(cleaned.iloc[2], 110.0) # (110 + 110) / 2
        
    def test_non_isolated_zero_ignored(self):
        # Two consecutive zeros should not be imputed by this method (not isolated)
        series = pd.Series([100, 110, 0, 0, 110, 100])
        cleaned = self.sl.impute_missing_periods(series)
        
        self.assertEqual(cleaned.iloc[2], 0)
        self.assertEqual(cleaned.iloc[3], 0)

    def test_full_process_integration(self):
        # Mix of isolated zero and a spike
        series = pd.Series([100, 110, 0, 110, 1000, 100])
        cleaned = self.sl.process(series)
        
        # Index 2 should be imputed
        self.assertEqual(cleaned.iloc[2], 110.0)
        # Index 4 should be capped
        self.assertLess(cleaned.iloc[4], 1000)

if __name__ == '__main__':
    unittest.main()
