# EPIC 3.2: Changes Made - Detailed Diff Summary

## File-by-File Changes

### 1. accounting/models.py

**Location:** Lines 210-232

**Before:**
```python
    # Natural Language Summary
    expert_summary = models.TextField(
        help_text="Expert-grade natural language summary of the insight (EPIC 4.2)"
    )

    class Meta:
```

**After:**
```python
    # Natural Language Summary
    expert_summary = models.TextField(
        help_text="Expert-grade natural language summary of the insight (EPIC 4.2)"
    )

    # External Normalization (EPIC 3.2)
    benchmark_slope = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="The external baseline slope (e.g., CPI) used for comparison"
    )
    benchmark_classification = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('REAL_GROWTH', 'Real Growth'),
            ('INFLATION_TRACKED', 'Inflation Tracked'),
            ('EFFICIENCY_GAIN', 'Efficiency Gain'),
        ],
        help_text="Classification: REAL_GROWTH, INFLATION_TRACKED, or EFFICIENCY_GAIN"
    )

    class Meta:
```

**Summary:** +23 lines (2 new fields to InsightFact model)

---

### 2. accounting/analysis/api.py

#### Change A: Updated InsightResponseSchema

**Location:** Lines 24-67

**Before:**
```python
class InsightResponseSchema(BaseModel):
    """..."""
    id: str = Field(...)
    categoryName: str = Field(...)
    insight_score: float = Field(...)
    materiality_pct: float = Field(...)
    processType: str = Field(...)
    expertSummary: str = Field(...)
    causal_volume_pct: Optional[float] = Field(...)
    causal_price_pct: Optional[float] = Field(...)
    projected_lower_bound: Decimal | None = Field(...)
    projected_upper_bound: Decimal | None = Field(...)

    class Config:
        from_attributes = True
```

**After:**
```python
class InsightResponseSchema(BaseModel):
    """..."""
    id: str = Field(...)
    categoryName: str = Field(...)
    insight_score: float = Field(...)
    materiality_pct: float = Field(...)
    processType: str = Field(...)
    expertSummary: str = Field(...)
    causal_volume_pct: Optional[float] = Field(...)
    causal_price_pct: Optional[float] = Field(...)
    projected_lower_bound: Decimal | None = Field(...)
    projected_upper_bound: Decimal | None = Field(...)
    benchmark_slope: Decimal | None = Field(
        None,
        description="External baseline slope (e.g., CPI) used for normalization comparison (EPIC 3.2)"
    )
    benchmark_classification: Optional[str] = Field(
        None,
        description="Classification against benchmark: REAL_GROWTH, INFLATION_TRACKED, or EFFICIENCY_GAIN"
    )

    class Config:
        from_attributes = True
```

**Summary:** +10 lines (2 new schema fields)

#### Change B: Updated get_top_insights() endpoint

**Location:** Lines 160-175

**Before:**
```python
    return [
        InsightResponseSchema(
            id=str(fact.category_id),
            categoryName=fact.category.name,
            insight_score=fact.insight_score,
            materiality_pct=fact.materiality_pct,
            processType=fact.process_type,
            expertSummary=fact.expert_summary,
            causal_volume_pct=fact.causal_volume_pct,
            causal_price_pct=fact.causal_price_pct,
            projected_lower_bound=fact.projected_lower_bound,
            projected_upper_bound=fact.projected_upper_bound,
        )
        for fact in insights
    ]
```

**After:**
```python
    return [
        InsightResponseSchema(
            id=str(fact.category_id),
            categoryName=fact.category.name,
            insight_score=fact.insight_score,
            materiality_pct=fact.materiality_pct,
            processType=fact.process_type,
            expertSummary=fact.expert_summary,
            causal_volume_pct=fact.causal_volume_pct,
            causal_price_pct=fact.causal_price_pct,
            projected_lower_bound=fact.projected_lower_bound,
            projected_upper_bound=fact.projected_upper_bound,
            benchmark_slope=fact.benchmark_slope,
            benchmark_classification=fact.benchmark_classification,
        )
        for fact in insights
    ]
```

**Summary:** +2 lines (serialize benchmark fields)

#### Change C: Updated get_latest_insights_snapshot() endpoint

**Location:** Lines 222-237

**Before:**
```python
    insights = [
        InsightResponseSchema(
            id=str(fact.category_id),
            categoryName=fact.category.name,
            insight_score=fact.insight_score,
            materiality_pct=fact.materiality_pct,
            processType=fact.process_type,
            expertSummary=fact.expert_summary,
            causal_volume_pct=fact.causal_volume_pct,
            causal_price_pct=fact.causal_price_pct,
            projected_lower_bound=fact.projected_lower_bound,
            projected_upper_bound=fact.projected_upper_bound,
        )
        for fact in facts
    ]
```

**After:**
```python
    insights = [
        InsightResponseSchema(
            id=str(fact.category_id),
            categoryName=fact.category.name,
            insight_score=fact.insight_score,
            materiality_pct=fact.materiality_pct,
            processType=fact.process_type,
            expertSummary=fact.expert_summary,
            causal_volume_pct=fact.causal_volume_pct,
            causal_price_pct=fact.causal_price_pct,
            projected_lower_bound=fact.projected_lower_bound,
            projected_upper_bound=fact.projected_upper_bound,
            benchmark_slope=fact.benchmark_slope,
            benchmark_classification=fact.benchmark_classification,
        )
        for fact in facts
    ]
```

**Summary:** +2 lines (serialize benchmark fields)

**Total api.py Changes:** +14 lines

---

### 3. accounting/analysis/insights.py

**Location:** Lines 263-291

