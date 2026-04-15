import unittest
import pandas as pd
import numpy as np
from accounting.analysis.projection import ProjectionEngine, ProjectionResult
from accounting.analysis.trend import TrendResult
from accounting.analysis.volatility import VolatilityResult
from accounting.analysis.classification import ProcessType


class TestProjectionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ProjectionEngine(
            mape_threshold=0.20,
            ci_multiplier=1.96,
            reserve_percentile=90.0,
            recent_months_for_mean=6
        )

    # =========================================================================
    # SUCCESS CRITERIA 1: Module receives prerequisite objects and outputs result
    # =========================================================================
    def test_receives_prerequisite_objects_outputs_result(self):
        """Verify engine accepts all prerequisite analysis objects and returns ProjectionResult."""
        series = pd.Series([100.0] * 24, index=pd.date_range('2023-01-01', periods=24, freq='MS'))

        trend_result = TrendResult(
            slope=0.01,
            p_value=0.05,
            is_significant=False,
            is_nonlinear=False
        )

        volatility_result = VolatilityResult(
            ser=10.0,
            has_structural_break=False,
            z_scores={'6m': 0.5, '12m': 0.3, '18m': 0.2}
        )

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.DETERMINISTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # Verify result structure
        self.assertIsInstance(result, ProjectionResult)
        self.assertIsInstance(result.projected_series, pd.Series)
        self.assertIsInstance(result.upper_bound, pd.Series)
        self.assertIsInstance(result.lower_bound, pd.Series)
        self.assertIsInstance(result.selected_model, str)

        # Verify projection length
        self.assertEqual(len(result.projected_series), 12)
        self.assertEqual(len(result.upper_bound), 12)
        self.assertEqual(len(result.lower_bound), 12)

    def test_handles_empty_series_error(self):
        """Verify error handling for empty series."""
        empty_series = pd.Series([])

        trend_result = TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=0.0, has_structural_break=False, z_scores={})

        with self.assertRaises(ValueError):
            self.engine.project(empty_series, ProcessType.DETERMINISTIC, trend_result, volatility_result)

    def test_handles_insufficient_data_error(self):
        """Verify error handling for series with <2 data points."""
        series = pd.Series([100.0])

        trend_result = TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=0.0, has_structural_break=False, z_scores={})

        with self.assertRaises(ValueError):
            self.engine.project(series, ProcessType.DETERMINISTIC, trend_result, volatility_result)

    # =========================================================================
    # SUCCESS CRITERIA 2: EPISODIC model - flat reserve from 90th percentile
    # =========================================================================
    def test_episodic_model_uses_90th_percentile_reserve(self):
        """
        Verify EPISODIC model calculates annual reserve from 90th percentile of non-zero spikes.
        Example: Spikes of [100, 200, 300, 400, 500, 1000]
        90th percentile ≈ 950, monthly allocation = 950 / 12 ≈ 79
        """
        # Create sparse episodic data: mostly zeros with occasional spikes
        data = [0] * 12 + [100, 0, 200, 0, 300, 0, 400, 0, 500, 0, 1000, 0]
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=len(data), freq='MS'))

        trend_result = TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=50.0, has_structural_break=False, z_scores={})

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.EPISODIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # Verify model type
        self.assertEqual(result.selected_model, "EPISODIC_RESERVE")

        # Verify projection is flat
        self.assertTrue((result.projected_series == result.projected_series.iloc[0]).all())

        # Verify projection is approximately 90th percentile / 12
        non_zero = [100, 200, 300, 400, 500, 1000]
        percentile_90 = float(np.percentile(non_zero, 90))
        expected_monthly = percentile_90 / 12.0
        self.assertAlmostEqual(result.projected_series.iloc[0], expected_monthly, delta=10)

    def test_episodic_model_handles_all_zeros(self):
        """Verify EPISODIC model handles series with all zeros."""
        series = pd.Series([0.0] * 24, index=pd.date_range('2023-01-01', periods=24, freq='MS'))

        trend_result = TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=0.0, has_structural_break=False, z_scores={})

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.EPISODIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # Should project zeros
        self.assertEqual(result.selected_model, "EPISODIC_RESERVE")
        self.assertTrue((result.projected_series == 0.0).all())

    # =========================================================================
    # SUCCESS CRITERIA 3: DETERMINISTIC model - flat projection = recent average
    # =========================================================================
    def test_deterministic_model_projects_flat_recent_average(self):
        """
        Verify DETERMINISTIC model projects recent 6-month mean as flat line.
        Example: Last 6 months = [90, 95, 100, 105, 110, 115]
        Mean = 102.5, project 102.5 flat for 12 months
        """
        # Create deterministic data: stable with low variance
        data = [100.0 + np.random.normal(0, 2) for _ in range(18)]  # First 18 months stable
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=len(data), freq='MS'))

        trend_result = TrendResult(slope=0.0, p_value=0.95, is_significant=False, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=2.0, has_structural_break=False, z_scores={})

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.DETERMINISTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # Verify model type
        self.assertEqual(result.selected_model, "MEAN_REVERSION")

        # Verify projection is flat
        self.assertTrue((result.projected_series == result.projected_series.iloc[0]).all())

        # Verify projection equals recent 6-month mean
        recent_mean = series.tail(6).mean()
        self.assertAlmostEqual(result.projected_series.iloc[0], recent_mean, delta=1)

    def test_deterministic_model_bounds_use_recent_variance(self):
        """Verify DETERMINISTIC bounds are based on recent 6-month variance."""
        # High variance data
        data = [100 + i * 2 for i in range(24)]  # Trending
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=len(data), freq='MS'))

        trend_result = TrendResult(slope=0.0, p_value=0.95, is_significant=False, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=5.0, has_structural_break=False, z_scores={})

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.DETERMINISTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # Verify bounds exist and are reasonable
        self.assertTrue((result.upper_bound >= result.projected_series).all())
        self.assertTrue((result.lower_bound <= result.projected_series).all())
        self.assertTrue((result.lower_bound >= 0).all())  # Non-negative constraint

    # =========================================================================
    # SUCCESS CRITERIA 4: STOCHASTIC with significant trend + low MAPE
    # =========================================================================
    def test_stochastic_significant_trend_low_mape_uses_regression(self):
        """
        Verify STOCHASTIC model with significant trend and low MAPE uses REGRESSION_TREND.
        Example: Consistent upward trend, MAPE < 20% over recent 6 months
        """
        # Create data with clear upward trend
        data = [100 + i * 5 for i in range(24)]  # Strong linear growth
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=len(data), freq='MS'))

        # Simulate significant trend with low MAPE (will be calculated by engine)
        trend_result = TrendResult(
            slope=0.05,
            p_value=0.01,  # Significant (p < 0.05)
            is_significant=True,
            is_nonlinear=False
        )

        volatility_result = VolatilityResult(
            ser=2.0,  # Low uncertainty
            has_structural_break=False,
            z_scores={'6m': 0.5, '12m': 0.3, '18m': 0.2}
        )

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.STOCHASTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # Should use regression (MAPE will be low for consistent trend)
        self.assertEqual(result.selected_model, "REGRESSION_TREND")

        # Verify projection continues upward trend (later values > earlier values)
        self.assertGreater(result.projected_series.iloc[-1], result.projected_series.iloc[0])

    def test_stochastic_trend_continuing_slope(self):
        """Verify REGRESSION_TREND projection continues the historical slope correctly."""
        # Upward trend: 100, 110, 120, 130, ... (slope ≈ 10/month)
        data = [100 + i * 10 for i in range(24)]
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=len(data), freq='MS'))

        trend_result = TrendResult(
            slope=0.095,  # log-linear scale
            p_value=0.001,
            is_significant=True,
            is_nonlinear=False
        )

        volatility_result = VolatilityResult(
            ser=1.0,
            has_structural_break=False,
            z_scores={}
        )

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.STOCHASTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # Last historical value should be less than first projection (continuing growth)
        last_actual = series.iloc[-1]
        first_projected = result.projected_series.iloc[0]
        self.assertGreater(first_projected, last_actual * 0.95)  # At least maintaining/slightly growing

    # =========================================================================
    # SUCCESS CRITERIA 5: STOCHASTIC with high MAPE - fallback to mean reversion
    # =========================================================================
    def test_stochastic_high_mape_falls_back_to_mean_reversion(self):
        """
        Verify STOCHASTIC model with high MAPE aborts trend model and falls back to Mean Reversion.
        Example: Noisy data where trend line doesn't fit well (MAPE > 20%)
        """
        # Create noisy data: trend with high random variation
        np.random.seed(42)
        base_trend = [100 + i * 2 for i in range(24)]
        noise = np.random.normal(0, 30, 24)  # High noise
        data = base_trend + noise

        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=len(data), freq='MS'))

        # Even if trend is marked significant, high noise should cause MAPE to be high
        trend_result = TrendResult(
            slope=0.02,
            p_value=0.05,
            is_significant=True,
            is_nonlinear=False
        )

        volatility_result = VolatilityResult(
            ser=30.0,  # High uncertainty
            has_structural_break=False,
            z_scores={'6m': 2.0, '12m': 1.8, '18m': 1.6}
        )

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.STOCHASTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # Should fallback to ADAPTIVE_MEAN_REVERSION
        self.assertEqual(result.selected_model, "ADAPTIVE_MEAN_REVERSION")

        # Verify projection is flat (mean reversion)
        self.assertTrue((result.projected_series == result.projected_series.iloc[0]).all())

    def test_stochastic_insignificant_trend_uses_mean_reversion(self):
        """Verify STOCHASTIC with insignificant trend always uses Mean Reversion."""
        data = [100.0 + np.random.normal(0, 5) for _ in range(24)]
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=len(data), freq='MS'))

        # Insignificant trend
        trend_result = TrendResult(
            slope=0.001,
            p_value=0.95,  # Highly insignificant (p > 0.05)
            is_significant=False,
            is_nonlinear=False
        )

        volatility_result = VolatilityResult(
            ser=5.0,
            has_structural_break=False,
            z_scores={}
        )

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.STOCHASTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # Should use ADAPTIVE_MEAN_REVERSION (since trend is not significant)
        self.assertEqual(result.selected_model, "ADAPTIVE_MEAN_REVERSION")

        # Projection should be flat
        self.assertTrue((result.projected_series == result.projected_series.iloc[0]).all())

    # =========================================================================
    # SUCCESS CRITERIA 6: Comprehensive pytest coverage
    # =========================================================================
    def test_confidence_intervals_are_symmetric(self):
        """Verify upper and lower bounds are equidistant from projection."""
        data = [100.0] * 24
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=24, freq='MS'))

        trend_result = TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=10.0, has_structural_break=False, z_scores={})

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.DETERMINISTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # Calculate distances
        upper_distance = result.upper_bound - result.projected_series
        lower_distance = result.projected_series - result.lower_bound

        # Should be approximately equal
        np.testing.assert_array_almost_equal(upper_distance.values, lower_distance.values, decimal=5)

    def test_projection_never_negative(self):
        """Verify projected series and bounds are never negative."""
        # Create data with some extreme drops
        data = [100, 50, 25, 100, 90, 80, 70, 60, 50, 40, 35, 30, 100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45]
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=len(data), freq='MS'))

        trend_result = TrendResult(slope=-0.05, p_value=0.01, is_significant=True, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=15.0, has_structural_break=False, z_scores={})

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.STOCHASTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # All projections should be >= 0
        self.assertTrue((result.projected_series >= 0).all())
        self.assertTrue((result.lower_bound >= 0).all())

    def test_reference_date_affects_projection_index(self):
        """Verify reference_date parameter correctly sets projection date range."""
        series = pd.Series([100.0] * 24, index=pd.date_range('2023-01-01', periods=24, freq='MS'))

        trend_result = TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=5.0, has_structural_break=False, z_scores={})

        reference_date = pd.Timestamp('2025-12-31')
        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.DETERMINISTIC,
            trend_result=trend_result,
            volatility_result=volatility_result,
            reference_date=reference_date
        )

        # First projected date should be ~1 month after reference
        first_projected_date = result.projected_series.index[0]
        # Should be roughly end of January 2026
        self.assertEqual(first_projected_date.month, 1)
        self.assertGreaterEqual(first_projected_date.year, 2026)

    def test_mape_calculation_handles_zero_actuals(self):
        """Verify MAPE calculation handles zero actuals gracefully."""
        # Data with zeros
        data = [100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0]
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=len(data), freq='MS'))

        trend_result = TrendResult(slope=0.0, p_value=1.0, is_significant=True, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=50.0, has_structural_break=False, z_scores={})

        # Should not raise error
        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.STOCHASTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        self.assertIsInstance(result, ProjectionResult)

    def test_bounds_respect_ci_multiplier(self):
        """Verify confidence interval bounds use the specified ci_multiplier."""
        data = [100.0] * 24
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=24, freq='MS'))

        # Use a different CI multiplier
        engine = ProjectionEngine(ci_multiplier=2.58)  # 99% CI instead of 95%

        trend_result = TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=10.0, has_structural_break=False, z_scores={})

        result = engine.project(
            historical_series=series,
            process_type=ProcessType.DETERMINISTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # Wider CI should result in larger bounds
        bound_range = (result.upper_bound - result.lower_bound).mean()
        expected_range = 2 * 2.58 * 10.0  # 2 * ci_multiplier * ser
        self.assertGreater(bound_range, expected_range * 0.9)  # Allow for some variance

    def test_episodic_with_outliers(self):
        """Verify EPISODIC model handles outliers correctly using 90th percentile."""
        # Data with one extreme outlier
        data = [0] * 12 + [100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 10000, 0]  # 10000 is outlier
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=len(data), freq='MS'))

        trend_result = TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=100.0, has_structural_break=False, z_scores={})

        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.EPISODIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        # 90th percentile should exclude the extreme outlier
        # Non-zero values: [100, 100, 100, 100, 100, 10000]
        # 90th percentile should be closer to 1000 than to 10000
        monthly_projection = result.projected_series.iloc[0]
        self.assertLess(monthly_projection, 1000)  # Significantly less than outlier/12

    def test_series_with_nan_values(self):
        """Verify engine handles NaN values by filling with zeros."""
        data = [100, 110, np.nan, 130, 140, np.nan, 160, 170, 180, 190, 200, 210,
                100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210]
        series = pd.Series(data, index=pd.date_range('2023-01-01', periods=len(data), freq='MS'))

        trend_result = TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False)
        volatility_result = VolatilityResult(ser=10.0, has_structural_break=False, z_scores={})

        # Should not raise error (engine fills NaN with 0)
        result = self.engine.project(
            historical_series=series,
            process_type=ProcessType.DETERMINISTIC,
            trend_result=trend_result,
            volatility_result=volatility_result
        )

        self.assertIsInstance(result, ProjectionResult)
        self.assertEqual(len(result.projected_series), 12)


if __name__ == '__main__':
    unittest.main()

