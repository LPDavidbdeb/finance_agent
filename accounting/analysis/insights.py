from dataclasses import dataclass, field
from typing import List, Optional
from .classification import ProcessType
from .trend import TrendResult
from .volatility import VolatilityResult
from .causal import CausalAnalysisResult


@dataclass
class CategoryProfile:
    """
    Complete profile of a spending category for insight ranking.

    Attributes:
        category_name: str - Name of the category (e.g., "Groceries", "Transportation")
        materiality_pct: float - Percentage of total household spend (0-100)
        process_type: ProcessType - DETERMINISTIC, STOCHASTIC, or EPISODIC
        trend_result: TrendResult - From TrendAnalyzer (EPIC 2.1)
        volatility_result: VolatilityResult - From VolatilityAnalyzer (EPIC 2.2)
        causal_result: Optional[CausalAnalysisResult] - From CausalAnalyzer (EPIC 3)
        projected_value: Optional[float] - 12-month projection (from ProjectionEngine)
        projected_upper: Optional[float] - Upper confidence bound
        projected_lower: Optional[float] - Lower confidence bound
        insight_score: float - Calculated ranking score (materiality × severity)
    """
    category_name: str
    materiality_pct: float
    process_type: ProcessType
    trend_result: TrendResult
    volatility_result: VolatilityResult
    causal_result: Optional[CausalAnalysisResult] = None
    projected_value: Optional[float] = None
    projected_upper: Optional[float] = None
    projected_lower: Optional[float] = None
    insight_score: float = field(default=0.0, init=False)

    def __post_init__(self):
        """Validate inputs after initialization."""
        if not (0 <= self.materiality_pct <= 100):
            raise ValueError(f"materiality_pct must be between 0 and 100, got {self.materiality_pct}")
        if self.materiality_pct < 0 or self.materiality_pct > 100:
            raise ValueError(f"materiality_pct out of range: {self.materiality_pct}")


