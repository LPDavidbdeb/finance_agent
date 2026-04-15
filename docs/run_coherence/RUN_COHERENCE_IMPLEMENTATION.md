# Run Coherence Implementation Summary

## Overview
Successfully implemented run coherence enforcement in the Insights API to prevent Frankenstein responses when ETL runs fail halfway. The framework now guarantees snapshot-consistent reads based on a specific `AnalysisRun`.

## Changes Made

### 1. Updated `/api/analysis/insights/top/` Endpoint
**File:** `accounting/analysis/api.py` (lines 85-164)

#### Key Changes:
- **Added optional query parameter:** `run_id: Optional[int] = None`
- **Implemented coherence logic:**
  - If `run_id` is explicitly provided → filters to that specific run
  - If `run_id` is None (default) → automatically finds the most recently completed run via `AnalysisRun.objects.filter(family=family, status='SUCCEEDED').order_by("-completed_at", "-id").first()`
  - If no completed run exists → gracefully returns empty list `[]` (no 404/500)
  
#### Query Logic:
```python
# Determine which AnalysisRun to use for filtering
target_run_id = run_id
if target_run_id is None:
    # Find the most recently completed run for this family
    latest_run = (
        AnalysisRun.objects
        .filter(family=family, status=AnalysisRun.Status.SUCCEEDED)
        .order_by("-completed_at", "-id")
        .first()
    )
    # If no completed run exists, return empty list
    if latest_run is None:
        return []
    target_run_id = latest_run.id

# Query InsightFact for the specific run, maintaining family scoping
insights = (
    InsightFact.objects
    .filter(
        category__family=family,
        analysis_run_id=target_run_id
    )
    .select_related("category")
    .order_by("-insight_score", "category__name")[:top_n]
)
```

#### Security:
- **Family scoping preserved:** All queries include `category__family=family` to prevent cross-tenant data leaks
- **No data model changes:** Pydantic schemas remain unchanged
- **Read-only operation:** No Celery ETL tasks modified

### 2. Updated `/api/analysis/insights/latest/` Endpoint
**File:** `accounting/analysis/api.py` (lines 185-232)

#### Key Change:
- **Ordering field:** Changed from `-started_at` to `-completed_at` for consistency with `get_top_insights`

```python
run = (
    AnalysisRun.objects
    .filter(family=family, status=AnalysisRun.Status.SUCCEEDED)
    .order_by("-completed_at", "-id")  # Was: "-started_at"
    .first()
)
```

This endpoint already filters by `analysis_run=run`, making it snapshot-consistent by design.

## Acceptance Criteria Validation

### ✅ Criterion 1: Optional `run_id` Query Parameter
- Parameter added to function signature: `run_id: Optional[int] = None`
- Updated docstring documents the parameter and its behavior
- Fully backward compatible (defaults to None)

### ✅ Criterion 2: Coherence Logic Implementation
- **Explicit run_id:** InsightFact filtered to `analysis_run_id=target_run_id`
- **Default behavior:** Queries for most recent SUCCEEDED run
  - Filter: `status='SUCCEEDED'` (not RUNNING or FAILED)
  - Order: `-completed_at, -id` (most recent first)
  - Fallback: Returns `[]` if no completed run exists

### ✅ Criterion 3: Error Handling & Edge Cases
- **No completed run:** Returns graceful empty list `[]` (not 404 or 500)
- **Family scoping:** `.filter(category__family=family)` prevents cross-tenant leaks
- **Existing scoping maintained:** No regression in data isolation

## Test Coverage
**File:** `accounting/analysis/test_api.py` (new test class: `RunCoherenceTestCase`)

Added comprehensive test suite with 7 test methods:

1. **`test_run_id_parameter_filters_by_specific_run`**
   - Verifies explicit run_id filtering returns correct InsightFact rows
   - Tests that different runs return different results

