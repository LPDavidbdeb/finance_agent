"""
EPIC 3.2: External Normalization Engine

This module provides logic to classify spending growth by comparing a category's
spend slope (Log-Linear trend) against an external benchmark (CPI, Income Growth, etc.).

Classification Logic:
- INFLATION_TRACKED: Category growth within tolerance of benchmark
- REAL_GROWTH: Category outpacing the benchmark
- EFFICIENCY_GAIN: Category growing slower than benchmark (cost reduction)
"""

from typing import Tuple
from decimal import Decimal


def classify_growth(
    category_slope: float,
    benchmark_slope: float,
    tolerance: float = 0.02
) -> str:
    """
    Classify spending growth by comparing category slope to external benchmark.

    The tolerance parameter defines the acceptable deviation band. If the category
    slope falls within [benchmark - tolerance, benchmark + tolerance], the category
    is considered to be tracking inflation.

    Args:
        category_slope: Log-linear regression slope of the spending category
        benchmark_slope: External baseline slope (e.g., CPI inflation rate)
        tolerance: Acceptable deviation band (default 2%, or 0.02)

    Returns:
        str: One of "REAL_GROWTH", "INFLATION_TRACKED", or "EFFICIENCY_GAIN"

    Examples:
        >>> classify_growth(0.06, 0.03, 0.02)  # 6% vs 3% CPI
        'REAL_GROWTH'

        >>> classify_growth(0.03, 0.03, 0.02)  # 3% vs 3% CPI
        'INFLATION_TRACKED'

        >>> classify_growth(0.009, 0.03, 0.02)  # 0.9% vs 3% CPI
        'EFFICIENCY_GAIN'
    """
    # Calculate deviation from benchmark
    deviation = category_slope - benchmark_slope

    # Check thresholds with tolerance
    if abs(deviation) <= tolerance:
        # Within tolerance band → tracking inflation
        return "INFLATION_TRACKED"
    elif deviation > tolerance:
        # Above benchmark + tolerance → real growth
        return "REAL_GROWTH"
    else:
        # Below benchmark - tolerance → efficiency gain
        return "EFFICIENCY_GAIN"


def classify_growth_with_confidence(
    category_slope: float,
    benchmark_slope: float,
    category_slope_std_err: float = None,
    tolerance: float = 0.02
) -> Tuple[str, dict]:
    """
    Classify growth and return confidence/uncertainty information.

    This extended version returns both the classification and metadata about
    the confidence of the classification based on statistical uncertainty.

    Args:
        category_slope: Log-linear regression slope of the spending category
        benchmark_slope: External baseline slope
        category_slope_std_err: Standard error of the category slope (for confidence intervals)
        tolerance: Acceptable deviation band (default 2%)

    Returns:
        Tuple[str, dict]: Classification and metadata dict with:
            - classification: "REAL_GROWTH", "INFLATION_TRACKED", or "EFFICIENCY_GAIN"
            - deviation: Actual deviation from benchmark
            - is_certain: Whether classification is statistically robust
            - confidence_notes: Text description of confidence level

    Examples:
        >>> classify_growth_with_confidence(0.05, 0.03, 0.01)
        ('REAL_GROWTH', {
            'deviation': 0.02,
            'is_certain': True,
            'confidence_notes': 'Statistically significant real growth detected'
        })
    """
    classification = classify_growth(category_slope, benchmark_slope, tolerance)
    deviation = category_slope - benchmark_slope

    # Determine confidence based on standard error if provided
    is_certain = True
    confidence_notes = ""

    if category_slope_std_err is not None:
        # If slope ± 2 std errors crosses the classification boundary, uncertain
        upper_bound = category_slope + (2 * category_slope_std_err)
        lower_bound = category_slope - (2 * category_slope_std_err)

        # Check if bounds cross classification boundaries
        lower_classification = classify_growth(lower_bound, benchmark_slope, tolerance)
        upper_classification = classify_growth(upper_bound, benchmark_slope, tolerance)

        if lower_classification != classification or upper_classification != classification:
            is_certain = False
            confidence_notes = "Classification uncertain due to statistical overlap"
        else:
            confidence_notes = f"Robust classification (±{2*category_slope_std_err:.4f} std error)"
    else:
        confidence_notes = "No uncertainty estimate provided"

    return classification, {
        'deviation': round(deviation, 4),
        'is_certain': is_certain,
        'confidence_notes': confidence_notes,
        'category_slope': category_slope,
        'benchmark_slope': benchmark_slope,
        'tolerance': tolerance,
    }


