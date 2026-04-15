from types import SimpleNamespace
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.utils import timezone
from django.test import TestCase
from django.contrib.auth import get_user_model

from accounting.analysis.api import trigger_engine_sync, get_engine_status, get_latest_insights_snapshot
from accounting.models import Account, AnalysisRun, InsightFact
from accounting.tasks import INSIGHTS_SYNC_CACHE_KEY
from users.models import Family

User = get_user_model()


class EngineOrchestrationApiTests(TestCase):
    def setUp(self):
        cache.delete(INSIGHTS_SYNC_CACHE_KEY)
        self.family = Family.objects.create(name="Engine API Family")
        self.user = User.objects.create_user(
            email="engine-status@example.com",
            password="secret123",
            family=self.family,
        )
        self.request = SimpleNamespace(auth=self.user)

        self.category = Account.objects.create(
            name="Groceries",
            account_type=Account.AccountType.EXPENSE,
            family=self.family,
        )

    @patch("accounting.analysis.api.rebuild_financial_insights.delay")
    def test_trigger_endpoint_dispatches_task(self, mock_delay):
        response = trigger_engine_sync(self.request)

        mock_delay.assert_called_once_with(family_id=self.family.id)
        self.assertEqual(response, {"message": "Sync started"})

    @patch("accounting.analysis.api.rebuild_financial_insights.apply")
    @patch("accounting.analysis.api.rebuild_financial_insights.delay", side_effect=RuntimeError("broker down"))
    def test_trigger_endpoint_falls_back_to_local_execution(self, mock_delay, mock_apply):
        response = trigger_engine_sync(self.request)

        mock_delay.assert_called_once_with(family_id=self.family.id)
        mock_apply.assert_called_once_with(kwargs={"family_id": self.family.id})
        self.assertEqual(response, {"message": "Sync started locally"})

    def test_status_endpoint_reports_syncing_when_cache_true(self):
        cache.set(INSIGHTS_SYNC_CACHE_KEY, True, timeout=60)

        status = get_engine_status(self.request)

        self.assertEqual(status.status, "syncing")
        self.assertEqual(status.total_facts, 0)
        self.assertIsNone(status.last_computed_at)

    def test_status_endpoint_reports_idle_and_fact_metadata(self):
        cache.set(INSIGHTS_SYNC_CACHE_KEY, False, timeout=60)

        fact = InsightFact.objects.create(
            category=self.category,
            insight_score=75000.0,
            materiality_pct=15.0,
            process_type="STOCHASTIC",
            has_structural_break=True,
            expert_summary="Category 'Groceries' is a STOCHASTIC process.",
        )

        status = get_engine_status(self.request)

        self.assertEqual(status.status, "idle")
        self.assertEqual(status.total_facts, 1)
        self.assertIsNotNone(status.last_computed_at)
        self.assertEqual(status.last_computed_at, fact.computed_at)

    def test_status_endpoint_uses_idle_default_when_cache_missing(self):
        cache.delete(INSIGHTS_SYNC_CACHE_KEY)

        status = get_engine_status(self.request)

        self.assertEqual(status.status, "idle")
        self.assertEqual(status.total_facts, 0)
        self.assertIsNone(status.last_computed_at)

    def test_status_endpoint_is_family_scoped(self):
        other_family = Family.objects.create(name="Other Engine API Family")
        other_category = Account.objects.create(
            name="Travel",
            account_type=Account.AccountType.EXPENSE,
            family=other_family,
        )
        InsightFact.objects.create(
            category=other_category,
            insight_score=99999.0,
            materiality_pct=40.0,
            process_type="EPISODIC",
            expert_summary="Other family fact",
        )

        status = get_engine_status(self.request)

        self.assertEqual(status.total_facts, 0)
        self.assertIsNone(status.last_computed_at)


