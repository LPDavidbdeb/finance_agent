# ETL Pipeline Fixes Summary

## Problem Statement
The ETL pipeline was returning zero profiles due to Step-0 filters dropping all sparse/low-materiality test data. Two key issues were identified:

### Issue 1: Sparse Test Fixtures
- **Root Cause**: Test fixtures created only 1 transaction per month per category
- **Step-0 Filter**: Sparsity check fails if >30% of months have zero transactions
- **Impact**: All test data was being filtered out as "Sparse"

### Issue 2: Materiality Calculation Bug
- **Root Cause**: Total family spend calculation included ASSET accounts (bank) with negative amounts
- **Effect**: Materiality percentages calculated as millions instead of 0-100%
- **Impact**: CategoryProfile validation failed (requires 0 ≤ materiality_pct ≤ 100)

---

## Solutions Implemented

### 1. Enriched Test Fixtures (`accounting/tests_etl_pipeline.py`)

**Changed**: `_create_test_transactions()` method

```python
# BEFORE: 1 transaction per month
for month_offset in range(12):
    # Only 1 grocery txn + 1 utility txn per month
    JournalEntry.objects.create(...)

# AFTER: Multiple transactions per month
for month_offset in range(12):
    base_date = (...).replace(day=1)
    
    # Groceries: 4 transactions/month @ $550 = $2200/month
    for week in range(0, 4):
        transaction_date = base_date + timedelta(days=7 * week)
        # Create transaction...
    
    # Utilities: 2 transactions/month @ $600 = $1200/month
    for utility_idx in range(2):
        transaction_date = base_date + timedelta(days=15 * (utility_idx + 1))
        # Create transaction...
```

**Benefits**:
- ✅ Dense transactions: 100% of months have spending (0% sparse)
- ✅ High materiality: Groceries ≈65%, Utilities ≈35% (both >> 1% threshold)
- ✅ Realistic data: Mirrors actual household spending patterns

### 2. Fixed Materiality Calculation (`accounting/tasks.py`)

**Changed**: `_transform_through_pipeline()` function (lines 273-283)

```python
# BEFORE: Sum ALL accounts (including ASSET accounts with negatives)
total_family_spend = CategoryMonthlyStat.objects.filter(
    category_id__in=Account.objects.filter(family=family).values_list('id', flat=True)
).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('1')

# AFTER: Sum ONLY EXPENSE accounts
expense_accounts = Account.objects.filter(
    family=family,
    account_type=Account.AccountType.EXPENSE
).values_list('id', flat=True)

total_family_spend = CategoryMonthlyStat.objects.filter(
    category_id__in=expense_accounts
).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('1')
```

**Impact**:
- ✅ Correct materiality percentages (0-100% range)
- ✅ Prevents negative total spend issues
- ✅ More semantically correct (expenses only)

### 3. Filtered Data Extraction (`accounting/tasks.py`)

**Changed**: `_extract_category_data()` function (lines 168-184)

```python
# BEFORE: Extract ALL accounts
stats = CategoryMonthlyStat.objects.filter(
    category_id__in=Account.objects.filter(family=family).values_list('id', flat=True)
)

# AFTER: Extract ONLY EXPENSE accounts
expense_accounts = Account.objects.filter(
    family=family,
    account_type=Account.AccountType.EXPENSE
).values_list('id', flat=True)

stats = CategoryMonthlyStat.objects.filter(
    category_id__in=expense_accounts
)
```

**Benefits**:
- ✅ Prevents processing of ASSET accounts (bank accounts)
- ✅ Cleaner data pipeline
- ✅ Prevents negative amounts from breaking analysis

---

## Test Results

### ETL Pipeline Tests (accounting/tests_etl_pipeline.py)
✅ **14/14 tests passing**

Key tests that now pass:
- `test_rebuild_financial_insights_executes_successfully` - Full pipeline execution
- `test_extract_category_data_returns_dataframes` - Data extraction
- `test_rebuild_increases_insight_fact_count` - Insight generation
- `test_full_etl_pipeline_flow` - End-to-end integration test

### API Tests (accounting/analysis/test_api.py)
✅ **24/24 tests passing**

Key tests that now pass:
- `test_full_insights_pipeline` - Complete pipeline from profiles to response
- `test_response_schema_validation` - Pydantic schema validation
- `test_endpoint_logic_run_id_none_uses_latest` - Run coherence

### Quick Verification (test_etl_quick.py)
```
✅ Pipeline executed:
   - Families processed: 1
   - Insights created: 2
   - Analysis runs created: 1
```

---

## Step-0 Filter Behavior (Reference)

The ETL pipeline's Step-0 (Data Filtering & Sanity) applies three key checks:

### 1. Materiality Check (SignalFilter.classify_materiality)
- **Threshold**: 1.0% of total household spend
- **Status**: "Muted" (dropped) if below threshold
- **Fix**: Enriched fixtures ensure >1% for test categories

### 2. Sparsity Check (SignalFilter.classify_sparsity)
- **Threshold**: >30% zero months = "Sparse" (dropped)
- **Requirement**: ≥70% of months must have transactions
- **Fix**: Multiple transactions per month = 100% coverage (0% sparse)

### 3. Minimum Data Points
- **Requirement**: ≥2 monthly data points
- **Fix**: 12 months of data created per test

---

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `accounting/tests_etl_pipeline.py` | Enriched fixtures with multiple txns/month | 60-100 |
| `accounting/tasks.py` | Filter EXPENSE accounts + fix materiality | 273-284 & 175-187 |
| `test_etl_quick.py` | Quick verification script | Created |

---

## Validation Commands

```bash
# Run ETL pipeline tests
python manage.py test accounting.tests_etl_pipeline -v 2

# Run API tests
python manage.py test accounting.analysis.test_api -v 2

# Quick verification
python test_etl_quick.py
```

---

## Architecture Notes

The ETL pipeline now correctly:

1. **REFRESH**: Updates materialized view with latest ledger data
2. **EXTRACT**: Queries EXPENSE accounts only (no bank accounts)
3. **TRANSFORM**: Applies Step-0 filters (materiality, sparsity, sanity)
4. **LOAD**: Persists insights via bulk_create (append-only)

All operations are **family-scoped** (multi-tenant safe) and **append-only** (idempotent).

