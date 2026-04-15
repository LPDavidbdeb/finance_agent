# EPIC 3.2: External Normalization Engine - Implementation Summary

## Overview

The External Normalization Engine classifies spending growth by comparing a category's log-linear trend slope against an external benchmark (CPI, wage growth, etc.). This allows the system to answer: "Is the category growing faster than inflation, tracking inflation, or becoming more efficient?"

## Architecture

### Three-Layer Design

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CLASSIFICATION LOGIC (normalization.py)                  │
│    Deterministic algorithm: classify_growth(slope, benchmark)│
│    Input: Two floats + tolerance                            │
│    Output: Classification string                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 2. PERSISTENCE INTERFACE (insights.py)                      │
│    InsightEngine.build_persistence_kwargs()                 │
│    Input: CategoryProfile + normalization_result dict       │
│    Output: Dict with benchmark_slope, benchmark_classification
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 3. DATABASE STORAGE (models.py + migration)                 │
│    InsightFact fields:                                      │
│    - benchmark_slope (DecimalField)                         │
│    - benchmark_classification (CharField with choices)      │
└─────────────────────────────────────────────────────────────┘
```

## Classification Logic

### Algorithm

```python
Let tolerance = 0.02 (2% default)
Let deviation = category_slope - benchmark_slope

If abs(deviation) <= tolerance:
    Return "INFLATION_TRACKED"
Else If deviation > tolerance:
    Return "REAL_GROWTH"
Else (deviation < -tolerance):
    Return "EFFICIENCY_GAIN"
```

### Three Classification States

| Classification | Condition | Meaning |
|---|---|---|
| **REAL_GROWTH** | `category > benchmark + tolerance` | Spending grows faster than inflation (discretionary increase or market forces) |
| **INFLATION_TRACKED** | `benchmark - tolerance <= category <= benchmark + tolerance` | Spending grows with inflation (economically tracking baseline) |
| **EFFICIENCY_GAIN** | `category < benchmark - tolerance` | Spending grows slower than inflation (cost savings or behavior change) |

### Example Scenarios

**Scenario 1: Groceries in 2024**
```
Category Growth (slope): 3.2% (log-linear trend)
CPI Benchmark: 2.5% (Canadian CPI)
Tolerance: 2%

Deviation: 3.2% - 2.5% = 0.7%
abs(0.7%) <= 2%? YES
Classification: INFLATION_TRACKED

Interpretation: Food prices rising with general inflation.
```

**Scenario 2: Dining Out (Discretionary)**
```
Category Growth: 5.0%
CPI Benchmark: 2.5%
Tolerance: 2%

Deviation: 5.0% - 2.5% = 2.5%
2.5% > 2%? YES
Classification: REAL_GROWTH

Interpretation: Dining spending outpacing inflation (more frequent visits or better restaurants).
```

**Scenario 3: Utilities (Efficiency Gain)**
```
Category Growth: 1.0%
CPI Benchmark: 2.5%
Tolerance: 2%

Deviation: 1.0% - 2.5% = -1.5%
abs(-1.5%) <= 2%? YES
Classification: INFLATION_TRACKED

Interpretation: Utilities growing slower than inflation (home efficiency improvements working).

But if Growth: 0.2%:
Deviation: 0.2% - 2.5% = -2.3%
-2.3% < -2%? YES
Classification: EFFICIENCY_GAIN

Interpretation: Utilities barely growing; significant efficiency gains achieved.
```

## Database Changes

### Schema Update

**New InsightFact Fields:**

```python
benchmark_slope = models.DecimalField(
    max_digits=7,           # Range: -999.9999 to 9999.9999
    decimal_places=4,       # Precision: 0.0001 (0.01%)
    null=True, blank=True,
    help_text="External baseline slope (e.g., CPI)"
)