def benchmark_slope_to_decimal(benchmark_slope: float) -> Decimal:
    """
    Convert benchmark slope (float) to Decimal for database persistence.

    Ensures precision in database storage using DecimalField.

    Args:
        benchmark_slope: Float slope value

    Returns:
        Decimal: Decimal representation with 4 decimal places
    """
    return Decimal(str(round(benchmark_slope, 4)))


# =============================================================================
# Benchmark Presets (Common External Baselines)
# =============================================================================

BENCHMARK_PRESETS = {
    "CPI_US_2024": 0.0318,  # Approximate US CPI 2024
    "CPI_CA_2024": 0.0250,  # Approximate Canadian CPI 2024
    "INFLATION_LOW": 0.0200,  # 2% (typical conservative inflation target)
    "INFLATION_MODERATE": 0.0300,  # 3% (moderate inflation)
    "INFLATION_HIGH": 0.0500,  # 5% (elevated inflation)
    "INCOME_GROWTH_TYPICAL": 0.0300,  # 3% typical wage growth
    "WAGE_GROWTH_CA_2024": 0.0285,  # Canadian wage growth estimate
    "ZERO": 0.0000,  # No growth benchmark
}


def get_benchmark_slope(
    benchmark_name: str = "CPI_CA_2024",
    custom_value: float = None
) -> float:
    """
    Retrieve a benchmark slope value by name or custom value.

    Args:
        benchmark_name: Name of preset benchmark (see BENCHMARK_PRESETS)
        custom_value: Optional override value (if provided, benchmark_name is ignored)

    Returns:
        float: The benchmark slope value

    Raises:
        ValueError: If benchmark_name not found and no custom_value provided

    Examples:
        >>> get_benchmark_slope("CPI_CA_2024")
        0.025

        >>> get_benchmark_slope(custom_value=0.035)
        0.035
    """
    if custom_value is not None:
        return custom_value

    if benchmark_name not in BENCHMARK_PRESETS:
        raise ValueError(
            f"Unknown benchmark '{benchmark_name}'. "
            f"Available: {list(BENCHMARK_PRESETS.keys())}"
        )

    return BENCHMARK_PRESETS[benchmark_name]


if __name__ == "__main__":
    # Self-test examples
    print("=== Growth Classification Examples ===\n")

    test_cases = [
        (0.06, 0.03, "Real Growth: 6% category exceeds 3% benchmark by more than tolerance"),
        (0.03, 0.03, "Inflation Tracked: 3% category = 3% benchmark"),
        (0.025, 0.03, "Inflation Tracked: 2.5% within 2% tolerance of 3%"),
        (0.009, 0.03, "Efficiency Gain: 0.9% is more than 2% below 3% benchmark"),
        (0.00, 0.03, "Efficiency Gain: 0% much slower than 3% benchmark"),
        (-0.01, 0.03, "Efficiency Gain: -1% deflation vs 3% inflation"),
    ]

    for cat_slope, bench_slope, description in test_cases:
        classification = classify_growth(cat_slope, bench_slope)
        print(f"{description}")
        print(f"  → Classification: {classification}\n")

    # Test with confidence
    print("=== Classification with Confidence ===\n")
    classification, metadata = classify_growth_with_confidence(
        0.05, 0.03, category_slope_std_err=0.005
    )
    print(f"Classification: {classification}")
    print(f"Metadata: {metadata}")

