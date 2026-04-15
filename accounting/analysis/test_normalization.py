"""
Tests for EPIC 3.2: External Normalization Engine

Tests the classification logic, benchmark presets, and persistence mechanism.
"""

from decimal import Decimal
from django.test import TestCase

from accounting.analysis.normalization import (
    classify_growth,
    classify_growth_with_confidence,
    benchmark_slope_to_decimal,
    get_benchmark_slope,
    BENCHMARK_PRESETS,
)


class NormalizationClassificationTestCase(TestCase):
    """Test suite for growth classification logic."""

    def test_real_growth_classification(self):
        """Verify category growth above benchmark + tolerance is classified as REAL_GROWTH."""
        # Category 6% vs 3% benchmark with 2% tolerance
        # 6% - 3% = 3%, which exceeds tolerance of 2%
        classification = classify_growth(0.06, 0.03, tolerance=0.02)
        self.assertEqual(classification, "REAL_GROWTH")

    def test_real_growth_with_higher_margin(self):
        """Verify clear real growth (well above tolerance)."""
        # Category 7% vs 3% benchmark
        # 7% - 3% = 4%, well above 2% tolerance
        classification = classify_growth(0.07, 0.03, tolerance=0.02)
        self.assertEqual(classification, "REAL_GROWTH")

    def test_inflation_tracked_exact_match(self):
        """Verify category matching benchmark is classified as INFLATION_TRACKED."""
        # Category 3% vs 3% benchmark = 0% deviation (within tolerance)
        classification = classify_growth(0.03, 0.03, tolerance=0.02)
        self.assertEqual(classification, "INFLATION_TRACKED")

    def test_inflation_tracked_within_tolerance_above(self):
        """Verify category above benchmark but within tolerance."""
        # Category 4% vs 3% benchmark
        # 4% - 3% = 1%, within 2% tolerance
        classification = classify_growth(0.04, 0.03, tolerance=0.02)
        self.assertEqual(classification, "INFLATION_TRACKED")

    def test_inflation_tracked_within_tolerance_below(self):
        """Verify category below benchmark but within tolerance."""
        # Category 2% vs 3% benchmark
        # 2% - 3% = -1%, within 2% tolerance
        classification = classify_growth(0.02, 0.03, tolerance=0.02)
        self.assertEqual(classification, "INFLATION_TRACKED")

    def test_inflation_tracked_at_tolerance_boundary_positive(self):
        """Verify exact tolerance boundary (positive) is INFLATION_TRACKED."""
        # Category 5% vs 3% benchmark with 2% tolerance
        # 5% - 3% = 2%, exactly at boundary → INFLATION_TRACKED
        classification = classify_growth(0.05, 0.03, tolerance=0.02)
        # Note: >= comparison means exactly at boundary is INFLATION_TRACKED
        self.assertEqual(classification, "INFLATION_TRACKED")

    def test_inflation_tracked_at_tolerance_boundary_negative(self):
        """Verify exact tolerance boundary (negative) is INFLATION_TRACKED."""
        # Category 1% vs 3% benchmark with 2% tolerance
        # 1% - 3% = -2%, exactly at boundary → INFLATION_TRACKED
        classification = classify_growth(0.01, 0.03, tolerance=0.02)
        self.assertEqual(classification, "INFLATION_TRACKED")

    def test_efficiency_gain_classification(self):
        """Verify category growth below benchmark - tolerance is EFFICIENCY_GAIN."""
        # Category 1% vs 3% benchmark with 2% tolerance
        # 1% - 3% = -2%, which exceeds negative tolerance
        classification = classify_growth(0.01, 0.03, tolerance=0.02)
        # Note: At boundary, should be INFLATION_TRACKED
        # Just below boundary:
        classification = classify_growth(0.009, 0.03, tolerance=0.02)
        self.assertEqual(classification, "EFFICIENCY_GAIN")

    def test_efficiency_gain_with_deflation(self):
        """Verify deflation is classified as EFFICIENCY_GAIN when below benchmark."""
        # Category -1% vs 3% benchmark
        # -1% - 3% = -4%, well below tolerance
        classification = classify_growth(-0.01, 0.03, tolerance=0.02)
        self.assertEqual(classification, "EFFICIENCY_GAIN")

    def test_efficiency_gain_with_zero_growth(self):
        """Verify zero growth vs positive benchmark is EFFICIENCY_GAIN."""
        # Category 0% vs 3% benchmark
        # 0% - 3% = -3%, well below tolerance
        classification = classify_growth(0.00, 0.03, tolerance=0.02)
        self.assertEqual(classification, "EFFICIENCY_GAIN")

    def test_custom_tolerance(self):
        """Verify custom tolerance parameter works."""
        # With 1% tolerance (stricter)
        classification = classify_growth(0.04, 0.03, tolerance=0.01)
        self.assertEqual(classification, "INFLATION_TRACKED")  # exactly at boundary

        classification = classify_growth(0.041, 0.03, tolerance=0.01)
        self.assertEqual(classification, "REAL_GROWTH")  # just above boundary

        # With 5% tolerance (more lenient)
        classification = classify_growth(0.08, 0.03, tolerance=0.05)
        self.assertEqual(classification, "INFLATION_TRACKED")  # 5% within 5% tolerance

    def test_negative_benchmark(self):
        """Verify handling of negative benchmark (e.g., deflation baseline)."""
        # Category 1% vs -2% benchmark (deflation baseline)
        # 1% - (-2%) = 3%, well above 2% tolerance
        classification = classify_growth(0.01, -0.02, tolerance=0.02)
        self.assertEqual(classification, "REAL_GROWTH")

    def test_both_negative_slopes(self):
        """Verify both negative slopes are handled correctly."""
        # Category -1% vs -3% benchmark
        # -1% - (-3%) = 2%, equals tolerance boundary
        classification = classify_growth(-0.01, -0.03, tolerance=0.02)
        self.assertEqual(classification, "INFLATION_TRACKED")