class TopInsightsApiTests(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Primary Family")
        self.other_family = Family.objects.create(name="Other Family")

        self.user = User.objects.create_user(
            email="analysis@example.com",
            password="secret123",
            family=self.family,
        )
        self.request = SimpleNamespace(auth=self.user)

        self.cat_food = Account.objects.create(
            name="Groceries",
            account_type=Account.AccountType.EXPENSE,
            family=self.family,
        )
        self.cat_rent = Account.objects.create(
            name="Housing",
            account_type=Account.AccountType.EXPENSE,
            family=self.family,
        )
        self.cat_other_family = Account.objects.create(
            name="Travel",
            account_type=Account.AccountType.EXPENSE,
            family=self.other_family,
        )

    def test_get_top_insights_returns_latest_per_category_for_family(self):
        from accounting.analysis.api import get_top_insights

        old = InsightFact.objects.create(
            category=self.cat_food,
            insight_score=100.0,
            materiality_pct=5.0,
            process_type="STOCHASTIC",
            expert_summary="Old groceries summary",
        )
        InsightFact.objects.filter(id=old.id).update(
            computed_at=timezone.now() - timedelta(days=2)
        )

        InsightFact.objects.create(
            category=self.cat_food,
            insight_score=250.0,
            materiality_pct=6.0,
            process_type="STOCHASTIC",
            expert_summary="Latest groceries summary",
            causal_volume_pct=3.2,
            causal_price_pct=1.1,
        )
        InsightFact.objects.create(
            category=self.cat_rent,
            insight_score=150.0,
            materiality_pct=20.0,
            process_type="DETERMINISTIC",
            expert_summary="Housing summary",
        )
        InsightFact.objects.create(
            category=self.cat_other_family,
            insight_score=999.0,
            materiality_pct=40.0,
            process_type="EPISODIC",
            expert_summary="Should never leak",
        )

        response = get_top_insights(self.request, top_n=10)

        self.assertEqual(len(response), 2)
        self.assertEqual(response[0].categoryName, "Groceries")
        self.assertEqual(response[0].insight_score, 250.0)
        self.assertEqual(response[0].causal_volume_pct, 3.2)
        self.assertEqual(response[1].categoryName, "Housing")

    def test_get_top_insights_applies_top_n(self):
        from accounting.analysis.api import get_top_insights

        InsightFact.objects.create(
            category=self.cat_food,
            insight_score=200.0,
            materiality_pct=8.0,
            process_type="STOCHASTIC",
            expert_summary="Groceries",
        )
        InsightFact.objects.create(
            category=self.cat_rent,
            insight_score=120.0,
            materiality_pct=18.0,
            process_type="DETERMINISTIC",
            expert_summary="Housing",
        )

        response = get_top_insights(self.request, top_n=1)

        self.assertEqual(len(response), 1)
        self.assertEqual(response[0].categoryName, "Groceries")


class LatestInsightsSnapshotApiTests(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Snapshot Family")
        self.other_family = Family.objects.create(name="Other Snapshot Family")

        self.user = User.objects.create_user(
            email="snapshot@example.com",
            password="secret123",
            family=self.family,
        )
        self.request = SimpleNamespace(auth=self.user)

        self.food = Account.objects.create(
            name="Groceries",
            account_type=Account.AccountType.EXPENSE,
            family=self.family,
        )
        self.rent = Account.objects.create(
            name="Housing",
            account_type=Account.AccountType.EXPENSE,
            family=self.family,
        )

    def test_latest_snapshot_returns_empty_payload_when_no_successful_run(self):
        response = get_latest_insights_snapshot(self.request)

        self.assertIsNone(response.run_id)
        self.assertEqual(response.total_insights, 0)
        self.assertEqual(response.insights, [])

    def test_latest_snapshot_returns_latest_successful_run_insights_only(self):
        old_run = AnalysisRun.objects.create(
            family=self.family,
            status=AnalysisRun.Status.SUCCEEDED,
            completed_at=timezone.now() - timedelta(hours=3),
        )
        latest_run = AnalysisRun.objects.create(
            family=self.family,
            status=AnalysisRun.Status.SUCCEEDED,
            completed_at=timezone.now(),
        )

        InsightFact.objects.create(
            category=self.food,
            analysis_run=old_run,
            insight_score=999.0,
            materiality_pct=15.0,
            process_type="STOCHASTIC",
            expert_summary="Old run row",
        )
        InsightFact.objects.create(
            category=self.food,
            analysis_run=latest_run,
            insight_score=220.0,
            materiality_pct=14.0,
            process_type="STOCHASTIC",
            expert_summary="Latest food",
        )
        InsightFact.objects.create(
            category=self.rent,
            analysis_run=latest_run,
            insight_score=180.0,
            materiality_pct=30.0,
            process_type="DETERMINISTIC",
            expert_summary="Latest rent",
        )

        other_run = AnalysisRun.objects.create(
            family=self.other_family,
            status=AnalysisRun.Status.SUCCEEDED,
            completed_at=timezone.now(),
        )
        other_cat = Account.objects.create(
            name="Travel",
            account_type=Account.AccountType.EXPENSE,
            family=self.other_family,
        )
        InsightFact.objects.create(
            category=other_cat,
            analysis_run=other_run,
            insight_score=2000.0,
            materiality_pct=50.0,
            process_type="EPISODIC",
            expert_summary="Other family should not leak",
        )

        response = get_latest_insights_snapshot(self.request)

        self.assertEqual(response.run_id, latest_run.id)
        self.assertEqual(response.total_insights, 2)
        self.assertEqual(response.insights[0].categoryName, "Groceries")
        self.assertEqual(response.insights[1].categoryName, "Housing")