**Before:**
```python
    @staticmethod
    def build_persistence_kwargs(profile: CategoryProfile, projection_result: Optional[dict] = None) -> dict:
        """Build InsightFact-compatible kwargs with confidence corridor mapping."""
        projection_result = projection_result or {}
        return {
            'projected_value': profile.projected_value,
            'projected_lower_bound': projection_result.get('lower_bound'),
            'projected_upper_bound': projection_result.get('upper_bound'),
        }
```

**After:**
```python
    @staticmethod
    def build_persistence_kwargs(profile: CategoryProfile, projection_result: Optional[dict] = None, normalization_result: Optional[dict] = None) -> dict:
        """
        Build InsightFact-compatible kwargs with confidence corridor mapping.
        
        Args:
            profile: CategoryProfile object with metrics
            projection_result: Dict with 'lower_bound' and 'upper_bound' for confidence corridor
            normalization_result: Dict with 'benchmark_slope' and 'benchmark_classification' from External Normalization Engine
        
        Returns:
            dict: Kwargs ready to pass to InsightFact.objects.create()
        """
        projection_result = projection_result or {}
        normalization_result = normalization_result or {}
        
        persistence_kwargs = {
            'projected_value': profile.projected_value,
            'projected_lower_bound': projection_result.get('lower_bound'),
            'projected_upper_bound': projection_result.get('upper_bound'),
        }
        
        # Add external normalization fields if provided (EPIC 3.2)
        if 'benchmark_slope' in normalization_result:
            persistence_kwargs['benchmark_slope'] = normalization_result.get('benchmark_slope')
        
        if 'benchmark_classification' in normalization_result:
            persistence_kwargs['benchmark_classification'] = normalization_result.get('benchmark_classification')
        
        return persistence_kwargs
```

**Summary:** +28 lines (enhanced function signature and implementation)

---

### 4. accounting/analysis/normalization.py (NEW FILE)

**250+ lines of code:**

**Key Functions:**
1. `classify_growth()` - Core classification algorithm
2. `classify_growth_with_confidence()` - Confidence-aware variant
3. `benchmark_slope_to_decimal()` - Type conversion
4. `get_benchmark_slope()` - Preset retrieval
5. `BENCHMARK_PRESETS` - Dict of common baselines

**Examples Included:**
- Self-test scenarios
- Real-world use cases
- Docstring examples

**Summary:** New module with complete normalization engine

---

### 5. accounting/migrations/0008_add_external_normalization_to_insightfact.py (NEW FILE)

**40 lines:**

```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0007_add_projection_intervals_to_insightfact'),
    ]

    operations = [
        migrations.AddField(
            model_name='insightfact',
            name='benchmark_slope',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='The external baseline slope (e.g., CPI) used for comparison',
                max_digits=7,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='insightfact',
            name='benchmark_classification',
            field=models.CharField(
                blank=True,
                choices=[
                    ('REAL_GROWTH', 'Real Growth'),
                    ('INFLATION_TRACKED', 'Inflation Tracked'),
                    ('EFFICIENCY_GAIN', 'Efficiency Gain'),
                ],
                help_text='Classification: REAL_GROWTH, INFLATION_TRACKED, or EFFICIENCY_GAIN',
                max_length=50,
                null=True,
            ),
        ),
    ]
```

**Summary:** New migration with 2 AddField operations

---

### 6. accounting/analysis/test_normalization.py (NEW FILE)

**350+ lines of comprehensive tests:**

**Test Classes:**
- NormalizationClassificationTestCase (13 tests)
- NormalizationConfidenceTestCase (4 tests)
- BenchmarkSlopeConversionTestCase (3 tests)
- BenchmarkPresetsTestCase (6 tests)
- NormalizationIntegrationTestCase (4 tests)

**Summary:** New test module with 30+ comprehensive test cases

---

## Summary of Changes

| File | Type | Lines | Description |
|------|------|-------|-------------|
| accounting/models.py | Modified | +23 | 2 new fields to InsightFact |
| accounting/analysis/api.py | Modified | +14 | Schema + 2 endpoints updated |
| accounting/analysis/insights.py | Modified | +28 | Enhanced persistence function |
| accounting/analysis/normalization.py | New | 250+ | Core normalization engine |
| accounting/migrations/0008_* | New | 40 | Database migration |
| accounting/analysis/test_normalization.py | New | 350+ | Comprehensive tests |

**Total: 6 files changed (3 modified, 3 new), ~700 lines of code/tests/docs**

---

## How to Apply Changes

### 1. Copy Files
- Replace accounting/models.py
- Replace accounting/analysis/api.py
- Replace accounting/analysis/insights.py
- Add accounting/analysis/normalization.py
- Add accounting/migrations/0008_add_external_normalization_to_insightfact.py
- Add accounting/analysis/test_normalization.py

### 2. Run Migrations
```bash
python manage.py makemigrations accounting
python manage.py migrate
```

### 3. Run Tests
```bash
python manage.py test accounting.analysis.test_normalization -v 2
```

### 4. Verify API
```bash
# GET /api/analysis/insights/top/ now returns:
{
  "benchmark_slope": 0.0250,
  "benchmark_classification": "INFLATION_TRACKED"
}
```

---

## Backward Compatibility

✅ All new database fields are nullable
✅ API returns null values gracefully  
✅ No breaking changes to existing functionality
✅ New parameter in build_persistence_kwargs() is optional
✅ Existing InsightFact rows unaffected

---

## Next Steps

1. Apply all file changes
2. Run migrations
3. Run test suite
4. Verify API responses include new fields
5. When benchmark data available, implement pipeline injection
6. Update frontend to consume and visualize classifications

