import os
import django
import pandas as pd
import numpy as np

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
django.setup()

from accounting.models import Account, TransactionLine

def analyze_shelter_series():
    target_family_name = "709rueBeaudoin"
    root_expenses = Account.objects.filter(name='Expenses', family__name=target_family_name, parent=None).first()
    
    shelter_cat = Account.objects.filter(name='Shelter', parent=root_expenses).first()
    if not shelter_cat:
        print("Shelter category not found.")
        return
        
    desc_ids = list(shelter_cat.get_descendants(include_self=True).values_list('id', flat=True))
    lines_qs = TransactionLine.objects.filter(account_id__in=desc_ids).values('journal_entry__date', 'amount', 'journal_entry__description')
    df = pd.DataFrame(list(lines_qs))
    df['date'] = pd.to_datetime(df['journal_entry__date'])
    df['month'] = df['date'].dt.to_period('M')
    
    monthly = df.groupby('month')['amount'].sum().astype(float).sort_index()
    
    print("--- SHELTER MONTHLY HISTORY ---")
    for m, val in monthly.items():
        # Get top merchant for that month for context
        top_tx = df[df['month'] == m].sort_values('amount', ascending=False).iloc[0] if not df[df['month'] == m].empty else None
        merchant = top_tx['journal_entry__description'] if top_tx is not None else "N/A"
        print(f"{m}: ${val:,.2f} (Primary: {merchant})")
    
    avg_total = monthly.mean()
    print(f"\nAll-time Average: ${avg_total:,.2f}")
    
    if len(monthly) >= 6:
        print(f"Latest Month (2026-04): ${monthly.get(pd.Period('2026-04', freq='M'), 0):,.2f}")
        print(f"Previous Month (2026-03): ${monthly.get(pd.Period('2026-03', freq='M'), 0):,.2f}")

if __name__ == "__main__":
    analyze_shelter_series()
