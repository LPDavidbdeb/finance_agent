from ninja import Router, errors
from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal
from ninja_jwt.authentication import JWTAuth
from datetime import datetime
from django.core.cache import cache

from accounting.models import AnalysisRun, InsightFact
from accounting.tasks import rebuild_financial_insights, INSIGHTS_SYNC_CACHE_KEY

from accounting.analysis.insights import InsightEngine, CategoryProfile
from accounting.analysis.trend import TrendResult
from accounting.analysis.volatility import VolatilityResult
from accounting.analysis.causal import CausalAnalysisResult
from accounting.analysis.classification import ProcessType


# =========================================================================
# Pydantic Schemas for Serialization
# =========================================================================

class InsightResponseSchema(BaseModel):
    """
    Pydantic schema for frontend consumption matching TypeScript interface.

    Fields:
        id: Unique identifier for the insight (category_name)
        categoryName: Display name of the spending category
        insight_score: Ranking score (base_severity × materiality multiplier)
        materiality_pct: Percentage of total household spend
        processType: DETERMINISTIC, STOCHASTIC, or EPISODIC
        expertSummary: Multi-sentence expert explanation
        causal_volume_pct: Volume effect % change (if available)
        causal_price_pct: Price effect % change (if available)
        benchmark_slope: External baseline slope for normalization comparison
        benchmark_classification: Classification vs benchmark (REAL_GROWTH, INFLATION_TRACKED, EFFICIENCY_GAIN)
    """
    id: str = Field(..., description="Unique identifier (category name)")
    categoryName: str = Field(..., description="Display name of category")
    insight_score: float = Field(..., description="Materiality-weighted ranking score")
    materiality_pct: float = Field(..., description="% of total household spend (0-100)")
    processType: str = Field(..., description="DETERMINISTIC, STOCHASTIC, or EPISODIC")
    expertSummary: str = Field(..., description="Expert-grade summary of insights")
    causal_volume_pct: Optional[float] = Field(None, description="Volume effect % (if available)")
    causal_price_pct: Optional[float] = Field(None, description="Price effect % (if available)")
    projected_lower_bound: Decimal | None = Field(
        None,
        description="Lower bound of the 95% prediction interval (Confidence Corridor)",
    )
    projected_upper_bound: Decimal | None = Field(
        None,
        description="Upper bound of the 95% prediction interval (Confidence Corridor)",
    )
    benchmark_slope: Decimal | None = Field(
        None,
        description="External baseline slope (e.g., CPI) used for normalization comparison (EPIC 3.2)"
    )
    benchmark_classification: Optional[str] = Field(
        None,
        description="Classification against benchmark: REAL_GROWTH, INFLATION_TRACKED, or EFFICIENCY_GAIN"
    )

    class Config:
        """Pydantic configuration."""
        from_attributes = True


class EngineStatusSchema(BaseModel):
    """Status payload returned by the ETL orchestration API."""

    status: str = Field(..., description="syncing or idle")
    last_computed_at: Optional[datetime] = Field(None, description="Most recent InsightFact timestamp")
    total_facts: int = Field(..., description="Total number of InsightFact rows")


class LatestInsightsSnapshotSchema(BaseModel):
    """Latest coherent insight snapshot for a family."""

    run_id: Optional[int] = Field(None, description="Latest successful AnalysisRun id")
    started_at: Optional[datetime] = Field(None, description="Run start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Run completion timestamp")
    total_insights: int = Field(..., description="Number of insight rows in this snapshot")
    insights: List[InsightResponseSchema] = Field(default_factory=list)


# =========================================================================
# Router and Endpoints
# =========================================================================

router = Router(auth=JWTAuth())


@router.get("/insights/top/", response=List[InsightResponseSchema])
def get_top_insights(request, top_n: int = 5, run_id: Optional[int] = None):
    """
    Get top materiality-weighted insights for the logged-in user's family.

    Returns a ranked list of insights sorted by insight_score (descending).
    Results are snapshot-consistent based on a specific AnalysisRun.

    Query Parameters:
        top_n: Number of top insights to return (default 5, max 20)
        run_id: Optional AnalysisRun ID to filter insights. If not provided, uses the most recent completed run.

    Returns:
        List[InsightResponseSchema]: Ranked insights with summaries and causal effects

    Example Response:
        [
            {
                "id": "Groceries",
                "categoryName": "Groceries",
                "insight_score": 75000.0,
                "materiality_pct": 15.0,
                "processType": "STOCHASTIC",
                "expertSummary": "Category 'Groceries' is a STOCHASTIC process...",
                "causal_volume_pct": 5.5,
                "causal_price_pct": 2.1
            },
            ...
        ]
    """
    # Enforce maximum limit
    top_n = min(int(top_n), 20)
    top_n = max(top_n, 1)

    user = request.auth
    family = getattr(user, "family", None)
    if family is None:
        return []

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


