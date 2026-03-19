from ninja import Router, errors
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth, TruncYear, TruncWeek
from django.shortcuts import get_object_or_404
from ninja_jwt.authentication import JWTAuth
from datetime import date
from typing import List, Literal, Optional
from decimal import Decimal

from .models import Account, TransactionLine, JournalEntry

router = Router(auth=JWTAuth())

@router.get("/spending-evolution")
def get_spending_evolution(
    request, 
    start_date: date, 
    end_date: date, 
    interval: Literal['bi-weekly', 'monthly', 'yearly'] = 'monthly'
):
    """
    Returns time-series spending data for descendants of the 'Expenses' root.
    """
    user = request.auth
    family = user.family

    # 1. Find the Expenses root for this family
    root_expenses = get_object_or_404(Account, family=family, name='Expenses', parent=None)
    expense_ids = root_expenses.get_descendants(include_self=True).values_list('id', flat=True)

    # 2. Query lines
    queryset = TransactionLine.objects.filter(
        journal_entry__family=family,
        account_id__in=expense_ids,
        journal_entry__date__range=[start_date, end_date]
    )

    # 3. Apply truncation
    if interval == 'monthly':
        trunc_func = TruncMonth('journal_entry__date')
    elif interval == 'yearly':
        trunc_func = TruncYear('journal_entry__date')
    else: # bi-weekly or default to weekly for now as Trunc doesn't support 14-day directly
        trunc_func = TruncWeek('journal_entry__date')

    results = queryset.annotate(period=trunc_func).values('period').annotate(total=Sum('amount')).order_by('period')

    # If bi-weekly requested, we'll do a post-processing step to group every 2 weeks
    if interval == 'bi-weekly':
        bi_weekly_results = []
        # results are ordered by period (Monday of each week)
        for i in range(0, len(results), 2):
            period = results[i]['period']
            amount = results[i]['total']
            if i + 1 < len(results):
                amount += results[i+1]['total']
            bi_weekly_results.append({
                "period": period.strftime("%Y-%m-%d"),
                "amount": float(amount)
            })
        return bi_weekly_results

    return [
        {
            "period": r['period'].strftime("%Y-%m" if interval == 'monthly' else "%Y" if interval == 'yearly' else "%Y-%m-%d"),
            "amount": float(r['total'])
        }
        for r in results
    ]

@router.get("/spending-by-category")
def get_spending_by_category(request, start_date: date, end_date: date):
    """
    Returns spending breakdown by top-level categories under 'Expenses'.
    """
    user = request.auth
    family = user.family

    root_expenses = get_object_or_404(Account, family=family, name='Expenses', parent=None)
    top_categories = root_expenses.get_children()

    results = []
    for cat in top_categories:
        descendant_ids = cat.get_descendants(include_self=True).values_list('id', flat=True)
        total = TransactionLine.objects.filter(
            journal_entry__family=family,
            account_id__in=descendant_ids,
            journal_entry__date__range=[start_date, end_date]
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        results.append({
            "category": cat.name,
            "amount": float(total)
        })

    # Sort by highest spend
    results.sort(key=lambda x: x['amount'], reverse=True)
    return results

@router.get("/annual-statements")
def get_annual_statements(request, year: int):
    """
    Returns Income Statement and Balance Sheet rolled-up totals for a given year.
    """
    user = request.auth
    family = user.family

    jan_1 = date(year, 1, 1)
    dec_31 = date(year, 12, 31)

    # Helper to sum lines for a root and date range
    def get_sum(root_name, start, end):
        root = Account.objects.filter(family=family, name=root_name, parent=None).first()
        if not root:
            return Decimal('0.00')
        ids = root.get_descendants(include_self=True).values_list('id', flat=True)
        return TransactionLine.objects.filter(
            journal_entry__family=family,
            account_id__in=ids,
            journal_entry__date__range=[start, end]
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    # Income Statement (strictly for the year)
    revenue = get_sum('Revenue', jan_1, dec_31)
    expenses = get_sum('Expenses', jan_1, dec_31)
    
    # Net Income = -Revenue (credits are negative) - Expenses (debits are positive)
    net_income = -revenue - expenses

    # Balance Sheet (cumulative up to dec_31)
    # Cumulative helper
    def get_cumulative_sum(root_name, up_to_date):
        root = Account.objects.filter(family=family, name=root_name, parent=None).first()
        if not root:
            return Decimal('0.00')
        ids = root.get_descendants(include_self=True).values_list('id', flat=True)
        return TransactionLine.objects.filter(
            journal_entry__family=family,
            account_id__in=ids,
            journal_entry__date__lte=up_to_date
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    assets = get_cumulative_sum('Assets', dec_31)
    liabilities = get_cumulative_sum('Liabilities', dec_31)
    equity = get_cumulative_sum('Equity', dec_31)

    return {
        "year": year,
        "income_statement": {
            "revenue": float(-revenue),
            "expenses": float(expenses),
            "net_income": float(net_income)
        },
        "balance_sheet": {
            "assets": float(assets),
            "liabilities": float(-liabilities),
            "equity": float(-equity),
            "check": float(assets + liabilities + equity) # Should be zero
        }
    }
