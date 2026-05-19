import os
import django
import pandas as pd
import numpy as np

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
django.setup()

from accounting.models import Account, TransactionLine
from accounting.analysis.classification import ProcessClassifier
from accounting.analysis.volatility import VolatilityAnalyzer
from accounting.analysis.causal import CausalAnalyzer
from accounting.analysis.trend import TrendAnalyzer
from accounting.analysis.insights import InsightEngine, CategoryProfile

def analyze_april_variance():
    target_family_name = "709rueBeaudoin"
    root_expenses = Account.objects.filter(name='Expenses', family__name=target_family_name, parent=None).first()
    
    if not root_expenses:
        print(f"Root Expenses account for family '{target_family_name}' not found.")
        return
        
    expense_ids = list(root_expenses.get_descendants(include_self=True).values_list('id', flat=True))
    all_qs = TransactionLine.objects.filter(account_id__in=expense_ids).values('journal_entry__date', 'amount')
    df_all = pd.DataFrame(list(all_qs))
    
    df_all['date'] = pd.to_datetime(df_all['journal_entry__date'])
    df_all['amount'] = df_all['amount'].astype(float)
    df_all['month'] = df_all['date'].dt.to_period('M')
    
    target_month = pd.Period('2026-04', freq='M')
    
    monthly_totals = df_all.groupby('month')['amount'].sum()
    avg_total = monthly_totals.mean()
    target_total = monthly_totals.get(target_month, 0)
    
    print(f"--- DIAGNOSTIC: APRIL 2026 VARIANCE (Family: {target_family_name}) ---")
    print(f"Total Expenses: ${target_total:,.2f} (Avg: ${avg_total:,.2f})")
    print(f"Net Variance: ${target_total - avg_total:,.2f}\n")

    top_categories = root_expenses.get_children().order_by('name')
    profiles = []
    engine = InsightEngine()
    classifier = ProcessClassifier()
    vol_analyzer = VolatilityAnalyzer()
    trend_analyzer = TrendAnalyzer()
    causal_analyzer = CausalAnalyzer()

    for cat in top_categories:
        cat_ids = list(cat.get_descendants(include_self=True).values_list('id', flat=True))
        lines_qs = TransactionLine.objects.filter(account_id__in=cat_ids).values('journal_entry__date', 'amount', 'journal_entry__description')
        
        if not lines_qs.exists():
            continue
            
        df = pd.DataFrame(list(lines_qs))
        df['date'] = pd.to_datetime(df['journal_entry__date'])
        df['amount'] = df['amount'].astype(float)
        df['month'] = df['date'].dt.to_period('M')
        
        series = df.groupby('month')['amount'].sum()
        series = series.reindex(monthly_totals.index, fill_value=0.0)
        
        month_spend = series.get(target_month, 0)
        cat_avg = series.mean()
        
        # We only pass the CATEGORY data to the analyzers
        # Causal analysis: Compare target_month vs its own average or prior periods
        causal = None
        try:
            causal_df = df.rename(columns={'journal_entry__description': 'merchant_name'})
            # Perform causal analysis up to the target month
            causal = causal_analyzer.analyze(causal_df, reference_date=target_month.to_timestamp() + pd.offsets.MonthEnd(0))
        except Exception:
            pass
            
        # Materiality is current month contribution
        materiality = (month_spend / target_total * 100) if target_total > 0 else 0
        
        trend = trend_analyzer.analyze(series)
        predicted = pd.Series([series.mean()] * len(series), index=series.index)
        vol = vol_analyzer.analyze(series, predicted)
        
        profile = CategoryProfile(
            category_name=cat.name,
            materiality_pct=materiality,
            process_type=classifier.classify(series),
            trend_result=trend,
            volatility_result=vol,
            causal_result=causal
        )
        
        # CUSTOM DIAGNOSTIC OUTPUT
        if abs(month_spend - cat_avg) > 100 or materiality > 10:
            print(f"CATEGORY: {cat.name}")
            print(f"  April Spend: ${month_spend:,.2f} (Avg: ${cat_avg:,.2f}) | Delta: ${month_spend - cat_avg:+.2f}")
            print(f"  Materiality: {materiality:.1f}% of April total")
            
            if causal:
                print(f"  Causal Diagnostic (L12M vs P12M baseline):")
                print(f"    - Volume Effect: {causal.volume_effect_pct:+.1f}% (Shift in transaction frequency)")
                print(f"    - Intensity Effect: {causal.price_effect_pct:+.1f}% (Shift in average transaction size)")
                if causal.mix_shift_detected:
                    print(f"    - ALERT: Structural merchant loyalty shift detected.")
            
            # Simple expert summary
            print(f"  Engine Insight: {engine.generate_expert_summary(profile)}")
            print("-" * 40)

if __name__ == "__main__":
    analyze_april_variance()