@router.post("/engine/trigger/")
def trigger_engine_sync(request):
    """Trigger asynchronous ETL rebuild for financial insights."""
    user = request.auth
    family = getattr(user, "family", None)
    if family is None:
        raise errors.HttpError(400, "User is not associated with a family.")

    try:
        rebuild_financial_insights.delay(family_id=family.id)
        return {"message": "Sync started"}
    except Exception:
        # If the broker is unavailable, still run the pipeline synchronously so the
        # UI remains functional in local/dev environments.
        rebuild_financial_insights.apply(kwargs={"family_id": family.id})
        return {"message": "Sync started locally"}


@router.get("/insights/latest/", response=LatestInsightsSnapshotSchema)
def get_latest_insights_snapshot(request):
    """Return latest successful coherent run snapshot for the logged-in user's family."""
    user = request.auth
    family = getattr(user, "family", None)
    if family is None:
        return LatestInsightsSnapshotSchema(run_id=None, started_at=None, completed_at=None, total_insights=0, insights=[])

    run = (
        AnalysisRun.objects
        .filter(family=family, status=AnalysisRun.Status.SUCCEEDED)
        .order_by("-completed_at", "-id")
        .first()
    )

    if run is None:
        return LatestInsightsSnapshotSchema(run_id=None, started_at=None, completed_at=None, total_insights=0, insights=[])

    facts = (
        InsightFact.objects
        .filter(analysis_run=run)
        .select_related("category")
        .order_by("-insight_score", "category__name")
    )

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

    return LatestInsightsSnapshotSchema(
        run_id=run.id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_insights=len(insights),
        insights=insights,
    )


@router.get("/engine/status/", response=EngineStatusSchema)
def get_engine_status(request):
    """Return ETL sync state and InsightFact warehouse metadata."""
    is_syncing = bool(cache.get(INSIGHTS_SYNC_CACHE_KEY, False))
    user = request.auth
    family = getattr(user, "family", None)
    if family is None:
        return EngineStatusSchema(status="syncing" if is_syncing else "idle", last_computed_at=None, total_facts=0)

    scoped_facts = InsightFact.objects.filter(category__family=family)
    latest_fact = scoped_facts.order_by("-computed_at", "-id").first()

    return EngineStatusSchema(
        status="syncing" if is_syncing else "idle",
        last_computed_at=latest_fact.computed_at if latest_fact else None,
        total_facts=scoped_facts.count(),
    )


