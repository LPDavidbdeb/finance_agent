#!/usr/bin/env python
"""
Quick test to verify ETL pipeline with enriched fixtures.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
django.setup()

from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase

from accounting.models import Account, JournalEntry, TransactionLine
from accounting.tasks import (
    rebuild_financial_insights,
    _refresh_materialized_view,
    _extract_category_data,
    _transform_through_pipeline,
    _load_insights,
)
from users.models import Family


def create_enriched_test_data():
    """Create enriched test data that passes Step-0 filters."""
    # Create family
    family = Family.objects.create(name="ETL Test Family")

    # Create expense categories
    groceries = Account.objects.create(
        name="Groceries",
        account_type=Account.AccountType.EXPENSE,
        family=family
    )

    utilities = Account.objects.create(
        name="Utilities",
        account_type=Account.AccountType.EXPENSE,
        family=family
    )

    # Create bank account for transactions
    bank = Account.objects.create(
        name="Chequing Account",
        account_type=Account.AccountType.ASSET,
        family=family
    )

    # Create 12 months of historical data with MULTIPLE transactions per month
    for month_offset in range(12):
        # Calculate the date for this month (normalized to 1st of month)
        base_date = (datetime.now().date() - timedelta(days=30 * month_offset)).replace(day=1)

        # Groceries: 4 transactions per month, $550 each = $2200/month
        for week in range(0, 4):
            transaction_date = base_date + timedelta(days=7 * week)

            je = JournalEntry.objects.create(
                family=family,
                date=transaction_date,
                description=f"Grocery shopping week {week + 1}",
                is_reconciled=True
            )

            TransactionLine.objects.create(
                journal_entry=je,
                account=groceries,
                amount=Decimal('550.00')
            )

            TransactionLine.objects.create(
                journal_entry=je,
                account=bank,
                amount=Decimal('-550.00')
            )

        # Utilities: 2 transactions per month, $600 each = $1200/month
        for utility_idx in range(2):
            transaction_date = base_date + timedelta(days=15 * (utility_idx + 1))

            je2 = JournalEntry.objects.create(
                family=family,
                date=transaction_date,
                description=f"Utility payment {utility_idx + 1}",
                is_reconciled=True
            )

            TransactionLine.objects.create(
                journal_entry=je2,
                account=utilities,
                amount=Decimal('600.00')
            )

            TransactionLine.objects.create(
                journal_entry=je2,
                account=bank,
                amount=Decimal('-600.00')
            )

    # Refresh materialized view
    _refresh_materialized_view()

    return family


def main():
    """Test the ETL pipeline."""
    print("🔄 Creating enriched test data...")
    family = create_enriched_test_data()
    print(f"✅ Created family: {family.name}")

    print("\n🔄 Running ETL pipeline...")
    try:
        result = rebuild_financial_insights(family_id=family.id)
        print(f"✅ Pipeline executed:")
        print(f"   - Families processed: {result['families_processed']}")
        print(f"   - Insights created: {result['insights_created']}")
        print(f"   - Analysis runs created: {result['analysis_runs_created']}")

        if result['insights_created'] > 0:
            print("\n✅ SUCCESS: ETL pipeline returned profiles!")
        else:
            print("\n❌ ISSUE: ETL pipeline returned zero profiles")

            # Diagnose
            print("\n🔍 Diagnostic info:")
            dataframes = _extract_category_data(family)
            print(f"   - Extracted {len(dataframes)} categories")
            for cat_id, series in dataframes.items():
                account = Account.objects.get(id=cat_id)
                print(f"   - {account.name}: {len(series)} months of data")

            if dataframes:
                print("\n   - Running transform...")
                profiles = _transform_through_pipeline(family, dataframes)
                print(f"   - Transform returned {len(profiles)} profiles")
                if profiles:
                    for p in profiles:
                        print(f"     - {p.category_name}: materiality={p.materiality_pct:.1f}%, sparsity={getattr(p, 'sparsity_status', 'unknown')}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()


