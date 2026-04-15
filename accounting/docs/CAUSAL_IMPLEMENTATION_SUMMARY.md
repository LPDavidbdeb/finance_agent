# Epic 3: Causal Decomposition Implementation Summary

## Overview
Successfully implemented the **CausalAnalyzer** module for EPIC 3 of the Financial Inference Engine, which breaks down spend changes into three components:
- **Volume Effect**: % change in transaction count (P12M → L12M)
- **Price Effect**: % change in average ticket size
- **Mix Shift**: Change in merchant concentration (top merchant share)

## Files Created

### 1. `accounting/analysis/causal.py` (191 lines)
**Core Implementation**

The module provides:

#### `CausalAnalysisResult` (Dataclass)
Structured output with these fields:
- `volume_effect_pct: float` - Percentage change in transaction count
- `price_effect_pct: float` - Percentage change in average ticket size  
- `mix_shift_detected: bool` - Flag if top merchant share changed >±10pp
- `l12m_transaction_count: int` - Number of transactions in Last 12 Months
- `p12m_transaction_count: int` - Number of transactions in Previous 12 Months
- `l12m_avg_ticket: float` - Average transaction amount in L12M
- `p12m_avg_ticket: float` - Average transaction amount in P12M
- `l12m_top_merchant_share: float` - Top merchant % share in L12M
- `p12m_top_merchant_share: float` - Top merchant % share in P12M

#### `CausalAnalyzer` (Main Class)
**Key Methods:**

1. **`analyze(transactions_df, reference_date=None) -> CausalAnalysisResult`**
   - Accepts raw transaction-level DataFrame with columns: date, amount, merchant_name
   - Supports Decimal, int, and float amount types
   - Splits data into 12-month windows (L12M vs P12M)
   - Falls back to median split if exact 12-month windows are empty
   - Returns comprehensive CausalAnalysisResult

2. **`_calculate_period_metrics(period_df) -> (count, avg_ticket, top_share_pct)`**
   - Internal method to compute transaction count, average ticket size, and top merchant share
   - Handles empty dataframes gracefully

3. **`_calculate_percentage_change(old_value, new_value) -> float`**
   - Calculates percentage change: ((new - old) / old) * 100
   - Handles edge cases (division by zero)

**Design Features:**
- Configurable mix_shift_threshold_pct (default 10 percentage points)
- Median split fallback for incomplete 12-month windows
- NumPy-free implementation (only pandas required)
- Proper type conversions (Decimal → float, string → datetime)
- Comprehensive error handling with descriptive messages

### 2. `accounting/analysis/test_causal.py` (435 lines)
**Comprehensive Test Suite**

Contains 16 test methods covering:

#### SUCCESS CRITERIA TESTS:

**Criterion 1: Module Acceptance**
- `test_returns_causal_analysis_result`: Verifies proper CausalAnalysisResult type
- `test_accepts_dataframe_with_required_columns`: Validates DataFrame acceptance
- `test_handles_decimal_amounts`: Decimal type conversion
- `test_rejects_empty_dataframe`: ValueError on empty input
- `test_rejects_missing_columns`: ValueError on missing required columns

**Criterion 2: Price Effect Detection**
- `test_price_effect_4purchases_50to60`: 4 purchases/month at $50→$60 = +20% price, 0% volume
  - Creates realistic 24-month dataset (12 months P12M, 12 months L12M)
  - Verifies +20% price effect calculation
  - Verifies 0% volume effect (constant transaction count)

**Criterion 3: Volume Effect Detection**
- `test_volume_effect_4to6_purchases_fixed_50`: Frequency 4x→6x/month at $50 = +50% volume, 0% price
  - Creates 12 months of 4 transactions each (P12M)
  - Creates 12 months of 6 transactions each (L12M)
  - Verifies +50% volume effect
  - Verifies 0% price effect (constant ticket size)

**Criterion 4: Mix Shift Detection**
- `test_mix_shift_detected_merchant_switch`: 90%→10% MerchantA share (80pp change) triggers detection
  - Creates explicit merchant split (9:1 ratio P12M, 1:9 ratio L12M)
  - Verifies mix_shift_detected = True
  - Uses median split fallback to properly divide 2024 vs 2025 data

