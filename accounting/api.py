from ninja import Router, errors
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth, TruncYear, TruncWeek
from django.shortcuts import get_object_or_404
from ninja_jwt.authentication import JWTAuth
from datetime import date
from typing import List, Literal, Optional
from decimal import Decimal

from .models import Account, TransactionLine, JournalEntry
from .schemas import AccountDetailOut, DimensionBreakdownOut, AccountCreateIn, AccountOut
from categorization.models import Merchant

router = Router(auth=JWTAuth())

@router.post("/accounts", response={201: AccountOut})
def create_account(request, payload: AccountCreateIn):
    """
    Creates a new sub-account under an existing parent for the user's family.
    """
    user = request.auth
    parent = get_object_or_404(Account, id=payload.parent_id, family=user.family)
    
    clean_name = payload.name.strip()
    if not clean_name:
        raise errors.HttpError(400, "Account name cannot be empty.")

    # Prevent duplicates under same parent
    if Account.objects.filter(parent=parent, name__iexact=clean_name, family=user.family).exists():
        raise errors.HttpError(400, f"An account named '{clean_name}' already exists under this parent.")

    # Enforce type inheritance and name normalization
    account = Account.objects.create(
        name=clean_name.upper(),
        parent=parent,
        account_type=parent.account_type,
        family=user.family
    )
    return 201, account

@router.delete("/accounts/{account_id}", response={204: None})
def delete_account(request, account_id: int):
    """
    Deletes an account if it belongs to the family and has no transaction history.
    Blocks deletion of non-leaf nodes.
    """
    user = request.auth
    account = get_object_or_404(Account, id=account_id, family=user.family)

    # Check for transaction history
    if TransactionLine.objects.filter(account=account).exists():
        raise errors.HttpError(400, "This account cannot be deleted because it has transaction history.")

    # Block deletion of non-leaf nodes (nodes with children)
    if not account.is_leaf_node():
        raise errors.HttpError(400, "Cannot delete account because it has sub-accounts. Delete the children first.")

    account.delete()
    return 204, None

