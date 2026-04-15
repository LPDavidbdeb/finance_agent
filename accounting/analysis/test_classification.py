import unittest
import pandas as pd
import numpy as np
from accounting.analysis.classification import ProcessClassifier, ProcessType

class TestProcessClassifier(unittest.TestCase):
    def setUp(self):
        self.pc = ProcessClassifier(cov_threshold=0.05, sparsity_threshold=0.30)

    def test_deterministic_classification(self):
        # Simulated rent payment series: exactly constant
        rent_series = [1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500]
        self.assertEqual(self.pc.classify(rent_series), ProcessType.DETERMINISTIC)

        # Tiny variations (less than 5% CoV)
        # mean=100, std=1.0 -> CoV=0.01 < 0.05
        low_var_series = [100, 101, 99, 100, 101, 99, 100, 101, 99, 100, 101, 99]
        self.assertEqual(self.pc.classify(low_var_series), ProcessType.DETERMINISTIC)

    def test_stochastic_classification(self):
        # Simulated grocery series: visible variations (more than 5% CoV)
        # mean=500, std=approx 80 -> CoV=0.16 > 0.05
        grocery_series = [450, 520, 390, 610, 480, 530, 420, 580, 460, 510, 400, 600]
        self.assertEqual(self.pc.classify(grocery_series), ProcessType.STOCHASTIC)

    def test_episodic_classification(self):
        # Simulated home repair series: mostly zeros, few spikes
        # 8 zeros out of 12 (66% sparse)
        repair_series = [0, 0, 5000, 0, 0, 0, 0, 2500, 0, 0, 0, 0]
        self.assertEqual(self.pc.classify(repair_series), ProcessType.EPISODIC)

        # Exactly 4 zeros in 12 months (33.3% sparse) -> Episodic
        sparse_series_boundary = [100, 100, 100, 100, 100, 100, 100, 100, 0, 0, 0, 0]
        self.assertEqual(self.pc.classify(sparse_series_boundary), ProcessType.EPISODIC)

    def test_optional_sparsity_status(self):
        # If we explicitly pass 'Sparse', it should be EPISODIC even if CoV is low
        low_var_series = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
        # Normally DETERMINISTIC
        self.assertEqual(self.pc.classify(low_var_series), ProcessType.DETERMINISTIC)
        # Overridden to EPISODIC
        self.assertEqual(self.pc.classify(low_var_series, sparsity_status="Sparse"), ProcessType.EPISODIC)

if __name__ == '__main__':
    unittest.main()
