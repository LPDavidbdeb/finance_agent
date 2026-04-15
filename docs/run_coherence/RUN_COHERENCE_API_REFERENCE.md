# Run Coherence API Quick Reference

## Endpoint Changes Summary

### GET /api/analysis/insights/top/

**New Signature:**
```python
def get_top_insights(request, top_n: int = 5, run_id: Optional[int] = None):
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `top_n` | int | 5 | Number of top insights to return (max 20) |
| `run_id` | int \| None | None | Optional AnalysisRun ID for snapshot-consistent reads |

**Behavior:**
- **If `run_id` provided:** Returns insights only from that specific run
- **If `run_id=None`:** Auto-selects most recent `AnalysisRun` with `status='SUCCEEDED'`
- **If no completed run exists:** Returns empty list `[]`

**Example Requests:**
```bash
# Use latest completed run (default)
curl "http://localhost:8000/api/analysis/insights/top/?top_n=5"

# Use specific run (ID 42)
curl "http://localhost:8000/api/analysis/insights/top/?top_n=5&run_id=42"

# Get top 10 from latest run
curl "http://localhost:8000/api/analysis/insights/top/?top_n=10"
```

**Response Schema (unchanged):**
```json
[
  {
    "id": "Groceries",
    "categoryName": "Groceries",
    "insight_score": 75000.0,
    "materiality_pct": 15.0,
    "processType": "STOCHASTIC",
    "expertSummary": "Category 'Groceries' is a STOCHASTIC process...",
    "causal_volume_pct": 5.5,
    "causal_price_pct": 2.1,
    "projected_lower_bound": 71000.25,
    "projected_upper_bound": 79000.75
  }
]
```

---

### GET /api/analysis/insights/latest/

**Signature (unchanged):**
```python
def get_latest_insights_snapshot(request):
```

**Changes:**
- Ordering changed from `-started_at` to `-completed_at` for consistency

**Response Schema (unchanged):**
```json
{
  "run_id": 42,
  "started_at": "2026-04-15T09:00:00Z",
  "completed_at": "2026-04-15T10:00:00Z",
  "total_insights": 5,
  "insights": [
    { ...InsightResponseSchema... }
  ]
}
```

---

## Implementation Details

### Run Selection Logic

**Default Flow (run_id=None):**
1. Query: `AnalysisRun.objects.filter(family=family, status='SUCCEEDED')`
2. Order: `-completed_at, -id`
3. Select: First result (most recent)
4. If None: Return empty list

**Explicit Flow (run_id provided):**
1. Use provided run_id directly
2. Query InsightFact for that run_id
3. Return results ordered by insight_score

**Pseudo-code:**
```python
if run_id is None:
    latest_run = AnalysisRun.objects \
        .filter(family=family, status='SUCCEEDED') \
        .order_by('-completed_at', '-id') \
        .first()
    
    if latest_run is None:
        return []
    
    target_run_id = latest_run.id
else:
    target_run_id = run_id

# Query facts for the determined run
facts = InsightFact.objects \
    .filter(category__family=family, analysis_run_id=target_run_id) \
    .select_related('category') \
    .order_by('-insight_score', 'category__name')[:top_n]
```

### Security Guarantees

✅ **Multi-tenancy:** All queries filter by `category__family=family`
✅ **Snapshot Consistency:** All facts from single `analysis_run_id`
✅ **No Data Leaks:** Cross-tenant boundaries enforced at query level
✅ **Audit Trail:** AnalysisRun tracks which facts were computed together

---

## Integration Checklist

- [ ] Code deployed to target environment
- [ ] Database migrations applied (none required)
- [ ] Frontend updated to optionally pass `run_id` parameter
- [ ] Monitoring added for "no completed run" scenario
- [ ] Documentation updated in API spec
- [ ] Smoke tests passing in staging
- [ ] Load test confirms no performance regression

---

## Troubleshooting

### Issue: Empty response from `/insights/top/`
**Possible Causes:**
1. No completed AnalysisRun for the family
2. No InsightFact rows in the latest run
3. Invalid JWT token (returns 401)

**Verification:**
```bash
# Check if family has completed runs
GET /api/analysis/engine/status/

# Should return run_id in response if runs exist
GET /api/analysis/insights/latest/
```

### Issue: Run still shows old insights
**Solution:**
Explicitly query with older `run_id` parameter to debug:
```bash
curl "http://localhost:8000/api/analysis/insights/top/?run_id=<old_run_id>&top_n=5"
```

### Issue: Wrong run selected
**Solution:**
Check AnalysisRun `completed_at` timestamps:
```bash
# In Django shell:
from accounting.models import AnalysisRun
AnalysisRun.objects.filter(family_id=<family_id>, status='SUCCEEDED') \
    .order_by('-completed_at').values('id', 'completed_at', 'status')
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-15 | Initial run coherence implementation |
| — | — | Added optional `run_id` query parameter |
| — | — | Fixed `/insights/latest/` ordering to use `completed_at` |