@router.get("/reports/dimension/{dimension_slug}", response=DimensionBreakdownOut)
def get_dimension_breakdown(request, dimension_slug: str, year: int):
    """
    Returns a detailed breakdown of a specific financial dimension for a given year.
    Uses a branch-wide aggregation logic.
    """
    user = request.auth
    family = user.family
    jan_1 = date(year, 1, 1)
    dec_31 = date(year, 12, 31)

    dimension_name = dimension_slug.replace('-', ' ').title()
    
    # 1. Identify the root node
    root_map = {
        'revenue': 'Revenue',
        'expenses': 'Expenses',
        'assets': 'Assets',
        'liabilities': 'Liabilities',
        'equity': 'Equity'
    }
    
    if dimension_slug not in root_map and dimension_slug not in ['net-income', 'net-worth']:
        raise errors.HttpError(404, f"Dimension {dimension_slug} not recognized.")

    if dimension_slug in ['net-income', 'net-worth']:
        # Handle calculated dimensions
        if dimension_slug == 'net-income':
            root_rev = get_object_or_404(Account, family=family, name='Revenue', parent=None)
            root_exp = get_object_or_404(Account, family=family, name='Expenses', parent=None)
            rev_bal = get_branch_sum(family, root_rev, jan_1, dec_31, False)
            exp_bal = get_branch_sum(family, root_exp, jan_1, dec_31, False)
            return {
                "dimension_name": "Net Income",
                "total_amount": float(-rev_bal - exp_bal),
                "line_items": [
                    {"name": "Total Revenue", "balance": float(-rev_bal)},
                    {"name": "Total Expenses", "balance": float(exp_bal)}
                ]
            }
        else: # net-worth
            root_ast = get_object_or_404(Account, family=family, name='Assets', parent=None)
            root_lib = get_object_or_404(Account, family=family, name='Liabilities', parent=None)
            ast_bal = get_branch_sum(family, root_ast, jan_1, dec_31, True)
            lib_bal = get_branch_sum(family, root_lib, jan_1, dec_31, True)
            return {
                "dimension_name": "Net Worth",
                "total_amount": float(ast_bal + lib_bal),
                "line_items": [
                    {"name": "Total Assets", "balance": float(ast_bal)},
                    {"name": "Total Liabilities", "balance": float(-lib_bal)}
                ]
            }

    # 2. Handle standard dimensions
    root_name = root_map[dimension_slug]
    root = get_object_or_404(Account, family=family, name=root_name, parent=None)
    is_cumulative = dimension_slug in ['assets', 'liabilities', 'equity']
    flip_sign = dimension_slug in ['revenue', 'liabilities', 'equity']

    # Calculate the True Total for the entire branch first
    true_total_balance = get_branch_sum(family, root, jan_1, dec_31, is_cumulative)

    # Fetch immediate children
    children = root.get_children()
    line_items = []
    child_sum = Decimal('0.00')

    for child in children:
        # Sum all transactions for this child and all its descendants
        balance = get_branch_sum(family, child, jan_1, dec_31, is_cumulative)
        child_sum += balance
        display_bal = -balance if flip_sign else balance
        
        # SCOPING FIX: Fetch sub-items (Banners) specifically for this child's branch
        child_descendant_ids = child.get_descendants(include_self=True).values_list('id', flat=True)
        q_child = Q(journal_entry__family=family, account_id__in=child_descendant_ids)
        if is_cumulative:
            q_child &= Q(journal_entry__date__lte=dec_31)
        else:
            q_child &= Q(journal_entry__date__year=year)
            
        sums = TransactionLine.objects.filter(q_child).values('journal_entry__description').annotate(total=Sum('amount'))
        
        sub_items_list = []
        for item in sums:
            val = -item['total'] if flip_sign else item['total']
            if abs(val) > Decimal('0.01'):
                sub_items_list.append({
                    "name": item['journal_entry__description'],
                    "balance": float(val)
                })
        
        line_items.append({
            "id": child.id,
            "name": child.name,
            "balance": float(display_bal),
            "sub_items": sorted(sub_items_list, key=lambda x: x['balance'], reverse=True)
        })

    # Calculate the Direct Root Remainder
    root_direct_bal = true_total_balance - child_sum
    display_root_direct = -root_direct_bal if flip_sign else root_direct_bal
    
    if abs(display_root_direct) > Decimal('0.01'):
        # Query banners directly mapped strictly to the root ID
        q_root_strict = Q(journal_entry__family=family, account_id=root.id)
        if is_cumulative:
            q_root_strict &= Q(journal_entry__date__lte=dec_31)
        else:
            q_root_strict &= Q(journal_entry__date__year=year)
            
        root_sums = TransactionLine.objects.filter(q_root_strict).values('journal_entry__description').annotate(total=Sum('amount'))
        
        root_sub_items = []
        for item in root_sums:
            val = -item['total'] if flip_sign else item['total']
            if abs(val) > Decimal('0.01'):
                root_sub_items.append({
                    "name": item['journal_entry__description'],
                    "balance": float(val)
                })
        
        line_items.append({
            "id": root.id,
            "name": f"Directly under {root_name}",
            "balance": float(display_root_direct),
            "sub_items": sorted(root_sub_items, key=lambda x: x['balance'], reverse=True)
        })

    total_amount = -true_total_balance if flip_sign else true_total_balance

    # 3. Handle Merchant (Banner) breakdown for the entire root branch (Global View)
    all_descendants = root.get_descendants(include_self=True)
    all_merchants = Merchant.objects.filter(family=family, default_account__in=all_descendants)
    
    # Grouped sums by clean_description
    q_all = Q(journal_entry__family=family, account_id__in=all_descendants.values_list('id', flat=True))
    if is_cumulative:
        q_all &= Q(journal_entry__date__lte=dec_31)
    else:
        q_all &= Q(journal_entry__date__range=[jan_1, dec_31])
        
    merchant_sums = TransactionLine.objects.filter(q_all).values('journal_entry__description').annotate(total=Sum('amount'))
    merchant_sum_dict = {item['journal_entry__description']: item['total'] for item in merchant_sums}

    merchant_items = []
    for m in all_merchants:
        m_bal = merchant_sum_dict.get(m.name, Decimal('0.00'))
        m_display_bal = -m_bal if flip_sign else m_bal
        
        # Only include if there's activity or requested
        merchant_items.append({
            "id": m.id,
            "name": m.name,
            "balance": float(m_display_bal)
        })

    # Sort merchant items by balance
    merchant_items.sort(key=lambda x: abs(x['balance']), reverse=True)

    # Final result
    return {
        "dimension_name": dimension_name,
        "total_amount": float(total_amount),
        "line_items": sorted(line_items, key=lambda x: x['balance'], reverse=True),
        "merchant_items": merchant_items
    }

