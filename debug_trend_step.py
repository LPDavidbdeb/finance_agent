import os
import django
import pandas as pd
import numpy as np

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
django.setup()

from accounting.models import Account, TransactionLine

def analyze_trend_step():
    target_family_name = "709rueBeaudoin"
    root_expenses = Account.objects.filter(name='Expenses', family__name=target_family_name, parent=None).first()
    
    trans_cat = Account.objects.filter(name='Transportation', parent=root_expenses).first()
    if not trans_cat:
        print("Transportation category not found.")
        return
        
    desc_ids = list(trans_cat.get_descendants(include_self=True).values_list('id', flat=True))
    lines_qs = TransactionLine.objects.filter(account_id__in=desc_ids).values('journal_entry__date', 'amount')
    df = pd.DataFrame(list(lines_qs))
    df['date'] = pd.to_datetime(df['journal_entry__date'])
    df['month'] = df['date'].dt.to_period('M')
    
    monthly = df.groupby('month')['amount'].sum().astype(float).sort_index()
    
    print("--- TRANSPORTATION MONTHLY HISTORY ---")
    for m, val in monthly.items():
        print(f"{m}: ${val:,.2f}")
    
    avg_total = monthly.mean()
    print(f"\nAll-time Average: ${avg_total:,.2f}")
    
    # Analyze the 'Step'
    if len(monthly) >= 6:
        last_3 = monthly.tail(3).mean()
        prev_3 = monthly.iloc[-6:-3].mean()
        print(f"Last 3 Months Avg: ${last_3:,.2f}")
        print(f"Previous 3 Months Avg: ${prev_3:,.2f}")
        print(f"Step Change: ${last_3 - prev_3:+.2f}")

if __name__ == "__main__":
    analyze_trend_step()