benchmark_classification = models.CharField(
    max_length=50,
    null=True, blank=True,
    choices=[
        ('REAL_GROWTH', 'Real Growth'),
        ('INFLATION_TRACKED', 'Inflation Tracked'),
        ('EFFICIENCY_GAIN', 'Efficiency Gain'),
    ],
    help_text="Classification: REAL_GROWTH, INFLATION_TRACKED, or EFFICIENCY_GAIN"
)
```

### Migration

```bash
python manage.py makemigrations accounting -m "add_external_normalization_to_insightfact"
python manage.py migrate
```

Migration creates two nullable fields (allowing incremental adoption).

## API Exposure

### InsightResponseSchema Updated

**New Fields in API Response:**

```json
{
  "id": "Groceries",
  "categoryName": "Groceries",
  "insight_score": 75000.0,
  "materiality_pct": 15.0,
  "processType": "STOCHASTIC",
  "expertSummary": "...",
  "causal_volume_pct": 5.5,
  "causal_price_pct": 2.1,
  "projected_lower_bound": 5190.00,
  "projected_upper_bound": 5650.00,
  "benchmark_slope": 0.0250,
  "benchmark_classification": "INFLATION_TRACKED"
}
```

**Endpoints Affected:**
- GET /api/analysis/insights/top/ - returns updated schema
- GET /api/analysis/insights/latest/ - returns updated schema

## Persistence Handoff

### Updated build_persistence_kwargs()

```python
def build_persistence_kwargs(
    profile: CategoryProfile,
    projection_result: Optional[dict] = None,
    normalization_result: Optional[dict] = None
) -> dict:
    """
    Input:
        profile: CategoryProfile with trend/volatility/causal metrics
        projection_result: {'lower_bound': X, 'upper_bound': Y}
        normalization_result: {
            'benchmark_slope': 0.025,
            'benchmark_classification': 'INFLATION_TRACKED'
        }
    
    Output:
        Dict with all fields ready for InsightFact.objects.create()
    """
    persistence_kwargs = {
        'projected_value': profile.projected_value,
        'projected_lower_bound': projection_result.get('lower_bound'),
        'projected_upper_bound': projection_result.get('upper_bound'),
        'benchmark_slope': normalization_result.get('benchmark_slope'),
        'benchmark_classification': normalization_result.get('benchmark_classification'),
    }
    return persistence_kwargs
```

### Usage Example

```python
# In ETL pipeline (when normalization results available)
normalization_result = {
    'benchmark_slope': 0.025,
    'benchmark_classification': 'INFLATION_TRACKED'
}

persistence_kwargs = InsightEngine.build_persistence_kwargs(
    profile=category_profile,
    projection_result=projection,
    normalization_result=normalization_result
)

insight_fact = InsightFact.objects.create(**persistence_kwargs)
```

## Benchmark Presets

The normalization module includes common benchmark presets:

```python
BENCHMARK_PRESETS = {
    "CPI_US_2024": 0.0318,              # US CPI
    "CPI_CA_2024": 0.0250,              # Canadian CPI
    "INFLATION_LOW": 0.0200,            # 2% target
    "INFLATION_MODERATE": 0.0300,       # 3% moderate
    "INFLATION_HIGH": 0.0500,           # 5% elevated
    "INCOME_GROWTH_TYPICAL": 0.0300,    # 3% wage growth
    "WAGE_GROWTH_CA_2024": 0.0285,      # Canadian wages
    "ZERO": 0.0000,                     # No growth
}
```

**Usage:**
```python
from accounting.analysis.normalization import get_benchmark_slope

# By preset name
ca_cpi = get_benchmark_slope("CPI_CA_2024")  # → 0.025

# Custom override
custom = get_benchmark_slope(custom_value=0.035)  # → 0.035
```

## Future Integration Points

### For Pipeline Developers

When implementing the pipeline to provide benchmark data:

1. **Source benchmark data** (CPI, wage growth, etc.)
2. **Call classify_growth()** with category_slope and benchmark_slope
3. **Package result** in normalization_result dict
4. **Pass to build_persistence_kwargs()** for database storage

### Example Integration

```python
from accounting.analysis.normalization import classify_growth, get_benchmark_slope

