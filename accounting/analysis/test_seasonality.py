import unittest
import pandas as pd
import numpy as np
from accounting.analysis.seasonality import SeasonalityAnalyzer

class TestSeasonalityAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = SeasonalityAnalyzer(correlation_threshold=0.7)

    def test_insufficient_data(self):
        # n < 24 should return False
        series = pd.Series([100] * 23)
        result = self.analyzer.analyze(series)
        self.assertFalse(result.is_seasonal)

    def test_seasonal_december_spike(self):
        # Consistent spike every December (index 11 and 23)
        data = [100] * 24
        data[11] = 1000
        data[23] = 1000
        series = pd.Series(data)
        
        result = self.analyzer.analyze(series)
        self.assertTrue(result.is_seasonal)
        self.assertEqual(result.best_lag, 0)
        self.assertAlmostEqual(result.max_correlation, 1.0, places=4)

    def test_seasonal_with_drift(self):
        # Year 1 spike in Dec (index 11)
        # Year 2 spike in Jan (index 24) -> but our tail(24) takes index 0..23
        # Let's be careful with indexing:
        # data[0..11] is Year 1
        # data[12..23] is Year 2
        
        data = [100] * 24
        data[11] = 1000 # Dec Year 1
        data[22] = 1000 # Nov Year 2 (drift -1)
        
        series = pd.Series(data)
        result = self.analyzer.analyze(series)
        
        # At lag 0: y1=[...1000], y2=[...1000, 100] -> Low correlation
        # At lag -1: s1=y1[1:]=[...1000], s2=y2[:-1]=[...1000] -> High correlation
        self.assertTrue(result.is_seasonal)
        self.assertEqual(result.best_lag, -1)

    def test_random_noise_not_seasonal(self):
        # Pure random noise
        np.random.seed(42)
        series = pd.Series(np.random.normal(100, 20, 24))
        
        result = self.analyzer.analyze(series)
        self.assertFalse(result.is_seasonal)

if __name__ == '__main__':
    unittest.main()