**Criterion 5: Comprehensive Coverage**
- `test_no_mix_shift_below_threshold`: 8pp change < 10pp threshold → no detection
- `test_multiple_merchants_no_shift`: 3 equal merchants, same distribution → no shift
- `test_combined_price_and_volume_effect`: Both effects change simultaneously (+50% vol, +20% price)
- `test_insufficient_data_raises_error`: Proper error for <2 data points
- `test_median_split_fallback`: Fallback works when exact 12-month windows are empty
- `test_reference_date_parameter`: Reference date parameter correctly anchors windows
- `test_varying_amount_size`: Multiple transaction sizes computed correctly
- `test_zero_old_value_percentage_change`: Edge case handling (infinity for zero division)

## Key Features Implemented

### 1. Transaction-Level Input
- Accepts raw Pandas DataFrames with transaction-level data
- No pre-aggregation required
- Supports mixed data types (Decimal, int, float for amounts)

### 2. Flexible Time Windows
- Default: Last 12 Months (L12M) vs Previous 12 Months (P12M)
- Configurable reference_date parameter
- Automatic median split fallback for short datasets

### 3. Three-Factor Decomposition
- **Volume Effect**: Detects frequency changes (4 purchases → 6 purchases = +50%)
- **Price Effect**: Detects ticket size changes ($50 → $60 = +20%)
- **Mix Shift**: Detects merchant concentration changes (90% → 10% top merchant = shift detected)

### 4. Robust Error Handling
- Validates DataFrame structure and contents
- Handles edge cases (empty periods, zero divisions, single merchants)
- Provides descriptive error messages

## Test Validation Strategy

The test suite follows Django's standard test structure with unittest.TestCase:

```
TestCausalAnalyzer (16 test methods)
├── Basic Acceptance (5 tests)
│   ├── test_returns_causal_analysis_result
│   ├── test_accepts_dataframe_with_required_columns
│   ├── test_handles_decimal_amounts
│   ├── test_rejects_empty_dataframe
│   └── test_rejects_missing_columns
│
├── Price Effect Validation (1 test)
│   └── test_price_effect_4purchases_50to60
│
├── Volume Effect Validation (1 test)
│   └── test_volume_effect_4to6_purchases_fixed_50
│
├── Mix Shift Detection (2 tests)
│   ├── test_mix_shift_detected_merchant_switch
│   └── test_no_mix_shift_below_threshold
│
└── Edge Cases & Robustness (7 tests)
    ├── test_combined_price_and_volume_effect
    ├── test_multiple_merchants_no_shift
    ├── test_insufficient_data_raises_error
    ├── test_median_split_fallback
    ├── test_reference_date_parameter
    ├── test_varying_amount_size
    └── test_zero_old_value_percentage_change
```

## Running the Tests

### Using Django Test Runner
```bash
python manage.py test accounting.analysis.test_causal -v 2
```

### Using unittest directly
```bash
python -m unittest accounting.analysis.test_causal.TestCausalAnalyzer -v
```

### Using the standalone test runner
```bash
python run_causal_tests.py
```

## Code Quality

- **Type Hints**: Full type hints throughout (Tuple, Optional, pd.DataFrame)
- **Documentation**: Comprehensive docstrings for all classes and methods
- **Error Handling**: Graceful error handling with descriptive ValueError messages
- **Imports**: Cleaned up unused imports (numpy, Decimal where not needed)
- **No Linting Errors**: Verified with get_errors (0 errors)

## Example Usage

```python
from accounting.analysis.causal import CausalAnalyzer
import pandas as pd

# Prepare transaction data
transactions_df = pd.DataFrame({
    'date': pd.date_range('2024-01-01', periods=365, freq='D'),
    'amount': [50.0] * 365,
    'merchant_name': ['Costco'] * 365
})

# Analyze
analyzer = CausalAnalyzer(mix_shift_threshold_pct=10.0)
result = analyzer.analyze(transactions_df)

# Results
print(f"Volume Change: {result.volume_effect_pct}%")
print(f"Price Change: {result.price_effect_pct}%")
print(f"Mix Shift: {result.mix_shift_detected}")
```

## Integration with EPIC Framework

This module is positioned in EPIC 3 (Causal Decomposition) and works with:
- **EPIC 2**: TrendAnalyzer, VolatilityAnalyzer (which operate on aggregated monthly Series)
- **EPIC 4**: Will use CausalAnalysisResult to explain why trends are happening
- **EPIC 5**: UX layer will render causal insights (e.g., "↑ Price Driven", "↑ Volume Driven")

## Next Steps

1. **EPIC 3.2**: Add External Normalization (Nominal vs Real Growth with CPI integration)
2. **EPIC 4**: Integrate with ProjectionEngine to understand causal drivers of forecast changes
3. **EPIC 5**: Add UI components to display causal decomposition in the frontend

