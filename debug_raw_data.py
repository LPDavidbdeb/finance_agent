import os
import django
import pandas as pd
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
django.setup()

from accounting.models import Account, TransactionLine

def check_raw_data():
    target_family_name = "709rueBeaudoin"
    root_expenses = Account.objects.filter(name='Expenses', family__name=target_family_name, parent=None).first()
    
    if not root_expenses:
        print("Root Expenses not found")
        return

    print(f"--- RAW DATA AUDIT FOR {target_family_name} ---")
    
    # Total Expenses context
    all_exp_ids = list(root_expenses.get_descendants(include_self=True).values_list('id', flat=True))
    total_april = sum(l.amount for l in TransactionLine.objects.filter(account_id__in=all_exp_ids, journal_entry__date__year=2026, journal_entry__date__month=4))
    print(f"TOTAL EXPENSES APRIL 2026: ${float(total_april):,.2f}\n")

    for cat in root_expenses.get_children().order_by('name'):
        desc_ids = list(cat.get_descendants(include_self=True).values_list('id', flat=True))
        
        april_lines = TransactionLine.objects.filter(
            account_id__in=desc_ids,
            journal_entry__date__year=2026,
            journal_entry__date__month=4
        )
        april_total = float(sum(l.amount for l in april_lines))
        
        all_lines = TransactionLine.objects.filter(account_id__in=desc_ids)
        all_df = pd.DataFrame(list(all_lines.values('journal_entry__date', 'amount')))
        if not all_df.empty:
            all_df['month'] = pd.to_datetime(all_df['journal_entry__date']).dt.to_period('M')
            avg_per_month = float(all_df.groupby('month')['amount'].sum().mean())
        else:
            avg_per_month = 0.0
            
        if april_total != 0 or avg_per_month != 0:
            print(f"Category: {cat.name}")
            print(f"  April 2026: ${april_total:,.2f}")
            print(f"  Avg Monthly: ${avg_per_month:,.2f}")
            print(f"  Delta: ${april_total - avg_per_month:,.2f}")

if __name__ == "__main__":
    check_raw_data()