2. **`test_default_uses_latest_completed_run`**
   - Confirms endpoint defaults to most recent SUCCEEDED run
   - Verifies completed_at ordering

3. **`test_graceful_handle_no_completed_run`**
   - Tests edge case: family with zero completed runs
   - Verifies graceful fallback behavior

4. **`test_family_scoping_prevents_cross_tenant_leak`**
   - Creates separate family with own AnalysisRun and InsightFact
   - Verifies data isolation via family scoping

5. **`test_endpoint_logic_run_id_none_uses_latest`**
   - Integration test simulating endpoint behavior with run_id=None
   - Verifies correct insights returned from latest run

6. **`test_endpoint_logic_run_id_explicit`**
   - Integration test simulating endpoint behavior with explicit run_id
   - Verifies correct insights returned from specified run

7. **`test_latest_snapshot_uses_completed_at`**
   - Validates /insights/latest/ endpoint ordering fix
   - Confirms completed_at field used instead of started_at

## Before/After Query Comparison

### Before (Vulnerable to Partial ETL):
```python
# Could pull "latest" row per category from mixed runs
latest_fact_for_category = InsightFact.objects.filter(
    category_id=OuterRef("category_id"),
    category__family=family,
).order_by("-computed_at", "-id").values("id")[:1]

latest_facts = (
    InsightFact.objects
    .filter(category__family=family, id=Subquery(latest_fact_for_category))
    .select_related("category")
)
# Result: Frankenstein response mixing facts from different runs
```

### After (Run-Coherent):
```python
# Guarantees all facts from a single coherent AnalysisRun
insights = (
    InsightFact.objects
    .filter(
        category__family=family,
        analysis_run_id=target_run_id  # Single run enforced
    )
    .select_related("category")
    .order_by("-insight_score", "category__name")[:top_n]
)
# Result: Snapshot-consistent reads from one coherent run
```

## API Usage Examples

### Example 1: Get Latest Insights (Default)
```
GET /api/analysis/insights/top/?top_n=5
```
Automatically uses most recent SUCCEEDED AnalysisRun. No run_id parameter needed.

### Example 2: Get Insights from Specific Run
```
GET /api/analysis/insights/top/?top_n=5&run_id=42
```
Returns insights only from AnalysisRun ID 42.

### Example 3: Get Latest Snapshot
```
GET /api/analysis/insights/latest/
```
Returns metadata (run_id, completed_at) plus insights from latest coherent run.

## Impact Assessment

### Security
- ✅ No new security vulnerabilities introduced
- ✅ Family scoping prevents cross-tenant data leaks
- ✅ Only read operations (no mutations)

### Performance
- ✅ No performance regression (simpler query than before)
- ✅ Direct `analysis_run_id` filter is indexed-friendly
- ✅ Single-run query avoids per-category subqueries

### Backward Compatibility
- ✅ `run_id` parameter is optional (defaults to None)
- ✅ Existing API clients continue to work unchanged
- ✅ New behavior is transparent (auto-selects latest run)

### Data Integrity
- ✅ Guarantees snapshot-consistent reads
- ✅ Prevents mixing facts from partial/failed runs
- ✅ Maintains audit trail via AnalysisRun versioning

## Constraints Adherence

- ✅ **Pydantic schemas unchanged:** InsightResponseSchema and LatestInsightsSnapshotSchema unmodified
- ✅ **No Celery tasks touched:** Ingestion pipeline unchanged
- ✅ **Read-only API fix:** No data model changes
- ✅ **Django Ninja compliance:** Uses @router.get decorator exclusively
- ✅ **Multi-tenancy enforced:** All queries scoped to `family=request.auth.family`

## Next Steps (Optional)
1. Deploy to staging and verify with real ETL scenarios
2. Monitor for edge cases (e.g., runs with no insights)
3. Consider UI enhancement: expose run_id selector in frontend
4. Add monitoring alert if no completed runs exist for a family

