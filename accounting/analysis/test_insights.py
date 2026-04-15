import unittest
from accounting.analysis.insights import InsightEngine, CategoryProfile
from accounting.analysis.trend import TrendResult
from accounting.analysis.volatility import VolatilityResult
from accounting.analysis.causal import CausalAnalysisResult
from accounting.analysis.classification import ProcessType


class TestInsightEngine(unittest.TestCase):
    def setUp(self):
        self.engine = InsightEngine(
            steep_slope_threshold=0.05,
            structural_break_weight=50,
            nonlinear_weight=30,
            steep_slope_weight=20,
            mix_shift_weight=20
        )

    # =========================================================================
    # SUCCESS CRITERIA 1: Module accepts CategoryProfile list, returns sorted by score
    # =========================================================================
    def test_accepts_category_profile_list_returns_sorted(self):
        """Verify engine accepts list of CategoryProfile objects and returns sorted by insight_score."""
        profiles = [
            CategoryProfile(
                category_name="Groceries",
                materiality_pct=15.0,
                process_type=ProcessType.STOCHASTIC,
                trend_result=TrendResult(slope=0.02, p_value=0.1, is_significant=False, is_nonlinear=False),
                volatility_result=VolatilityResult(ser=10.0, has_structural_break=False, z_scores={}),
            ),
            CategoryProfile(
                category_name="Utilities",
                materiality_pct=8.0,
                process_type=ProcessType.DETERMINISTIC,
                trend_result=TrendResult(slope=0.01, p_value=0.5, is_significant=False, is_nonlinear=False),
                volatility_result=VolatilityResult(ser=2.0, has_structural_break=True, z_scores={}),
            ),
        ]

        ranked = self.engine.rank(profiles)

        # Verify returned as list
        self.assertIsInstance(ranked, list)
        self.assertEqual(len(ranked), 2)

        # Verify sorted by insight_score (utilities should rank higher due to structural break)
        self.assertEqual(ranked[0].category_name, "Utilities")
        self.assertGreater(ranked[0].insight_score, ranked[1].insight_score)

    def test_empty_profile_list_returns_empty(self):
        """Verify engine handles empty profile list."""
        ranked = self.engine.rank([])
        self.assertEqual(ranked, [])

    def test_single_profile_returns_single(self):
        """Verify engine handles single profile."""
        profile = CategoryProfile(
            category_name="Test",
            materiality_pct=10.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=5.0, has_structural_break=False, z_scores={}),
        )

        ranked = self.engine.rank([profile])
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].category_name, "Test")

    def test_invalid_materiality_raises_error(self):
        """Verify error on invalid materiality percentage."""
        with self.assertRaises(ValueError):
            CategoryProfile(
                category_name="Invalid",
                materiality_pct=150.0,  # > 100
                process_type=ProcessType.STOCHASTIC,
                trend_result=TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False),
                volatility_result=VolatilityResult(ser=0.0, has_structural_break=False, z_scores={}),
            )

    # =========================================================================
    # SUCCESS CRITERIA 2: 20% materiality + structural break > 5% materiality + structural break
    # =========================================================================
    def test_higher_materiality_ranks_higher(self):
        """
        Verify category with higher materiality ranks higher.
        Example: Both have structural break (+50), but one is 20% of budget, other is 5%.
        Expected: 50 × (20 × 100) = 100,000 > 50 × (5 × 100) = 25,000
        """
        high_materiality = CategoryProfile(
            category_name="Groceries (20%)",
            materiality_pct=20.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=10.0, has_structural_break=True, z_scores={}),
        )

        low_materiality = CategoryProfile(
            category_name="Subscriptions (5%)",
            materiality_pct=5.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=10.0, has_structural_break=True, z_scores={}),
        )

        ranked = self.engine.rank([low_materiality, high_materiality])

        # High materiality should rank first
        self.assertEqual(ranked[0].category_name, "Groceries (20%)")
        self.assertEqual(ranked[1].category_name, "Subscriptions (5%)")

        # Verify score calculation
        self.assertEqual(ranked[0].insight_score, 50 * (20 * 100))  # 100,000
        self.assertEqual(ranked[1].insight_score, 50 * (5 * 100))   # 25,000
        self.assertGreater(ranked[0].insight_score, ranked[1].insight_score)

    def test_materiality_multiplier_formula(self):
        """Verify materiality multiplier is applied correctly: base_severity × (materiality_pct × 100)."""
        profile = CategoryProfile(
            category_name="Test",
            materiality_pct=15.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=5.0, has_structural_break=True, z_scores={}),  # +50 points
        )

        ranked = self.engine.rank([profile])
        expected_score = 50 * (15 * 100)  # 50 * 1500 = 75,000
        self.assertEqual(ranked[0].insight_score, expected_score)

    # =========================================================================
    # SUCCESS CRITERIA 3: Structural break (50) > steep slope (20) at same materiality
    # =========================================================================
    def test_structural_break_outranks_steep_slope(self):
        """
        Verify category with structural break (+50) ranks higher than steep slope (+20).
        Both at 10% materiality.
        Expected: 50 × 1000 = 50,000 > 20 × 1000 = 20,000
        """
        structural_break = CategoryProfile(
            category_name="With Structural Break",
            materiality_pct=10.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.02, p_value=0.5, is_significant=False, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=10.0, has_structural_break=True, z_scores={}),  # +50
        )

        steep_slope = CategoryProfile(
            category_name="With Steep Slope",
            materiality_pct=10.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.08, p_value=0.01, is_significant=True, is_nonlinear=False),  # +20
            volatility_result=VolatilityResult(ser=5.0, has_structural_break=False, z_scores={}),
        )

        ranked = self.engine.rank([steep_slope, structural_break])

        # Structural break should rank higher
        self.assertEqual(ranked[0].category_name, "With Structural Break")
        self.assertEqual(ranked[1].category_name, "With Steep Slope")
        self.assertGreater(ranked[0].insight_score, ranked[1].insight_score)

        # Verify scores
        self.assertEqual(ranked[0].insight_score, 50 * 1000)  # 50,000
        self.assertEqual(ranked[1].insight_score, 20 * 1000)  # 20,000

    def test_all_severity_factors_combine(self):
        """Verify all severity factors stack: structural break (+50) + nonlinear (+30) + steep slope (+20) + mix shift (+20) = 120."""
        causal = CausalAnalysisResult(
            volume_effect_pct=10.0,
            price_effect_pct=5.0,
            mix_shift_detected=True,
            l12m_transaction_count=100,
            p12m_transaction_count=110,
            l12m_avg_ticket=50.0,
            p12m_avg_ticket=48.0,
            l12m_top_merchant_share=45.0,
            p12m_top_merchant_share=30.0,
        )

        profile = CategoryProfile(
            category_name="Multiple Issues",
            materiality_pct=10.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.08, p_value=0.01, is_significant=True, is_nonlinear=True),  # +30 +20
            volatility_result=VolatilityResult(ser=15.0, has_structural_break=True, z_scores={}),  # +50
            causal_result=causal,  # +20
        )

        ranked = self.engine.rank([profile])
        # Base severity: 50 + 30 + 20 + 20 = 120
        expected_score = 120 * (10 * 100)  # 120 * 1000 = 120,000
        self.assertEqual(ranked[0].insight_score, expected_score)

    # =========================================================================
    # SUCCESS CRITERIA 4: Handles missing CausalResult gracefully
    # =========================================================================
    def test_missing_causal_result_no_crash(self):
        """Verify engine handles missing CausalResult without crashing."""
        profile = CategoryProfile(
            category_name="No Causal Data",
            materiality_pct=12.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.03, p_value=0.05, is_significant=True, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=8.0, has_structural_break=False, z_scores={}),
            causal_result=None,  # Explicitly None
        )

        # Should not raise error
        ranked = self.engine.rank([profile])
        self.assertEqual(len(ranked), 1)
        self.assertGreaterEqual(ranked[0].insight_score, 0)

    def test_mix_shift_not_counted_when_causal_none(self):
        """Verify mix_shift points not added when CausalResult is None."""
        # Without causal result: only nonlinear (+30)
        profile_no_causal = CategoryProfile(
            category_name="No Causal",
            materiality_pct=10.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.02, p_value=0.1, is_significant=False, is_nonlinear=True),
            volatility_result=VolatilityResult(ser=5.0, has_structural_break=False, z_scores={}),
            causal_result=None,
        )

        ranked = self.engine.rank([profile_no_causal])
        expected = 30 * (10 * 100)  # 30,000
        self.assertEqual(ranked[0].insight_score, expected)

        # With causal result but no mix shift: still only nonlinear (+30)
        causal_no_shift = CausalAnalysisResult(
            volume_effect_pct=0.0,
            price_effect_pct=0.0,
            mix_shift_detected=False,
            l12m_transaction_count=100,
            p12m_transaction_count=100,
            l12m_avg_ticket=50.0,
            p12m_avg_ticket=50.0,
            l12m_top_merchant_share=40.0,
            p12m_top_merchant_share=40.0,
        )

        profile_with_causal_no_shift = CategoryProfile(
            category_name="With Causal No Shift",
            materiality_pct=10.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.02, p_value=0.1, is_significant=False, is_nonlinear=True),
            volatility_result=VolatilityResult(ser=5.0, has_structural_break=False, z_scores={}),
            causal_result=causal_no_shift,
        )

        ranked2 = self.engine.rank([profile_with_causal_no_shift])
        self.assertEqual(ranked2[0].insight_score, expected)  # Same score

    # =========================================================================
    # SUCCESS CRITERIA 5: Comprehensive pytest coverage
    # =========================================================================
    def test_expert_summary_basic(self):
        """Verify generate_expert_summary() produces readable output."""
        profile = CategoryProfile(
            category_name="Groceries",
            materiality_pct=15.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.03, p_value=0.05, is_significant=True, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=10.0, has_structural_break=True, z_scores={}),
            projected_value=5000.0,
            projected_upper=5200.0,
            projected_lower=4800.0,
        )

        summary = self.engine.generate_expert_summary(profile)

        # Verify components are present
        self.assertIn("Groceries", summary)
        self.assertIn("STOCHASTIC", summary)
        self.assertIn("Structural break", summary)
        self.assertIn("upward trend", summary)
        self.assertIn("2026 Projection", summary)
        self.assertIn("$5,000", summary)
        self.assertIn("±", summary)

    def test_expert_summary_with_causal_effects(self):
        """Verify expert summary includes causal decomposition."""
        causal = CausalAnalysisResult(
            volume_effect_pct=15.0,
            price_effect_pct=-5.0,
            mix_shift_detected=True,
            l12m_transaction_count=150,
            p12m_transaction_count=130,
            l12m_avg_ticket=48.0,
            p12m_avg_ticket=50.5,
            l12m_top_merchant_share=50.0,
            p12m_top_merchant_share=35.0,
        )

        profile = CategoryProfile(
            category_name="Coffee",
            materiality_pct=5.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.01, p_value=0.5, is_significant=False, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=2.0, has_structural_break=False, z_scores={}),
            causal_result=causal,
        )

        summary = self.engine.generate_expert_summary(profile)

        # Verify causal effects are mentioned
        self.assertIn("Merchant loyalty shift", summary)
        self.assertIn("Volume effect:", summary)
        self.assertIn("+15.0%", summary)
        self.assertIn("Price effect:", summary)
        self.assertIn("-5.0%", summary)

    def test_expert_summary_downward_trend(self):
        """Verify expert summary detects downward trend."""
        profile = CategoryProfile(
            category_name="Entertainment",
            materiality_pct=8.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=-0.06, p_value=0.01, is_significant=True, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=5.0, has_structural_break=False, z_scores={}),
            projected_value=1500.0,
        )

        summary = self.engine.generate_expert_summary(profile)

        # Should mention downward trend and slope
        self.assertIn("downward trend", summary)
        self.assertIn("0.060", summary)  # Slope magnitude

    def test_expert_summary_no_projection(self):
        """Verify expert summary handles missing projection data."""
        profile = CategoryProfile(
            category_name="Miscellaneous",
            materiality_pct=3.0,
            process_type=ProcessType.EPISODIC,
            trend_result=TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=20.0, has_structural_break=False, z_scores={}),
            projected_value=None,  # No projection
        )

        summary = self.engine.generate_expert_summary(profile)

        # Should not crash, should mention process type and have no projection
        self.assertIn("EPISODIC", summary)
        self.assertIn("Stable pattern", summary)
        self.assertNotIn("2026 Projection", summary)

    def test_get_top_insights_returns_sorted_summaries(self):
        """Verify get_top_insights() returns top N with summaries."""
        profiles = [
            CategoryProfile(
                category_name="Cat A",
                materiality_pct=5.0,
                process_type=ProcessType.STOCHASTIC,
                trend_result=TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False),
                volatility_result=VolatilityResult(ser=5.0, has_structural_break=True, z_scores={}),
            ),
            CategoryProfile(
                category_name="Cat B",
                materiality_pct=10.0,
                process_type=ProcessType.STOCHASTIC,
                trend_result=TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=True),
                volatility_result=VolatilityResult(ser=5.0, has_structural_break=False, z_scores={}),
            ),
            CategoryProfile(
                category_name="Cat C",
                materiality_pct=3.0,
                process_type=ProcessType.DETERMINISTIC,
                trend_result=TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False),
                volatility_result=VolatilityResult(ser=2.0, has_structural_break=False, z_scores={}),
            ),
        ]

        top_insights = self.engine.get_top_insights(profiles, top_n=2)

        # Should return 2 insights
        self.assertEqual(len(top_insights), 2)

        # Verify structure
        for insight in top_insights:
            self.assertIn('rank', insight)
            self.assertIn('category_name', insight)
            self.assertIn('insight_score', insight)
            self.assertIn('materiality_pct', insight)
            self.assertIn('base_severity', insight)
            self.assertIn('summary', insight)

        # Cat B (10% materiality + nonlinear +30) should rank first
        # Score: 30 × 1000 = 30,000
        # Cat A (5% materiality + structural break +50) should rank second
        # Score: 50 × 500 = 25,000
        self.assertEqual(top_insights[0]['category_name'], "Cat B")
        self.assertEqual(top_insights[1]['category_name'], "Cat A")

    def test_zero_materiality_zero_score(self):
        """Verify category with 0% materiality has 0 insight score."""
        profile = CategoryProfile(
            category_name="Zero Materiality",
            materiality_pct=0.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.0, p_value=0.01, is_significant=True, is_nonlinear=True),
            volatility_result=VolatilityResult(ser=10.0, has_structural_break=True, z_scores={}),
        )

        ranked = self.engine.rank([profile])
        # Even with multiple severity factors, 0 materiality = 0 score
        self.assertEqual(ranked[0].insight_score, 0.0)

    def test_steep_slope_threshold_enforcement(self):
        """Verify steep_slope_threshold parameter is enforced."""
        engine = InsightEngine(steep_slope_threshold=0.10)

        # Slope of 0.08 < 0.10 threshold: should not trigger steep slope bonus
        profile_below = CategoryProfile(
            category_name="Below Threshold",
            materiality_pct=10.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.08, p_value=0.01, is_significant=True, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=5.0, has_structural_break=False, z_scores={}),
        )

        # Slope of 0.12 > 0.10 threshold: should trigger bonus
        profile_above = CategoryProfile(
            category_name="Above Threshold",
            materiality_pct=10.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.12, p_value=0.01, is_significant=True, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=5.0, has_structural_break=False, z_scores={}),
        )

        ranked_below = engine.rank([profile_below])
        ranked_above = engine.rank([profile_above])

        # Below should have 0 base (significant but not steep enough)
        self.assertEqual(ranked_below[0].insight_score, 0.0)

        # Above should have 20 base (steep slope bonus applies)
        self.assertEqual(ranked_above[0].insight_score, 20 * 1000)

    def test_confidence_interval_percentage_in_summary(self):
        """Verify confidence interval displayed as percentage in summary."""
        profile = CategoryProfile(
            category_name="Test",
            materiality_pct=10.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.0, p_value=1.0, is_significant=False, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=5.0, has_structural_break=False, z_scores={}),
            projected_value=1000.0,
            projected_upper=1100.0,
            projected_lower=900.0,
        )

        summary = self.engine.generate_expert_summary(profile)

        # Margin: (1100 - 900) / (2 * 1000) * 100 = 10%
        self.assertIn("± 10%", summary)


if __name__ == '__main__':
    unittest.main()

