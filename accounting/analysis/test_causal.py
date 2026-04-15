import unittest
import pandas as pd
from decimal import Decimal
from datetime import timedelta
from accounting.analysis.causal import CausalAnalyzer, CausalAnalysisResult


class TestCausalAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = CausalAnalyzer(mix_shift_threshold_pct=10.0)

    # =========================================================================
    # SUCCESS CRITERIA 1: Module accepts transaction DataFrame and returns result
    # =========================================================================
    def test_returns_causal_analysis_result(self):
        """Verify that analyze() returns a proper CausalAnalysisResult."""
        df = self._create_simple_transactions()
        result = self.analyzer.analyze(df)

        self.assertIsInstance(result, CausalAnalysisResult)
        self.assertIsInstance(result.volume_effect_pct, float)
        self.assertIsInstance(result.price_effect_pct, float)
        self.assertIsInstance(result.mix_shift_detected, bool)

    def test_accepts_dataframe_with_required_columns(self):
        """Verify that analyze() accepts DataFrame with date, amount, merchant_name."""
        df = pd.DataFrame({
            'date': pd.date_range('2025-01-01', periods=24, freq='M'),
            'amount': [50.0] * 24,
            'merchant_name': ['MerchantA'] * 24,
        })

        result = self.analyzer.analyze(df)
        self.assertIsInstance(result, CausalAnalysisResult)

    def test_rejects_empty_dataframe(self):
        """Verify that empty DataFrames raise ValueError."""
        df = pd.DataFrame({'date': [], 'amount': [], 'merchant_name': []})

        with self.assertRaises(ValueError):
            self.analyzer.analyze(df)

    def test_rejects_missing_columns(self):
        """Verify that missing required columns raise ValueError."""
        df = pd.DataFrame({'date': [1, 2], 'amount': [10, 20]})  # missing merchant_name

        with self.assertRaises(ValueError):
            self.analyzer.analyze(df)

    def test_handles_decimal_amounts(self):
        """Verify that Decimal amounts are converted correctly."""
        df = pd.DataFrame({
            'date': pd.date_range('2025-01-01', periods=24, freq='M'),
            'amount': [Decimal('50.00')] * 24,
            'merchant_name': ['MerchantA'] * 24,
        })

        result = self.analyzer.analyze(df)
        self.assertAlmostEqual(result.l12m_avg_ticket, 50.0, places=2)

    # =========================================================================
    # SUCCESS CRITERIA 2: Price Effect Test
    # Test: 4 purchases/month at $50 → $60, expects +20% price, 0% volume
    # =========================================================================
    def test_price_effect_4purchases_50to60(self):
        """
        Scenario: User makes exactly 4 purchases per month.
        P12M: 4 * 12 = 48 purchases at $50 = $2400 total
        L12M: 4 * 12 = 48 purchases at $60 = $2880 total
        Expected: +20% price effect, 0% volume effect
        """
        # Create P12M: 12 months, 4 transactions each at $50
        p12m_dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
        p12m_txns = []
        for month in pd.date_range('2024-01-01', periods=12, freq='MS'):
            for i in range(4):
                p12m_txns.append({
                    'date': month + timedelta(days=i*7),
                    'amount': 50.0,
                    'merchant_name': 'MerchantA'
                })

        # Create L12M: 12 months, 4 transactions each at $60
        l12m_txns = []
        for month in pd.date_range('2025-01-01', periods=12, freq='MS'):
            for i in range(4):
                l12m_txns.append({
                    'date': month + timedelta(days=i*7),
                    'amount': 60.0,
                    'merchant_name': 'MerchantA'
                })

        df = pd.DataFrame(p12m_txns + l12m_txns)
        result = self.analyzer.analyze(df, reference_date=pd.Timestamp('2025-12-31'))

        # Volume: 48 → 48, so 0% change
        self.assertAlmostEqual(result.volume_effect_pct, 0.0, places=1)

        # Price: $50 → $60, so +20% change
        self.assertAlmostEqual(result.price_effect_pct, 20.0, places=1)

        # No merchant shift
        self.assertFalse(result.mix_shift_detected)

    # =========================================================================
    # SUCCESS CRITERIA 3: Volume Effect Test
    # Test: Ticket stays at $50, but frequency goes 4x/month → 6x/month, +50% volume
    # =========================================================================
    def test_volume_effect_4to6_purchases_fixed_50(self):
        """
        Scenario: User makes variable number of purchases per month, all at $50.
        P12M: 4 purchases/month * 12 months = 48 purchases at $50 = $2400 total
        L12M: 6 purchases/month * 12 months = 72 purchases at $50 = $3600 total
        Expected: +50% volume effect, 0% price effect
        """
        # Create P12M: 12 months, 4 transactions each at $50
        p12m_txns = []
        for month in pd.date_range('2024-01-01', periods=12, freq='MS'):
            for i in range(4):
                p12m_txns.append({
                    'date': month + timedelta(days=i*7),
                    'amount': 50.0,
                    'merchant_name': 'MerchantA'
                })

        # Create L12M: 12 months, 6 transactions each at $50
        l12m_txns = []
        for month in pd.date_range('2025-01-01', periods=12, freq='MS'):
            for i in range(6):
                l12m_txns.append({
                    'date': month + timedelta(days=i*6),
                    'amount': 50.0,
                    'merchant_name': 'MerchantA'
                })

        df = pd.DataFrame(p12m_txns + l12m_txns)
        result = self.analyzer.analyze(df, reference_date=pd.Timestamp('2025-12-31'))

        # Volume: 48 → 72, so +50% change
        self.assertAlmostEqual(result.volume_effect_pct, 50.0, places=1)

        # Price: $50 → $50, so 0% change
        self.assertAlmostEqual(result.price_effect_pct, 0.0, places=1)

        # No merchant shift
        self.assertFalse(result.mix_shift_detected)

    # =========================================================================
    # SUCCESS CRITERIA 4: Mix Shift Test
    # Test: User shifts primary spending from Merchant A to Merchant B
    # =========================================================================
    def test_mix_shift_detected_merchant_switch(self):
        """
        Scenario: User shifts spending from Merchant A to Merchant B.
        P12M (2023-12-31 to 2024-12-30): 90% of spend at MerchantA, 10% at MerchantB
        L12M (2024-12-31 to 2025-12-31): 10% of spend at MerchantA, 90% at MerchantB
        Expected: mix_shift_detected = True (change of 80 percentage points > threshold)
        """
        # P12M: MerchantA is dominant by spend, but not overwhelmingly so.
        p12m_txns = []
        for month in range(12):
            # MerchantA: 6 low-ticket transactions
            for i in range(6):
                p12m_txns.append({
                    'date': pd.Timestamp('2024-01-01') + timedelta(days=(month * 10) + i),
                    'amount': 10.0,
                    'merchant_name': 'MerchantA'
                })
            # MerchantB: 4 low-ticket transactions
            for i in range(4):
                p12m_txns.append({
                    'date': pd.Timestamp('2024-01-01') + timedelta(days=(month * 10) + 6 + i),
                    'amount': 10.0,
                    'merchant_name': 'MerchantB'
                })

        # L12M: flip the spend dominance hard so MerchantB clearly wins.
        l12m_txns = []
        for month in range(12):
            # MerchantA: 1 small-ticket transaction
            l12m_txns.append({
                'date': pd.Timestamp('2025-01-01') + timedelta(days=(month * 10)),
                'amount': 10.0,
                'merchant_name': 'MerchantA'
            })
            # MerchantB: 9 large-ticket transactions
            for i in range(9):
                l12m_txns.append({
                    'date': pd.Timestamp('2025-01-01') + timedelta(days=(month * 10) + 1 + i),
                    'amount': 100.0,
                    'merchant_name': 'MerchantB'
                })

        df = pd.DataFrame(p12m_txns + l12m_txns)
        result = self.analyzer.analyze(df, reference_date=pd.Timestamp('2024-12-31'))

        # Spend-share concentration flips sharply, so the threshold must trigger.
        self.assertTrue(result.mix_shift_detected)
        self.assertGreater(abs(result.l12m_top_merchant_share - result.p12m_top_merchant_share), 10.0)

    def test_no_mix_shift_below_threshold(self):
        """
        Scenario: Top merchant share changes from 50% to 58% (8pp change < 10pp threshold)
        Expected: mix_shift_detected = False
        """
        # Create P12M: 50% at MerchantA, 50% at MerchantB
        p12m_txns = []
        for month in pd.date_range('2024-01-01', periods=12, freq='MS'):
            for i in range(5):
                p12m_txns.append({
                    'date': month + timedelta(days=i*3),
                    'amount': 50.0,
                    'merchant_name': 'MerchantA'
                })
            for i in range(5):
                p12m_txns.append({
                    'date': month + timedelta(days=15 + i*3),
                    'amount': 50.0,
                    'merchant_name': 'MerchantB'
                })

        # Create L12M: 58% at MerchantA, 42% at MerchantB
        l12m_txns = []
        for month in pd.date_range('2025-01-01', periods=12, freq='MS'):
            # 58 purchases out of 100
            for i in range(6):
                l12m_txns.append({
                    'date': month + timedelta(days=i*2),
                    'amount': 50.0,
                    'merchant_name': 'MerchantA'
                })
            # 42 purchases out of 100
            for i in range(4):
                l12m_txns.append({
                    'date': month + timedelta(days=12 + i*2),
                    'amount': 50.0,
                    'merchant_name': 'MerchantB'
                })

        df = pd.DataFrame(p12m_txns + l12m_txns)
        result = self.analyzer.analyze(df, reference_date=pd.Timestamp('2025-12-31'))

        # Should NOT detect mix shift (8pp change < 10pp threshold)
        self.assertFalse(result.mix_shift_detected)

    # =========================================================================
    # ADDITIONAL EDGE CASES & ROBUSTNESS
    # =========================================================================
    def test_insufficient_data_raises_error(self):
        """Verify that data with fewer than 2 data points across windows raises error."""
        # Only one transaction total
        df = pd.DataFrame({
            'date': [pd.Timestamp('2025-12-15')],
            'amount': [50.0],
            'merchant_name': ['MerchantA']
        })

        with self.assertRaises(ValueError):
            self.analyzer.analyze(df)

    def test_median_split_fallback(self):
        """
        Verify that if exact 12-month windows don't exist,
        the analyzer falls back to median split (first 50% vs second 50%).
        """
        # Create 20 transactions spread over ~2 months
        df = pd.DataFrame({
            'date': pd.date_range('2025-01-01', periods=20, freq='D'),
            'amount': [50.0] * 10 + [60.0] * 10,
            'merchant_name': ['MerchantA'] * 20
        })

        result = self.analyzer.analyze(df)

        # First 10 at $50, next 10 at $60
        self.assertAlmostEqual(result.p12m_transaction_count, 10)
        self.assertAlmostEqual(result.l12m_transaction_count, 10)
        self.assertAlmostEqual(result.p12m_avg_ticket, 50.0, places=1)
        self.assertAlmostEqual(result.l12m_avg_ticket, 60.0, places=1)

    def test_combined_price_and_volume_effect(self):
        """
        Scenario: Both price and volume change simultaneously.
        P12M: 40 transactions at $50 = $2000
        L12M: 60 transactions at $60 = $3600
        Expected: +50% volume, +20% price
        """
        # P12M: 40 transactions at $50
        p12m_txns = []
        day_counter = 0
        for i in range(40):
            p12m_txns.append({
                'date': pd.Timestamp('2024-01-01') + timedelta(days=day_counter),
                'amount': 50.0,
                'merchant_name': 'MerchantA'
            })
            day_counter += 1

        # L12M: 60 transactions at $60
        l12m_txns = []
        day_counter = 0
        for i in range(60):
            l12m_txns.append({
                'date': pd.Timestamp('2025-01-01') + timedelta(days=day_counter),
                'amount': 60.0,
                'merchant_name': 'MerchantA'
            })
            day_counter += 1

        df = pd.DataFrame(p12m_txns + l12m_txns)
        result = self.analyzer.analyze(df, reference_date=pd.Timestamp('2025-12-31'))

        # Volume: 40 → 60 = +50%
        self.assertAlmostEqual(result.volume_effect_pct, 50.0, places=0)
        # Price: $50 → $60 = +20%
        self.assertAlmostEqual(result.price_effect_pct, 20.0, places=0)

    def test_multiple_merchants_no_shift(self):
        """
        Scenario: Multiple merchants with no dominant shift.
        P12M and L12M have same distribution
        Expected: mix_shift_detected = False
        """
        # Create P12M: 3 equal merchants
        p12m_txns = []
        for month in pd.date_range('2024-01-01', periods=12, freq='MS'):
            for merchant in ['A', 'B', 'C']:
                for i in range(4):
                    p12m_txns.append({
                        'date': month + timedelta(days=i*7),
                        'amount': 50.0,
                        'merchant_name': f'Merchant{merchant}'
                    })

        # Create L12M: Same 3 equal merchants
        l12m_txns = []
        for month in pd.date_range('2025-01-01', periods=12, freq='MS'):
            for merchant in ['A', 'B', 'C']:
                for i in range(4):
                    l12m_txns.append({
                        'date': month + timedelta(days=i*7),
                        'amount': 50.0,
                        'merchant_name': f'Merchant{merchant}'
                    })

        df = pd.DataFrame(p12m_txns + l12m_txns)
        result = self.analyzer.analyze(df, reference_date=pd.Timestamp('2025-12-31'))

        # Top merchant is ~33% in both periods (no shift)
        self.assertFalse(result.mix_shift_detected)

    def test_reference_date_parameter(self):
        """Verify that reference_date parameter correctly anchors the 12-month window."""
        date_range = pd.date_range('2024-01-01', '2025-12-31', freq='D')
        num_dates = len(date_range)
        df = pd.DataFrame({
            'date': date_range,
            'amount': [50.0] * num_dates,
            'merchant_name': ['MerchantA'] * num_dates,
        })

        # Use reference date of 2025-06-30 (mid-2025)
        result = self.analyzer.analyze(df, reference_date=pd.Timestamp('2025-06-30'))

        # Should still return valid result
        self.assertIsInstance(result, CausalAnalysisResult)
        self.assertGreater(result.l12m_transaction_count, 0)
        self.assertGreater(result.p12m_transaction_count, 0)

    def test_zero_old_value_percentage_change(self):
        """
        Verify handling when old value is zero (no transactions in P12M).
        Expected: should return inf if L12M has transactions, else 0.
        """
        # All transactions in L12M, none in P12M
        result = CausalAnalyzer._calculate_percentage_change(0, 100)
        self.assertEqual(result, float('inf'))

        result = CausalAnalyzer._calculate_percentage_change(0, 0)
        self.assertEqual(result, 0.0)

    def test_varying_amount_size(self):
        """Verify that the analyzer handles varying transaction amounts correctly."""
        # Mix of small and large transactions
        amounts = [10.0, 20.0, 100.0, 50.0, 75.0] * 10  # 50 varied transactions
        dates = pd.date_range('2024-06-01', periods=50, freq='D')

        df = pd.DataFrame({
            'date': dates,
            'amount': amounts,
            'merchant_name': ['MerchantA'] * 50,
        })

        result = self.analyzer.analyze(df)
        avg_amount = sum(amounts) / len(amounts)
        self.assertAlmostEqual(result.l12m_avg_ticket, avg_amount, places=1)

    # =========================================================================
    # TEST HELPER
    # =========================================================================
    def _create_simple_transactions(self):
        """Helper to create a simple 24-month transaction dataset."""
        return pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=24, freq='M'),
            'amount': [50.0] * 24,
            'merchant_name': ['MerchantA'] * 24,
        })


if __name__ == '__main__':
    unittest.main()

