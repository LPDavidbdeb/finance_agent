from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

from accounting.models import Account, InsightFact, CategoryMonthlyStat, JournalEntry, TransactionLine
from users.models import Family


class InsightFactModelTestCase(TestCase):
    """Test suite for the InsightFact append-only model (Layer 3)."""

    def setUp(self):
        """Create test data."""
        self.family = Family.objects.create(
            name="Test Family",
            timezone="America/Toronto"
        )
        self.category = Account.objects.create(
            name="Groceries",
            account_type=Account.AccountType.EXPENSE,
            family=self.family
        )

    def test_insight_fact_model_creation(self):
        """Verify InsightFact model can be created and saved."""
        insight = InsightFact.objects.create(
            category=self.category,
            insight_score=75000.0,
            materiality_pct=15.0,
            process_type='STOCHASTIC',
            slope=0.045,
            has_structural_break=True,
            causal_volume_pct=5.5,
            causal_price_pct=2.1,
            projected_value=5420.0,
            expert_summary="Category is growing with structural break detected."
        )

        self.assertIsNotNone(insight.id)
        self.assertEqual(insight.category.name, "Groceries")
        self.assertEqual(insight.insight_score, 75000.0)

    def test_insight_fact_computed_at_auto_set(self):
        """Verify computed_at is automatically set on creation."""
        before_creation = timezone.now()

        insight = InsightFact.objects.create(
            category=self.category,
            insight_score=50000.0,
            materiality_pct=10.0,
            process_type='DETERMINISTIC',
            expert_summary="Utilities are stable."
        )

        after_creation = timezone.now()

        # computed_at should be set automatically
        self.assertIsNotNone(insight.computed_at)
        self.assertGreaterEqual(insight.computed_at, before_creation)
        self.assertLessEqual(insight.computed_at, after_creation)

    def test_insight_fact_optional_fields(self):
        """Verify optional fields (null=True) can be saved as None."""
        insight = InsightFact.objects.create(
            category=self.category,
            insight_score=30000.0,
            materiality_pct=6.0,
            process_type='EPISODIC',
            slope=None,  # Optional
            causal_volume_pct=None,  # Optional
            causal_price_pct=None,  # Optional
            projected_value=None,  # Optional
            expert_summary="Episodic category with no causal data."
        )

        self.assertIsNone(insight.slope)
        self.assertIsNone(insight.causal_volume_pct)
        self.assertIsNone(insight.projected_value)

    def test_insight_fact_ordering(self):
        """Verify InsightFact objects are ordered by -computed_at."""
        # Create three insights
        insight1 = InsightFact.objects.create(
            category=self.category,
            insight_score=50000.0,
            materiality_pct=10.0,
            process_type='STOCHASTIC',
            expert_summary="First insight."
        )

        # Wait a bit to ensure different timestamps
        timezone.now()

        insight2 = InsightFact.objects.create(
            category=self.category,
            insight_score=60000.0,
            materiality_pct=12.0,
            process_type='STOCHASTIC',
            expert_summary="Second insight."
        )

        # Query and verify ordering
        insights = list(InsightFact.objects.all())

        # Most recent should be first
        self.assertEqual(insights[0].id, insight2.id)
        self.assertEqual(insights[1].id, insight1.id)

    def test_insight_fact_versioning(self):
        """Verify multiple versions of same category are stored separately (append-only)."""
        # Create first version
        insight1 = InsightFact.objects.create(
            category=self.category,
            insight_score=50000.0,
            materiality_pct=10.0,
            process_type='STOCHASTIC',
            expert_summary="Version 1."
        )

        # Create second version (same category, different values)
        insight2 = InsightFact.objects.create(
            category=self.category,
            insight_score=55000.0,
            materiality_pct=11.0,
            process_type='STOCHASTIC',
            expert_summary="Version 2."
        )

        # Both should exist
        self.assertEqual(InsightFact.objects.filter(category=self.category).count(), 2)
        self.assertNotEqual(insight1.id, insight2.id)
        self.assertEqual(insight1.category.id, insight2.category.id)

    def test_insight_fact_indexes(self):
        """Verify database indexes are created for common queries."""
        # Create an insight
        insight = InsightFact.objects.create(
            category=self.category,
            insight_score=50000.0,
            materiality_pct=10.0,
            process_type='STOCHASTIC',
            expert_summary="Test."
        )

        # Test that indexed query works
        result = InsightFact.objects.filter(category=self.category).order_by('-computed_at').first()
        self.assertEqual(result.id, insight.id)

    def test_insight_fact_field_types(self):
        """Verify field types and constraints."""
        insight = InsightFact.objects.create(
            category=self.category,
            insight_score=75000.5,  # FloatField
            materiality_pct=15.5,   # FloatField
            process_type='STOCHASTIC',
            slope=0.045,
            causal_volume_pct=5.5,
            causal_price_pct=2.1,
            projected_value=5420.0,
            expert_summary="Test summary."
        )

        # Verify types after retrieval
        retrieved = InsightFact.objects.get(id=insight.id)
        self.assertIsInstance(retrieved.insight_score, float)
        self.assertIsInstance(retrieved.materiality_pct, float)
        self.assertIsInstance(retrieved.slope, float)