def _create_mock_profiles() -> List[CategoryProfile]:
    """
    Create realistic mock CategoryProfile objects for demonstration.

    In production, this would load actual data from the database for the user's family.
    """
    profiles = []

    # Profile 1: Groceries - Stochastic with structural break
    profiles.append(
        CategoryProfile(
            category_name="Groceries",
            materiality_pct=15.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(
                slope=0.045,
                p_value=0.02,
                is_significant=True,
                is_nonlinear=False
            ),
            volatility_result=VolatilityResult(
                ser=12.5,
                has_structural_break=True,
                z_scores={'6m': 2.1, '12m': 1.8, '18m': 1.5}
            ),
            causal_result=CausalAnalysisResult(
                volume_effect_pct=5.5,
                price_effect_pct=2.1,
                mix_shift_detected=False,
                l12m_transaction_count=156,
                p12m_transaction_count=148,
                l12m_avg_ticket=45.2,
                p12m_avg_ticket=44.3,
                l12m_top_merchant_share=28.0,
                p12m_top_merchant_share=26.0
            ),
            projected_value=5420.0,
            projected_upper=5650.0,
            projected_lower=5190.0
        )
    )

    # Profile 2: Utilities - Deterministic, stable
    profiles.append(
        CategoryProfile(
            category_name="Utilities",
            materiality_pct=8.5,
            process_type=ProcessType.DETERMINISTIC,
            trend_result=TrendResult(
                slope=0.005,
                p_value=0.78,
                is_significant=False,
                is_nonlinear=False
            ),
            volatility_result=VolatilityResult(
                ser=2.3,
                has_structural_break=False,
                z_scores={'6m': 0.3, '12m': 0.2, '18m': 0.1}
            ),
            causal_result=None,
            projected_value=1020.0,
            projected_upper=1050.0,
            projected_lower=990.0
        )
    )

    # Profile 3: Transportation - Episodic
    profiles.append(
        CategoryProfile(
            category_name="Transportation",
            materiality_pct=12.0,
            process_type=ProcessType.EPISODIC,
            trend_result=TrendResult(
                slope=-0.02,
                p_value=0.42,
                is_significant=False,
                is_nonlinear=False
            ),
            volatility_result=VolatilityResult(
                ser=85.0,
                has_structural_break=False,
                z_scores={'6m': 0.9, '12m': 0.7, '18m': 0.5}
            ),
            causal_result=None,
            projected_value=1440.0,
            projected_upper=1680.0,
            projected_lower=1200.0
        )
    )

    # Profile 4: Entertainment - Stochastic with steep downward trend
    profiles.append(
        CategoryProfile(
            category_name="Entertainment",
            materiality_pct=6.5,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(
                slope=-0.062,
                p_value=0.01,
                is_significant=True,
                is_nonlinear=False
            ),
            volatility_result=VolatilityResult(
                ser=8.2,
                has_structural_break=True,
                z_scores={'6m': 2.4, '12m': 2.1, '18m': 1.9}
            ),
            causal_result=CausalAnalysisResult(
                volume_effect_pct=-18.0,
                price_effect_pct=1.2,
                mix_shift_detected=True,
                l12m_transaction_count=52,
                p12m_transaction_count=63,
                l12m_avg_ticket=62.0,
                p12m_avg_ticket=61.2,
                l12m_top_merchant_share=55.0,
                p12m_top_merchant_share=38.0
            ),
            projected_value=780.0,
            projected_upper=850.0,
            projected_lower=710.0
        )
    )

    # Profile 5: Dining Out - Stochastic, stable
    profiles.append(
        CategoryProfile(
            category_name="Dining Out",
            materiality_pct=9.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(
                slope=0.015,
                p_value=0.35,
                is_significant=False,
                is_nonlinear=False
            ),
            volatility_result=VolatilityResult(
                ser=15.0,
                has_structural_break=False,
                z_scores={'6m': 0.6, '12m': 0.4, '18m': 0.3}
            ),
            causal_result=CausalAnalysisResult(
                volume_effect_pct=3.0,
                price_effect_pct=4.5,
                mix_shift_detected=False,
                l12m_transaction_count=72,
                p12m_transaction_count=70,
                l12m_avg_ticket=58.5,
                p12m_avg_ticket=56.0,
                l12m_top_merchant_share=22.0,
                p12m_top_merchant_share=20.0
            ),
            projected_value=1350.0,
            projected_upper=1450.0,
            projected_lower=1250.0
        )
    )

    # Profile 6: Subscriptions - Small, low materiality (tests zero score scenario)
    profiles.append(
        CategoryProfile(
            category_name="Subscriptions",
            materiality_pct=3.0,
            process_type=ProcessType.DETERMINISTIC,
            trend_result=TrendResult(
                slope=0.0,
                p_value=1.0,
                is_significant=False,
                is_nonlinear=False
            ),
            volatility_result=VolatilityResult(
                ser=0.5,
                has_structural_break=False,
                z_scores={}
            ),
            causal_result=None,
            projected_value=360.0,
            projected_upper=380.0,
            projected_lower=340.0
        )
    )

    return profiles


def _get_process_type_string(insight: dict) -> str:
    """Extract process type string from insight dict (from rank output)."""
    # The rank output doesn't directly include process_type in the dict,
    # so we need to infer from the profile or return the process_type
    # For now, we'll get it from the category profile lookup
    # This is a workaround; in production, would be included in the insight dict
    try:
        # Map category to process type from mock data
        process_map = {
            "Groceries": "STOCHASTIC",
            "Utilities": "DETERMINISTIC",
            "Transportation": "EPISODIC",
            "Entertainment": "STOCHASTIC",
            "Dining Out": "STOCHASTIC",
            "Subscriptions": "DETERMINISTIC"
        }
        return process_map.get(insight['category_name'], "STOCHASTIC")
    except Exception:
        return "STOCHASTIC"


def _extract_causal_volume(insight: dict) -> Optional[float]:
    """Extract causal volume effect from insight summary if available."""
    # Parse from summary string (e.g., "Volume effect: +15.0%")
    summary = insight['summary']
    if "Volume effect:" in summary:
        try:
            # Extract the percentage value
            parts = summary.split("Volume effect:")
            if len(parts) > 1:
                volume_str = parts[1].split("%")[0].strip()
                return float(volume_str)
        except (ValueError, IndexError):
            pass
    return None


def _extract_causal_price(insight: dict) -> Optional[float]:
    """Extract causal price effect from insight summary if available."""
    # Parse from summary string (e.g., "Price effect: -5.0%")
    summary = insight['summary']
    if "Price effect:" in summary:
        try:
            # Extract the percentage value
            parts = summary.split("Price effect:")
            if len(parts) > 1:
                price_str = parts[1].split("%")[0].strip()
                return float(price_str)
        except (ValueError, IndexError):
            pass
    return None