class NormalizationConfidenceTestCase(TestCase):
    """Test suite for classification with confidence metrics."""

    def test_robust_classification_no_uncertainty(self):
        """Verify robust classification when no uncertainty data provided."""
        classification, metadata = classify_growth_with_confidence(
            0.06, 0.03, category_slope_std_err=None, tolerance=0.02
        )

        self.assertEqual(classification, "REAL_GROWTH")
        self.assertIn('deviation', metadata)
        self.assertIn('is_certain', metadata)
        self.assertIn('confidence_notes', metadata)
        self.assertEqual(metadata['is_certain'], True)
        self.assertAlmostEqual(metadata['deviation'], 0.03, places=4)

    def test_robust_classification_with_small_error(self):
        """Verify robust classification when standard error is small relative to deviation."""
        # Category 6% vs 3% with small uncertainty (0.4% std error)
        classification, metadata = classify_growth_with_confidence(
            0.06, 0.03, category_slope_std_err=0.004, tolerance=0.02
        )

        self.assertEqual(classification, "REAL_GROWTH")
        self.assertTrue(metadata['is_certain'])
        # Bounds: [6% - 2*0.4%, 6% + 2*0.4%] = [5.2%, 6.8%]
        # Both bounds remain above benchmark + tolerance (5.0%)

    def test_uncertain_classification_with_large_error(self):
        """Verify uncertain classification when error bounds cross boundary."""
        # Category 3.5% vs 3% with large uncertainty (1.5% std error)
        # Deviation is 0.5%, within tolerance, but uncertainty is large
        classification, metadata = classify_growth_with_confidence(
            0.035, 0.03, category_slope_std_err=0.015, tolerance=0.02
        )

        self.assertEqual(classification, "INFLATION_TRACKED")
        # Bounds: [3.5% - 3%, 3.5% + 3%] = [0.5%, 6.5%]
        # This spans both INFLATION_TRACKED and REAL_GROWTH regions
        self.assertFalse(metadata['is_certain'])

    def test_confidence_metadata_completeness(self):
        """Verify all metadata fields are present."""
        classification, metadata = classify_growth_with_confidence(
            0.06, 0.03, category_slope_std_err=0.01, tolerance=0.02
        )

        required_keys = {
            'deviation', 'is_certain', 'confidence_notes',
            'category_slope', 'benchmark_slope', 'tolerance'
        }
        self.assertTrue(required_keys.issubset(set(metadata.keys())))