# Step 1: Get the category's log-linear slope
category_slope = 0.032

# Step 2: Get benchmark (e.g., Canadian CPI)
benchmark_slope = get_benchmark_slope("CPI_CA_2024")

# Step 3: Classify
classification = classify_growth(category_slope, benchmark_slope)

# Step 4: Package for persistence
normalization_result = {
    'benchmark_slope': benchmark_slope,
    'benchmark_classification': classification
}

# Step 5: Persist
kwargs = InsightEngine.build_persistence_kwargs(
    profile=profile,
    normalization_result=normalization_result
)
InsightFact.objects.create(**kwargs)
```

## Testing

Comprehensive test suite in `accounting/analysis/test_normalization.py`:

- **NormalizationClassificationTestCase** (10 tests)
  - Tests all classification boundaries
  - Tests custom tolerance
  - Tests edge cases (negative slopes, exact boundaries)

- **NormalizationConfidenceTestCase** (3 tests)
  - Tests classification with statistical uncertainty
  - Verifies confidence metadata

- **BenchmarkSlopeConversionTestCase** (3 tests)
  - Tests float → Decimal conversion
  - Tests precision and rounding

- **BenchmarkPresetsTestCase** (6 tests)
  - Tests preset retrieval
  - Tests custom overrides
  - Tests error handling

- **NormalizationIntegrationTestCase** (4 tests)
  - Real-world scenarios
  - End-to-end persistence roundtrips

**Run tests:**
```bash
python manage.py test accounting.analysis.test_normalization -v 2
```

## Constraints & Design Decisions

### 1. Tolerance = 0.02 (2%) Default
**Rationale:** Balances sensitivity with noise immunity. CPI data has ~1-2% measurement uncertainty.

### 2. DecimalField for benchmark_slope
**Rationale:** Matches projected_*_bound precision. Ensures database consistency.

### 3. Nullable Fields (null=True, blank=True)
**Rationale:** Allows phased rollout. Old InsightFact rows without benchmarks still valid.

### 4. No Changes to Celery Tasks
**Constraint:** Normalization is stateless math. Pipeline orchestration unchanged.

### 5. Read-Only for Now
**Note:** Benchmark values injected from external source (planned). Engine designed to receive, not fetch.

## Extensibility

### Future Enhancements

1. **Confidence Intervals**
   - `classify_growth_with_confidence()` already supports std error
   - Can integrate with regression uncertainty

2. **Multi-Benchmark Comparison**
   - Could classify against multiple benchmarks simultaneously
   - Example: "vs CPI" AND "vs Wage Growth"

3. **Temporal Benchmarks**
   - Use inflation expectations (forward-looking)
   - Example: "BoC target rate" instead of realized CPI

4. **Category-Specific Benchmarks**
   - Different categories get different baselines
   - Example: Healthcare → medical inflation, Utilities → energy prices

5. **Comparative Analytics**
   - "Your Groceries vs. Canadian Household"
   - Benchmark against peer group instead of macro

## Related Documentation

- **EPIC 2.1:** Trend Analysis Framework (trend.py) - provides category_slope
- **EPIC 4.2:** Expert Summary Generation (insights.py) - will incorporate classification
- **Run Coherence:** InsightFact snapshot consistency (api.py) - guarantees data coherence
- **Persistence Pattern:** build_persistence_kwargs() - maps analytics → database

## Summary

EPIC 3.2 implements a clean, testable classification engine that:
- ✅ Classifies growth relative to external benchmarks
- ✅ Integrates seamlessly with persistence layer
- ✅ Exposes results via API for frontend consumption
- ✅ Ready for benchmark data injection from pipeline
- ✅ Zero impact on existing ETL orchestration