class InsightEngine:
    """
    EPIC 4.2: Materiality-Weighted Insights for the Financial Inference Engine.

    Ranks spending categories by combining:
    - Mathematical Severity (structural breaks, nonlinearity, steep trends, mix shifts)
    - Financial Materiality (% of total household spend)

    Generates expert-grade summaries explaining why a category matters to the user.
    """

    def __init__(
        self,
        steep_slope_threshold: float = 0.05,
        structural_break_weight: int = 50,
        nonlinear_weight: int = 30,
        steep_slope_weight: int = 20,
        mix_shift_weight: int = 20
    ):
        """
        Args:
            steep_slope_threshold: Absolute slope value to trigger steep slope bonus (default 0.05)
            structural_break_weight: Points for structural break (default 50)
            nonlinear_weight: Points for nonlinear trend (default 30)
            steep_slope_weight: Points for steep significant trend (default 20)
            mix_shift_weight: Points for merchant mix shift (default 20)
        """
        self.steep_slope_threshold = steep_slope_threshold
        self.structural_break_weight = structural_break_weight
        self.nonlinear_weight = nonlinear_weight
        self.steep_slope_weight = steep_slope_weight
        self.mix_shift_weight = mix_shift_weight

    def rank(self, profiles: List[CategoryProfile]) -> List[CategoryProfile]:
        """
        Rank categories by insight_score (calculated as base_severity × materiality_multiplier).

        Args:
            profiles: List of CategoryProfile objects

        Returns:
            List of CategoryProfile objects sorted by insight_score (descending)
        """
        if not profiles:
            return []

        # Calculate insight scores for each category
        for profile in profiles:
            profile.insight_score = self._calculate_insight_score(profile)

        # Sort by insight_score descending
        return sorted(profiles, key=lambda p: p.insight_score, reverse=True)

    def _calculate_insight_score(self, profile: CategoryProfile) -> float:
        """
        Calculate insight_score = base_severity × (materiality_pct × 100).

        Formula:
        - Base Severity: Sum of conditional points
        - Materiality Multiplier: (materiality_pct × 100)
        - Final Score: Base × Materiality Multiplier

        Args:
            profile: CategoryProfile to score

        Returns:
            float - The insight_score
        """
        # Calculate base severity points
        base_severity = self._calculate_base_severity(profile)

        # Calculate materiality multiplier (materiality_pct in percentage form)
        materiality_multiplier = profile.materiality_pct * 100.0

        # Final score
        insight_score = base_severity * materiality_multiplier
        return float(insight_score)

    def _calculate_base_severity(self, profile: CategoryProfile) -> float:
        """
        Calculate base severity points from trend, volatility, and causal factors.

        Points awarded:
        - Structural break: +50
        - Nonlinear trend: +30
        - Significant steep slope (|slope| > threshold): +20
        - Mix shift detected: +20

        Args:
            profile: CategoryProfile to evaluate

        Returns:
            float - Sum of severity points
        """
        base_points = 0.0

        # Structural break: +50 points
        if profile.volatility_result.has_structural_break:
            base_points += self.structural_break_weight

        # Nonlinear trend: +30 points
        if profile.trend_result.is_nonlinear:
            base_points += self.nonlinear_weight

        # Significant steep slope: +20 points
        if (profile.trend_result.is_significant and
                abs(profile.trend_result.slope) > self.steep_slope_threshold):
            base_points += self.steep_slope_weight

        # Mix shift detected: +20 points (if causal result provided)
        if profile.causal_result is not None and profile.causal_result.mix_shift_detected:
            base_points += self.mix_shift_weight

        return base_points

    def generate_expert_summary(self, profile: CategoryProfile) -> str:
        """
        Generate an expert-grade natural language summary of the category insight.

        Format: "Category '{name}' is a {ProcessType} process. {Findings}. {Projection}."

        Args:
            profile: CategoryProfile to summarize

        Returns:
            str - Multi-sentence expert summary
        """
        parts = []

        # Part 1: Category name and process type
        parts.append(
            f"Category '{profile.category_name}' is a {profile.process_type.value} process."
        )

        # Part 2: Findings (severity factors)
        findings = []

        if profile.volatility_result.has_structural_break:
            findings.append("Structural break detected")

        if profile.trend_result.is_nonlinear:
            findings.append("Nonlinear trajectory observed")

        if profile.trend_result.is_significant:
            if profile.trend_result.slope > 0:
                trend_direction = "upward"
            else:
                trend_direction = "downward"

            if abs(profile.trend_result.slope) > self.steep_slope_threshold:
                findings.append(f"Steep {trend_direction} trend (slope: {profile.trend_result.slope:.3f})")
            else:
                findings.append(f"Moderate {trend_direction} trend")

        if profile.causal_result is not None:
            if profile.causal_result.mix_shift_detected:
                findings.append("Merchant loyalty shift detected")
            if profile.causal_result.volume_effect_pct != 0:
                vol_sign = "+" if profile.causal_result.volume_effect_pct > 0 else ""
                findings.append(
                    f"Volume effect: {vol_sign}{profile.causal_result.volume_effect_pct:.1f}%"
                )
            if profile.causal_result.price_effect_pct != 0:
                price_sign = "+" if profile.causal_result.price_effect_pct > 0 else ""
                findings.append(
                    f"Price effect: {price_sign}{profile.causal_result.price_effect_pct:.1f}%"
                )

        if findings:
            parts.append(" ".join(findings) + ".")
        else:
            parts.append("Stable pattern observed.")

        # Part 3: Projection
        if profile.projected_value is not None:
            projection_str = f"2026 Projection: ${profile.projected_value:,.0f}"

            # Add confidence interval if available
            if profile.projected_upper is not None and profile.projected_lower is not None:
                # Calculate margin of error as a percentage
                if profile.projected_value != 0:
                    margin_pct = ((profile.projected_upper - profile.projected_lower) / (2 * profile.projected_value)) * 100
                    projection_str += f" ± {margin_pct:.0f}%"

            parts.append(projection_str + ".")

        return " ".join(parts)

    def get_top_insights(self, profiles: List[CategoryProfile], top_n: int = 5) -> List[dict]:
        """
        Get the top N insights with summaries and scores.

        Args:
            profiles: List of CategoryProfile objects
            top_n: Number of top insights to return (default 5)

        Returns:
            List of dicts with keys: category_name, insight_score, severity_rank, summary
        """
        ranked = self.rank(profiles)

        insights = []
        for i, profile in enumerate(ranked[:top_n], 1):
            summary = self.generate_expert_summary(profile)
            insights.append({
                'rank': i,
                'category_name': profile.category_name,
                'insight_score': profile.insight_score,
                'materiality_pct': profile.materiality_pct,
                'base_severity': self._calculate_base_severity(profile),
                'summary': summary
            })

        return insights