def get_branch_sum(family, account, start, end, cumulative):
    """
    Helper to sum all transaction lines for an account and its descendants.
    """
    descendant_ids = account.get_descendants(include_self=True).values_list('id', flat=True)
    q = Q(journal_entry__family=family, account_id__in=descendant_ids)
    
    if cumulative:
        q &= Q(journal_entry__date__lte=end)
    else:
        q &= Q(journal_entry__date__range=[start, end])
        
    return TransactionLine.objects.filter(q).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

import numpy as np
from django.db.models import StdDev

@router.get("/accounts/{account_id}", response=AccountDetailOut)
def get_account_detail(request, account_id: int, year: Optional[int] = None):
    """
    Returns full details for an account with CFA-grade analytical insights.
    """
    if year is None:
        year = date.today().year

    user = request.auth
    family = user.family
    account = get_object_or_404(Account, id=account_id, family=family)

    # 1. Branch Data
    descendants = account.get_descendants(include_self=True)
    
    # 2. Financial Context (Current vs Previous)
    def get_sum(branch_qs, target_year):
        val = TransactionLine.objects.filter(
            journal_entry__family=family,
            account__in=branch_qs,
            journal_entry__date__year=target_year
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        return abs(float(val))

    amt_current = get_sum(descendants, year)
    amt_previous = get_sum(descendants, year - 1)
    
    # 3. Denominators for Share calculations
    parent_amt = get_sum(account.parent.get_descendants(include_self=True) if account.parent else descendants, year)
    root_revenue = Account.objects.filter(name='Revenue', parent=None, family=family).first()
    total_revenue_curr = get_sum(root_revenue.get_descendants(include_self=True) if root_revenue else Account.objects.none(), year)
    total_revenue_prev = get_sum(root_revenue.get_descendants(include_self=True) if root_revenue else Account.objects.none(), year - 1)
    
    total_assets_ids = Account.objects.filter(name='Assets', parent=None, family=family).first()
    # Assets are cumulative
    total_assets = abs(float(TransactionLine.objects.filter(
        journal_entry__family=family,
        account__in=total_assets_ids.get_descendants(include_self=True) if total_assets_ids else Account.objects.none(),
        journal_entry__date__lte=date(year, 12, 31)
    ).aggregate(total=Sum('amount'))['total'] or 0.0))

    # 4. Math Calculations
    yoy_growth = (amt_current - amt_previous) / amt_previous if amt_previous > 0 else None
    revenue_growth = (total_revenue_curr - total_revenue_prev) / total_revenue_prev if total_revenue_prev > 0 else 0
    
    # Volatility (Std Dev of monthly sums)
    monthly_sums = TransactionLine.objects.filter(
        journal_entry__family=family,
        account__in=descendants,
        journal_entry__date__year=year
    ).annotate(month=TruncMonth('journal_entry__date')).values('month').annotate(total=Sum('amount')).values_list('total', flat=True)
    volatility = float(np.std([float(x) for x in monthly_sums])) if monthly_sums else 0.0

    # Merchants & Concentration
    sums = TransactionLine.objects.filter(
        journal_entry__family=family,
        account__in=descendants,
        journal_entry__date__year=year
    ).values('journal_entry__description').annotate(total=Sum('amount'))
    sum_dict = {item['journal_entry__description']: abs(float(item['total'])) for item in sums}
    
    merchant_list = []
    merchants_objs = Merchant.objects.filter(family=family, default_account__in=descendants)
    for m in merchants_objs:
        bal = sum_dict.get(m.name, 0.0)
        merchant_list.append({"id": m.id, "name": m.name, "balance": bal})
    merchant_list.sort(key=lambda x: x['balance'], reverse=True)
    
    concentration = (merchant_list[0]['balance'] / amt_current) if amt_current > 0 and merchant_list else 0.0

    # CFA Flags
    red_flag = None
    green_flag = None
    health_tag = "stable"
    drift = (yoy_growth - revenue_growth) if yoy_growth is not None else 0
    
    if account.account_type == 'EXPENSE' and drift > 0.05:
        health_tag = "drifting"
        red_flag = {"title": "Operational Drift", "detail": f"Category growing {drift*100:.1f}% faster than income."}
    elif concentration > 0.5:
        health_tag = "concentrated"
        red_flag = {"title": "Concentration Risk", "detail": f"Top vendor accounts for {concentration*100:.0f}% of spend."}
    
    if yoy_growth is not None and yoy_growth < -0.1 and account.account_type == 'EXPENSE':
        green_flag = {"title": "Efficiency Gain", "detail": "Category spend reduced by >10% YoY."}

    # 5. Historical Trends (Last 5 years)
    historical_trends = []
    current_year_const = date.today().year
    
    total_sum_all_years = 0.0
    valid_years_count = 0

    children_objs = list(account.get_children())

    for y in range(current_year_const - 4, current_year_const + 1):
        year_total = get_sum(descendants, y)
        
        # Calculate breakdown by children
        breakdown_dict = {}
        if children_objs:
            for child in children_objs:
                child_branch = child.get_descendants(include_self=True)
                child_val = get_sum(child_branch, y)
                if child_val > 0:
                    breakdown_dict[child.name] = child_val
        else:
            # Fallback to top 5 merchants if no sub-accounts exist
            top_merchants_desc = TransactionLine.objects.filter(
                journal_entry__family=family,
                account__in=descendants,
                journal_entry__date__year=y
            ).values('journal_entry__description').annotate(total=Sum('amount')).order_by('-total')[:5]
            for item in top_merchants_desc:
                if item['total']:
                    breakdown_dict[item['journal_entry__description']] = abs(float(item['total']))

        historical_trends.append({
            "year": y,
            "total": year_total,
            "monthly_avg": year_total / 12,
            "breakdown": breakdown_dict
        })
        
        if year_total > 0:
            total_sum_all_years += year_total
            valid_years_count += 1

    avg_yearly = total_sum_all_years / valid_years_count if valid_years_count > 0 else 0.0

    # Manual result
    return {
        "id": account.id,
        "name": account.name,
        "account_type": account.account_type,
        "parent_id": account.parent_id,
        "children": list(account.get_children()),
        "merchants": merchant_list,
        "insights": {
            "amount_current": amt_current,
            "amount_previous": amt_previous,
            "yoy_growth": yoy_growth,
            "share_of_parent": (amt_current / parent_amt) if parent_amt > 0 else 1.0,
            "share_of_total_inflow": (amt_current / total_revenue_curr) if total_revenue_curr > 0 else 0.0,
            "volatility_score": volatility,
            "concentration_top_1": concentration,
            "drift_spread": drift if account.account_type == 'EXPENSE' else None,
            "optimization_headroom": (merchant_list[0]['balance'] * 0.05) if merchant_list else 0.0,
            "burn_coverage_days": (total_assets / (amt_current / 365)) if amt_current > 0 else None,
            "health_tag": health_tag,
            "red_flag": red_flag,
            "green_flag": green_flag,
            "strategic_action": {
                "action": f"Review {merchant_list[0]['name'] if merchant_list else 'vendors'} for 5% optimization." if health_tag == 'concentrated' else "No immediate action required.",
                "owner": "household",
                "time_horizon": "30d"
            }
        },
        "historical_trends": historical_trends,
        "avg_yearly_total": avg_yearly,
        "avg_monthly_avg": avg_yearly / 12
    }

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