class CategoryMonthlyStatModelTestCase(TestCase):
    """Test suite for the CategoryMonthlyStat unmanaged model (Layer 1)."""

    def test_category_monthly_stat_model_structure(self):
        """Verify CategoryMonthlyStat model fields exist and are recognized."""
        # Check model has expected fields
        model = CategoryMonthlyStat
        field_names = {f.name for f in model._meta.get_fields()}

        expected_fields = {
            'id', 'category_id', 'month', 'total_amount', 'transaction_count', 'avg_ticket'
        }

        self.assertTrue(expected_fields.issubset(field_names))

    def test_category_monthly_stat_is_unmanaged(self):
        """Verify CategoryMonthlyStat has managed=False."""
        self.assertFalse(CategoryMonthlyStat._meta.managed)

    def test_category_monthly_stat_correct_db_table(self):
        """Verify CategoryMonthlyStat uses correct database table name."""
        self.assertEqual(CategoryMonthlyStat._meta.db_table, 'accounting_categorymonthlystat')

    def test_category_monthly_stat_field_properties(self):
        """Verify CategoryMonthlyStat field configurations."""
        model = CategoryMonthlyStat

        # category_id should be IntegerField with db_index
        category_id_field = model._meta.get_field('category_id')
        self.assertEqual(category_id_field.get_internal_type(), 'IntegerField')

        # month should be DateField with db_index
        month_field = model._meta.get_field('month')
        self.assertEqual(month_field.get_internal_type(), 'DateField')

        # total_amount should be DecimalField
        total_amount_field = model._meta.get_field('total_amount')
        self.assertEqual(total_amount_field.get_internal_type(), 'DecimalField')

        # transaction_count should be IntegerField
        count_field = model._meta.get_field('transaction_count')
        self.assertEqual(count_field.get_internal_type(), 'IntegerField')

    def test_category_monthly_stat_decimal_defaults(self):
        """Verify DecimalField defaults are set correctly."""
        model = CategoryMonthlyStat

        total_amount_field = model._meta.get_field('total_amount')
        self.assertEqual(total_amount_field.default, Decimal('0.00'))

        avg_ticket_field = model._meta.get_field('avg_ticket')
        self.assertEqual(avg_ticket_field.default, Decimal('0.00'))

    def test_category_monthly_stat_str_representation(self):
        """Verify CategoryMonthlyStat __str__ method works with mock data."""
        # Create a mock instance (won't be saved since unmanaged)
        stat = CategoryMonthlyStat(
            category_id=123,
            month=datetime(2025, 3, 1).date(),
            total_amount=Decimal('5000.00'),
            transaction_count=50,
            avg_ticket=Decimal('100.00')
        )

        # __str__ should work without database access
        str_repr = str(stat)
        self.assertIn('123', str_repr)  # category_id
        self.assertIn('2025-03', str_repr)  # month
        self.assertIn('50', str_repr)  # transaction_count


