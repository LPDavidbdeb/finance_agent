from django.test import TestCase

from accounting.analysis.classification import ProcessType
from accounting.analysis.insights import CategoryProfile
from accounting.analysis.trend import TrendResult
from accounting.analysis.volatility import VolatilityResult
from accounting.models import Account, AnalysisRun, InsightFact
from accounting.tasks import _load_insights
from users.models import Family


class AnalysisRunLinkageTests(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Run Linkage Family")
        self.category = Account.objects.create(
            name="Groceries",
            account_type=Account.AccountType.EXPENSE,
            family=self.family,
        )
        self.run = AnalysisRun.objects.create(family=self.family)

    def test_load_insights_attaches_analysis_run(self):
        profile = CategoryProfile(
            category_name="Groceries",
            materiality_pct=10.0,
            process_type=ProcessType.STOCHASTIC,
            trend_result=TrendResult(slope=0.03, p_value=0.04, is_significant=True, is_nonlinear=False),
            volatility_result=VolatilityResult(ser=6.2, has_structural_break=False, z_scores={}),
            projected_value=1000.0,
            projected_upper=1100.0,
            projected_lower=900.0,
        )
        profile._account_id = self.category.id
        profile._expert_summary = "Groceries summary"

        created = _load_insights([profile], analysis_run=self.run)

        self.assertEqual(created, 1)
        fact = InsightFact.objects.get(category=self.category)
        self.assertEqual(fact.analysis_run_id, self.run.id)

