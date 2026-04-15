import unittest
import pandas as pd
import numpy as np
from accounting.analysis.filters import SignalFilter

class TestSignalFilter(unittest.TestCase):
    def setUp(self):
        self.sf = SignalFilter(materiality_threshold=0.01, sparsity_threshold=0.30)

    def test_materiality_boundaries(self):
        # Exactly 1% -> Active (percentage < threshold is Muted, so 0.01 is not < 0.01)
        self.assertEqual(self.sf.classify_materiality(100, 10000), "Active")
        # 0.5% -> Muted
        self.assertEqual(self.sf.classify_materiality(50, 10000), "Muted")
        # 2% -> Active
        self.assertEqual(self.sf.classify_materiality(200, 10000), "Active")

    def test_materiality_division_by_zero(self):
        # Fallback should be Muted
        self.assertEqual(self.sf.classify_materiality(100, 0), "Muted")

    def test_sparsity_boundaries(self):
        # Exactly 4 zeros in 12 months -> 4/12 = 0.333 > 0.30 -> Sparse
        sparse_series = [100, 100, 100, 100, 100, 100, 100, 100, 0, 0, 0, 0]
        self.assertEqual(self.sf.classify_sparsity(sparse_series), "Sparse")

        # Exactly 3 zeros in 12 months -> 3/12 = 0.25 <= 0.30 -> Dense
        dense_series = [100, 100, 100, 100, 100, 100, 100, 100, 100, 0, 0, 0]
        self.assertEqual(self.sf.classify_sparsity(dense_series), "Dense")

if __name__ == '__main__':
    unittest.main()