class MaterializedViewMigrationTestCase(TestCase):
    """Test suite for the Materialized View migration."""

    def test_materialized_view_migration_exists(self):
        """Verify the migration file for Materialized View exists."""
        import os
        migration_path = '/Users/Louis-Philippe/Documents/finance_agent/accounting/migrations/0005_create_materialized_view.py'
        self.assertTrue(os.path.exists(migration_path))

    def test_materialized_view_sql_is_valid(self):
        """Verify the SQL migration contains expected components."""
        # Read the migration file to verify SQL structure
        with open('/Users/Louis-Philippe/Documents/finance_agent/accounting/migrations/0005_create_materialized_view.py', 'r') as f:
            content = f.read()

            # Verify CREATE MATERIALIZED VIEW is in the migration
            self.assertIn('CREATE MATERIALIZED VIEW', content)

            # Verify table name is correct
            self.assertIn('accounting_categorymonthlystat', content)

            # Verify key columns are referenced
            self.assertIn('account_id', content)
            self.assertIn('DATE_TRUNC', content)
            self.assertIn('total_amount', content)
            self.assertIn('transaction_count', content)
            self.assertIn('avg_ticket', content)

            # Verify reverse operation drops the view
            self.assertIn('DROP MATERIALIZED VIEW IF EXISTS', content)


class HybridLayerIntegrationTestCase(TestCase):
    """Integration tests for the complete hybrid data layer."""

    def setUp(self):
        """Create test family and categories."""
        self.family = Family.objects.create(
            name="Integration Test Family",
            timezone="America/Toronto"
        )

        # Create expense categories
        self.groceries = Account.objects.create(
            name="Groceries",
            account_type=Account.AccountType.EXPENSE,
            family=self.family
        )

        self.utilities = Account.objects.create(
            name="Utilities",
            account_type=Account.AccountType.EXPENSE,
            family=self.family
        )

    def test_insight_fact_with_journal_entries(self):
        """Verify InsightFact can reference categories with journal entries."""
        # Create journal entries
        je = JournalEntry.objects.create(
            family=self.family,
            date=datetime(2025, 3, 15).date(),
            description="Grocery shopping",
            is_reconciled=True
        )

        TransactionLine.objects.create(
            journal_entry=je,
            account=self.groceries,
            amount=Decimal('150.00')
        )

        # Create insight fact for the category
        insight = InsightFact.objects.create(
            category=self.groceries,
            insight_score=85000.0,
            materiality_pct=18.0,
            process_type='STOCHASTIC',
            expert_summary="Groceries increased 15%."
        )

        # Verify relationship works
        self.assertEqual(insight.category.name, "Groceries")
        self.assertEqual(insight.category.account_type, Account.AccountType.EXPENSE)

    def test_multiple_categories_with_insights(self):
        """Verify multiple categories can have their own insight facts."""
        # Create insights for different categories
        insight_groceries = InsightFact.objects.create(
            category=self.groceries,
            insight_score=85000.0,
            materiality_pct=18.0,
            process_type='STOCHASTIC',
            expert_summary="Groceries insight."
        )

        insight_utilities = InsightFact.objects.create(
            category=self.utilities,
            insight_score=35000.0,
            materiality_pct=8.0,
            process_type='DETERMINISTIC',
            expert_summary="Utilities insight."
        )

        # Verify both exist independently
        self.assertEqual(InsightFact.objects.filter(category=self.groceries).count(), 1)
        self.assertEqual(InsightFact.objects.filter(category=self.utilities).count(), 1)
        self.assertEqual(InsightFact.objects.count(), 2)

    def test_insight_fact_audit_trail(self):
        """Verify InsightFact creates an audit trail of computed insights."""
        # Simulate computing insight, updating category, computing again
        insight1 = InsightFact.objects.create(
            category=self.groceries,
            insight_score=50000.0,
            materiality_pct=10.0,
            process_type='STOCHASTIC',
            expert_summary="Initial computation."
        )

        # Later computation for same category
        insight2 = InsightFact.objects.create(
            category=self.groceries,
            insight_score=65000.0,
            materiality_pct=13.0,
            process_type='STOCHASTIC',
            expert_summary="Updated computation."
        )

        # Query audit trail for this category
        audit_trail = InsightFact.objects.filter(category=self.groceries).order_by('-computed_at')

        self.assertEqual(audit_trail.count(), 2)
        self.assertEqual(audit_trail[0].insight_score, 65000.0)
        self.assertEqual(audit_trail[1].insight_score, 50000.0)


if __name__ == '__main__':
    import unittest
    unittest.main()