class BenchmarkSlopeConversionTestCase(TestCase):
    """Test suite for benchmark slope conversion utilities."""

    def test_float_to_decimal_conversion(self):
        """Verify float to Decimal conversion maintains precision."""
        result = benchmark_slope_to_decimal(0.0318)
        self.assertIsInstance(result, Decimal)
        self.assertEqual(result, Decimal('0.0318'))

    def test_float_to_decimal_rounding(self):
        """Verify rounding to 4 decimal places."""
        result = benchmark_slope_to_decimal(0.031234567)
        self.assertEqual(result, Decimal('0.0312'))

    def test_decimal_roundtrip(self):
        """Verify conversion preserves value after roundtrip."""
        original = 0.025
        decimal = benchmark_slope_to_decimal(original)
        back_to_float = float(decimal)
        self.assertAlmostEqual(original, back_to_float, places=4)


class BenchmarkPresetsTestCase(TestCase):
    """Test suite for benchmark preset utilities."""

    def test_get_benchmark_slope_by_name_cpi_ca(self):
        """Verify preset retrieval for Canadian CPI."""
        slope = get_benchmark_slope("CPI_CA_2024")
        self.assertEqual(slope, BENCHMARK_PRESETS["CPI_CA_2024"])
        self.assertAlmostEqual(slope, 0.025, places=3)

    def test_get_benchmark_slope_by_name_cpi_us(self):
        """Verify preset retrieval for US CPI."""
        slope = get_benchmark_slope("CPI_US_2024")
        self.assertEqual(slope, BENCHMARK_PRESETS["CPI_US_2024"])
        self.assertAlmostEqual(slope, 0.0318, places=4)

    def test_get_benchmark_slope_custom_override(self):
        """Verify custom value overrides preset name."""
        slope = get_benchmark_slope("CPI_CA_2024", custom_value=0.035)
        self.assertEqual(slope, 0.035)

    def test_get_benchmark_slope_zero_preset(self):
        """Verify zero preset for no-growth baseline."""
        slope = get_benchmark_slope("ZERO")
        self.assertEqual(slope, 0.0)

    def test_get_benchmark_slope_invalid_name(self):
        """Verify error when invalid preset name provided."""
        with self.assertRaises(ValueError):
            get_benchmark_slope("INVALID_PRESET")

    def test_get_benchmark_slope_all_presets_accessible(self):
        """Verify all presets can be retrieved by name."""
        for preset_name in BENCHMARK_PRESETS.keys():
            slope = get_benchmark_slope(preset_name)
            self.assertEqual(slope, BENCHMARK_PRESETS[preset_name])


class NormalizationIntegrationTestCase(TestCase):
    """Integration tests combining multiple components."""

    def test_classification_with_ca_inflation_benchmark(self):
        """Verify real-world scenario: Canadian household spending vs CPI."""
        # Groceries: 3.2% annual growth
        # Canadian CPI 2024: ~2.5%
        # Tolerance: 2%
        ca_cpi = get_benchmark_slope("CPI_CA_2024")
        classification = classify_growth(0.032, ca_cpi, tolerance=0.02)
        self.assertEqual(classification, "INFLATION_TRACKED")

    def test_classification_with_us_inflation_benchmark(self):
        """Verify real-world scenario: Category growth vs US CPI."""
        # Utilities: 3.5% growth
        # US CPI 2024: ~3.18%
        # Tolerance: 2%
        us_cpi = get_benchmark_slope("CPI_US_2024")
        classification = classify_growth(0.035, us_cpi, tolerance=0.02)
        self.assertEqual(classification, "INFLATION_TRACKED")

    def test_classification_with_wage_growth_benchmark(self):
        """Verify classification against wage growth benchmark."""
        # Dining: 5% growth (beyond wage growth)
        # Wage growth: ~2.85%
        # This could indicate discretionary increase
        wage_growth = get_benchmark_slope("WAGE_GROWTH_CA_2024")
        classification = classify_growth(0.05, wage_growth, tolerance=0.02)
        self.assertEqual(classification, "REAL_GROWTH")

    def test_decimal_persistence_roundtrip(self):
        """Verify Decimal conversion preserves precision for database storage."""
        benchmark = get_benchmark_slope("CPI_CA_2024")
        decimal_benchmark = benchmark_slope_to_decimal(benchmark)

        # Simulate database save/load
        back_to_float = float(decimal_benchmark)
        classification = classify_growth(0.032, back_to_float, tolerance=0.02)

        self.assertEqual(classification, "INFLATION_TRACKED")

