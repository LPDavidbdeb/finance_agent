import os
import django
import pandas as pd
import numpy as np

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
django.setup()

from accounting.models import Account, TransactionLine

def reconcile():
    target_family_name = "709rueBeaudoin"
    
    # Get ALL transactions for this family
    lines = TransactionLine.objects.filter(journal_entry__family__name=target_family_name).values(
        'journal_entry__date', 'amount', 'account__name', 'journal_entry__description'
    )
    df = pd.DataFrame(list(lines))
    df['date'] = pd.to_datetime(df['journal_entry__date'])
    df['month'] = df['date'].dt.to_period('M')
    df['amount'] = df['amount'].astype(float)
    
    # Strictly Expenses (to match the 6000 vs 4000 comparison)
    # We'll filter for account names that usually sit under Expenses
    expense_root = Account.objects.filter(name='Expenses', family__name=target_family_name, parent=None).first()
    exp_ids = list(expense_root.get_descendants(include_self=True).values_list('id', flat=True))
    
    df_exp = df[df['journal_entry__date'].isin(
        TransactionLine.objects.filter(account_id__in=exp_ids).values_list('journal_entry__date', flat=True)
    )].copy()
    
    # Actually, let's just use the expense series properly
    exp_lines = TransactionLine.objects.filter(account_id__in=exp_ids).values('journal_entry__date', 'amount', 'journal_entry__description')
    df_exp = pd.DataFrame(list(exp_lines))
    df_exp['date'] = pd.to_datetime(df_exp['journal_entry__date'])
    df_exp['month'] = df_exp['date'].dt.to_period('M')
    df_exp['amount'] = df_exp['amount'].astype(float)

    monthly_exp = df_exp.groupby('month')['amount'].sum()
    
    num_months = len(monthly_exp)
    all_time_avg = monthly_exp.mean()
    april_2026 = monthly_exp.get(pd.Period('2026-04', freq='M'), 0)
    
    print(f"--- RECONCILIATION REPORT ---")
    print(f"Total Months of Data: {num_months}")
    print(f"All-Time Monthly Average: ${all_time_avg:,.2f}")
    print(f"April 2026 Total: ${april_2026:,.2f}")
    print(f"Gross Variance: ${april_2026 - all_time_avg:,.2f}\n")
    
    # 1. Impact of Outliers (Home Improvement)
    renov_merchants = ['ENTREPRISE DYNAMIC', 'ALERTE FISSURE']
    renov_total = df_exp[df_exp['journal_entry__description'].str.contains('|'.join(renov_merchants), na=False)]['amount'].sum()
    # How much did this add to the average? (Total / Total Months)
    renov_impact_on_avg = renov_total / num_months
    
    print(f"Home Improvement Outliers:")
    print(f"  Total Renov Cost: ${renov_total:,.2f}")
    print(f"  Impact on Average: +${renov_impact_on_avg:,.2f} per month (forever)")
    
    # 2. Adjusted Baseline (Excluding massive one-offs)
    adjusted_avg = (monthly_exp.sum() - renov_total) / num_months
    print(f"\nAdjusted Baseline (No Renov): ${adjusted_avg:,.2f}")
    print(f"Variance vs Adjusted: ${april_2026 - adjusted_avg:,.2f} (Much smaller!)\n")
    
    # 3. Car Payment Verification
    car_payments = df_exp[(df_exp['date'] >= '2026-02-01') & (df_exp['account__name'].str.contains('Transportation', na=False))]
    # Or maybe it's under a specific merchant?
    print(f"Car Payment Check (Post-Feb 2026 Transportation):")
    trans_recent = df_exp[(df_exp['month'] >= '2026-02') & (df_exp['journal_entry__description'].str.contains('FINANCEMENT', na=False))]
    if not trans_recent.empty:
        print(f"  Found potential car payment: {trans_recent.iloc[0]['journal_entry__description']} - ${trans_recent.iloc[0]['amount']:,.2f}")
    else:
        # Check all transportation in April
        april_trans = df_exp[(df_exp['month'] == '2026-04') & (df_exp['journal_entry__description'].str.contains('DESJARDINS', na=False))]
        print(f"  April Trans Sample: {april_trans.head(2)[['journal_entry__description', 'amount']].to_dict('records')}")

if __name__ == "__main__":
    reconcile()
