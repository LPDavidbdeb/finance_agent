from collections import defaultdict

from ninja import Router, errors
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth, TruncYear, TruncWeek
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from ninja_jwt.authentication import JWTAuth
from datetime import date
from typing import List, Literal, Optional
from decimal import Decimal
from dateutil.relativedelta import relativedelta
import numpy as np

from .models import Account, TransactionLine, JournalEntry
from .pdf_reports import build_monthly_expense_report_pdf
from .schemas import (
    AccountDetailOut, DimensionBreakdownOut, AccountCreateIn, AccountOut,
    DrillDownOut, DrillDownBannerOut, BannerTransactionOut, RerouteIn, FlatAccountOut,
    AnnualHistoryOut,
    AccountTransactionOut,
    MonthlyExpenseReportOut,
)
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
    Uses a branch-wide aggregation logic with direct root remainder handling.
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
        # Handle calculated dimensions (Net Income / Net Worth)
        if dimension_slug == 'net-income':
            root_rev = get_object_or_404(Account, family=family, name='Revenue', parent=None)
            root_exp = get_object_or_404(Account, family=family, name='Expenses', parent=None)
            rev_bal = get_branch_sum(family, root_rev, jan_1, dec_31, False)
            exp_bal = get_branch_sum(family, root_exp, jan_1, dec_31, False)
            return {
                "dimension_name": "Net Income",
                "total_amount": float(-rev_bal - exp_bal),
                "line_items": [
                    {"name": "Total Revenue", "balance": float(-rev_bal), "sub_items": []},
                    {"name": "Total Expenses", "balance": float(exp_bal), "sub_items": []}
                ],
                "merchant_items": []
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
                    {"name": "Total Assets", "balance": float(ast_bal), "sub_items": []},
                    {"name": "Total Liabilities", "balance": float(-lib_bal), "sub_items": []}
                ],
                "merchant_items": []
            }

    # 2. Handle standard dimensions (Revenue, Expenses, etc.)
    root_name = root_map[dimension_slug]
    root = get_object_or_404(Account, family=family, name=root_name, parent=None)
    is_cumulative = dimension_slug in ['assets', 'liabilities', 'equity']
    flip_sign = dimension_slug in ['revenue', 'liabilities', 'equity']

    # Step A: Calculate the True Total for the entire root branch first
    true_total_balance = get_branch_sum(family, root, jan_1, dec_31, is_cumulative)

    # Fetch immediate children
    children = root.get_children()
    line_items = []
    child_sum = Decimal('0.00')

    for child in children:
        # Sum all transactions for this child and ALL its descendants
        balance = get_branch_sum(family, child, jan_1, dec_31, is_cumulative)
        child_sum += balance
        display_bal = -balance if flip_sign else balance

        sub_children = list(child.get_children())

        if sub_children:
            # Child has sub-accounts (e.g. Food → Restaurants, Grocery Stores).
            # Build sub_items as grouped subcategory nodes, each with their merchant list.
            sub_items_list = []

            for sub_child in sub_children:
                sub_bal = get_branch_sum(family, sub_child, jan_1, dec_31, is_cumulative)
                sub_display = -sub_bal if flip_sign else sub_bal
                if abs(sub_display) < Decimal('0.01'):
                    continue

                sc_ids = sub_child.get_descendants(include_self=True).values_list('id', flat=True)
                q_sc = Q(journal_entry__family=family, account_id__in=sc_ids)
                if is_cumulative:
                    q_sc &= Q(journal_entry__date__lte=dec_31)
                else:
                    q_sc &= Q(journal_entry__date__year=year)

                sc_sums = TransactionLine.objects.filter(q_sc).values('journal_entry__description').annotate(total=Sum('amount'))
                merchants = []
                for item in sc_sums:
                    val = -item['total'] if flip_sign else item['total']
                    if abs(val) > Decimal('0.01'):
                        merchants.append({"name": item['journal_entry__description'], "balance": float(val)})

                sub_items_list.append({
                    "name": sub_child.name,
                    "balance": float(sub_display),
                    "type": "subcategory",
                    "merchants": sorted(merchants, key=lambda x: x['balance'], reverse=True)
                })

            # Also surface any transactions posted directly to the child account itself
            q_direct = Q(journal_entry__family=family, account_id=child.id)
            if is_cumulative:
                q_direct &= Q(journal_entry__date__lte=dec_31)
            else:
                q_direct &= Q(journal_entry__date__year=year)

            direct_sums = TransactionLine.objects.filter(q_direct).values('journal_entry__description').annotate(total=Sum('amount'))
            direct_merchants = []
            for item in direct_sums:
                val = -item['total'] if flip_sign else item['total']
                if abs(val) > Decimal('0.01'):
                    direct_merchants.append({"name": item['journal_entry__description'], "balance": float(val)})

            if direct_merchants:
                sub_items_list.append({
                    "name": f"Directly under {child.name}",
                    "balance": sum(m['balance'] for m in direct_merchants),
                    "type": "subcategory",
                    "merchants": sorted(direct_merchants, key=lambda x: x['balance'], reverse=True)
                })

            sub_items_list = sorted(sub_items_list, key=lambda x: x['balance'], reverse=True)
        else:
            # No sub-accounts: flat merchant list (original behaviour)
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
            sub_items_list = sorted(sub_items_list, key=lambda x: x['balance'], reverse=True)

        line_items.append({
            "id": child.id,
            "name": child.name,
            "balance": float(display_bal),
            "sub_items": sub_items_list
        })

    # Step B: Calculate the Direct Root Remainder (Transactions posted directly to the root category)
    root_direct_bal = true_total_balance - child_sum
    display_root_direct = -root_direct_bal if flip_sign else root_direct_bal
    
    if abs(display_root_direct) > Decimal('0.01'):
        # Query banners directly mapped strictly to the root account ID
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

    # 3. Handle Merchant (Banner) breakdown for the Global View (The whole branch)
    all_descendants = root.get_descendants(include_self=True)
    all_merchants = Merchant.objects.filter(family=family, default_account__in=all_descendants)
    
    q_all = Q(journal_entry__family=family, account_id__in=all_descendants.values_list('id', flat=True))
    if is_cumulative:
        q_all &= Q(journal_entry__date__lte=dec_31)
    else:
        q_all &= Q(journal_entry__date__range=[jan_1, dec_31])
        
    merchant_sums = TransactionLine.objects.filter(q_all).values('journal_entry__description').annotate(total=Sum('amount'))
    
    merchant_items = []
    for item in merchant_sums:
        m_bal = item['total']
        m_display_bal = -m_bal if flip_sign else m_bal
        if abs(m_display_bal) > Decimal('0.01'):
            # Try to find a merchant with this name to get the ID
            m_obj = Merchant.objects.filter(family=family, name=item['journal_entry__description']).first()
            merchant_items.append({
                "id": m_obj.id if m_obj else 0, # Use 0 if no record exists
                "name": item['journal_entry__description'],
                "balance": float(m_display_bal)
            })

    # Final result
    return {
        "dimension_name": dimension_name,
        "total_amount": float(-true_total_balance if flip_sign else true_total_balance),
        "line_items": sorted(line_items, key=lambda x: x['balance'], reverse=True),
        "merchant_items": sorted(merchant_items, key=lambda x: abs(x['balance']), reverse=True)
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

from django.db.models import Sum, Q, Count
...
@router.get("/reports/dimension/{dimension_slug}/drill-down", response=DrillDownOut)
def get_dimension_drill_down(request, dimension_slug: str, period: str):
    """
    Returns a detailed drill-down for a dimension in a specific month (YYYY-MM).
    Includes category-level breakdown with historical averages and banner-grouped transactions.
    """
    user = request.auth
    family = user.family
    
    try:
        year, month = map(int, period.split('-'))
        start_date = date(year, month, 1)
        end_date = start_date + relativedelta(months=1) - relativedelta(days=1)
        
        # Period for historical average (Current Year)
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
    except (ValueError, TypeError):
        raise errors.HttpError(400, "Invalid period format. Use YYYY-MM.")

    root_map = {
        'revenue': 'Revenue',
        'expenses': 'Expenses',
        'assets': 'Assets',
        'liabilities': 'Liabilities',
        'equity': 'Equity'
    }
    
    if dimension_slug not in root_map:
        raise errors.HttpError(404, f"Dimension {dimension_slug} not drillable directly.")

    root_name = root_map[dimension_slug]
    root = get_object_or_404(Account, family=family, name=root_name, parent=None)
    is_cumulative = dimension_slug in ['assets', 'liabilities', 'equity']
    flip_sign = dimension_slug in ['revenue', 'liabilities', 'equity']

    # 1. Category Breakdown for this month with Historical Avg
    children = root.get_children()
    category_breakdown = []
    
    # Range for this month's breakdown
    q_month = Q(journal_entry__family=family)
    if is_cumulative:
        q_month &= Q(journal_entry__date__lte=end_date)
    else:
        q_month &= Q(journal_entry__date__range=[start_date, end_date])

    for child in children:
        child_ids = child.get_descendants(include_self=True).values_list('id', flat=True)
        
        # Month Balance
        bal = TransactionLine.objects.filter(q_month, account_id__in=child_ids).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        display_bal = -bal if flip_sign else bal
        
        # Historical Year Avg (normalized to monthly)
        q_year = Q(journal_entry__family=family, account_id__in=child_ids)
        if is_cumulative:
            # For cumulative, average is tricky, we'll use the avg of end-of-month snapshots if needed,
            # but for now let's use the year-total / 12 as a proxy for velocity.
            year_total = TransactionLine.objects.filter(q_year, journal_entry__date__range=[year_start, year_end]).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        else:
            year_total = TransactionLine.objects.filter(q_year, journal_entry__date__range=[year_start, year_end]).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        avg_bal = abs(float(year_total)) / 12
        
        if abs(display_bal) > 0.01 or avg_bal > 0.01:
            category_breakdown.append({
                "id": child.id,
                "name": child.name,
                "balance": float(display_bal),
                "average_monthly_balance": avg_bal
            })
    
    category_breakdown.sort(key=lambda x: abs(x['balance']), reverse=True)

    # 2. Grouped Banners (Merchants)
    # We aggregate by description and child category
    banner_qs = TransactionLine.objects.filter(
        journal_entry__family=family,
        account__in=root.get_descendants(include_self=True),
        journal_entry__date__range=[start_date, end_date]
    ).values('journal_entry__description', 'account__name').annotate(
        total=Sum('amount'),
        tx_count=Count('id')
    )

    banners = []
    for item in banner_qs:
        val = item['total']
        display_val = -val if flip_sign else val
        
        banners.append({
            "name": item['journal_entry__description'],
            "amount": float(display_val),
            "count": item['tx_count'],
            "category": item['account__name']
        })

    return {
        "dimension_name": root_name,
        "period": period,
        "category_breakdown": category_breakdown,
        "banners": sorted(banners, key=lambda x: abs(x['amount']), reverse=True)
    }

@router.get("/reports/dimension/{dimension_slug}/banner-transactions", response=List[BannerTransactionOut])
def get_banner_transactions(request, dimension_slug: str, period: str, banner: str):
    """
    Returns individual journal entries for a specific banner within a period.
    Each entry includes the source account (which financial product) and the routed-to account.
    """
    from banking.models import FinancialProduct

    user = request.auth
    family = user.family

    try:
        year, month = map(int, period.split('-'))
        start_date = date(year, month, 1)
        end_date = start_date + relativedelta(months=1) - relativedelta(days=1)
    except (ValueError, TypeError):
        raise errors.HttpError(400, "Invalid period format. Use YYYY-MM.")

    # Create a map to easily grab the institution_id
    fp_map = {
        fp.account_id: fp.institution_id
        for fp in FinancialProduct.objects.filter(family=family)
    }
    fp_account_ids = set(fp_map.keys())

    entries = JournalEntry.objects.filter(
        family=family,
        description=banner,
        date__range=[start_date, end_date]
    ).prefetch_related('lines__account', 'staged_transactions')

    results = []
    for entry in entries:
        lines = list(entry.lines.all())
        source_line = next((l for l in lines if l.account_id in fp_account_ids), None)
        category_line = next((l for l in lines if l.account_id not in fp_account_ids), None)
        
        # Fallback if self-routed (both legs are FP accounts, e.g. credit card payment)
        if not category_line and len(lines) >= 2:
            category_line = next((l for l in lines if l != source_line), lines[1])

        # Link back to statement if available
        staged_tx = entry.staged_transactions.first()
        statement_id = staged_tx.statement_import_id if staged_tx else None
        
        # Grab raw description and institution ID for rule creation
        raw_description = staged_tx.raw_description if staged_tx else entry.description
        institution_id = fp_map.get(source_line.account_id) if source_line else None

        results.append({
            'journal_entry_id': entry.id,
            'date': entry.date,
            'amount': abs(float(category_line.amount)) if category_line else abs(float(lines[0].amount)),
            'source_account': source_line.account.name if source_line else '—',
            'routed_to': category_line.account.name if category_line else '—',
            'routed_to_id': category_line.account_id if category_line else 0,
            'statement_id': statement_id,
            'raw_description': raw_description,
            'institution_id': institution_id,
        })

    return sorted(results, key=lambda x: x['date'], reverse=True)


@router.patch("/journal-entries/{entry_id}/reroute", response={200: BannerTransactionOut})
def reroute_journal_entry(request, entry_id: int, payload: RerouteIn):
    """
    Swaps the category leg of a journal entry to a different account.
    If merchant_id is provided, it updates the entry description to that merchant name 
    and sets the account to that merchant's default account.
    """
    from banking.models import FinancialProduct
    from django.db import transaction as db_transaction

    user = request.auth
    family = user.family

    entry = get_object_or_404(JournalEntry, id=entry_id, family=family)
    
    new_account = None
    new_description = None
    
    if payload.merchant_id:
        merchant = get_object_or_404(Merchant, id=payload.merchant_id, family=family)
        if not merchant.default_account:
            raise errors.HttpError(400, f"Merchant '{merchant.name}' does not have a default account associated.")
        new_account = merchant.default_account
        new_description = merchant.name
    elif payload.new_account_id:
        new_account = get_object_or_404(Account, id=payload.new_account_id, family=family)
    else:
        raise errors.HttpError(400, "Either new_account_id or merchant_id must be provided.")

    fp_map = {
        fp.account_id: fp.institution_id
        for fp in FinancialProduct.objects.filter(family=family)
    }
    fp_account_ids = set(fp_map.keys())

    lines = list(entry.lines.select_related('account').all())
    source_line = next((l for l in lines if l.account_id in fp_account_ids), None)
    category_line = next((l for l in lines if l.account_id not in fp_account_ids), None)

    if not category_line:
        # Fallback for self-routed transfers where both legs are FP accounts
        if len(lines) >= 2:
            category_line = next((l for l in lines if l != source_line), lines[1])
        else:
            raise errors.HttpError(400, "Could not identify the category leg of this journal entry.")

    # Resolve staged transaction early — needed inside the atomic block for gap 2.
    staged_tx = entry.staged_transactions.first()

    # Re-derive the correct amounts for both lines from first principles.
    # source_line.amount sign encodes the original transaction direction:
    #   positive  → source was the DEBIT leg  (inflow to asset / payment on liability)
    #   negative  → source was the CREDIT leg (outflow from asset / purchase on liability)
    # The category leg always sits on the opposite side, so we recompute both
    # amounts rather than blindly swapping just the account FK.  This ensures
    # the entry remains correct even when the new account crosses the
    # debit-normal / credit-normal boundary (e.g. expense → revenue).
    abs_amount = abs(source_line.amount)
    if source_line.amount > 0:          # source was debit
        new_source_amount   =  abs_amount
        new_category_amount = -abs_amount
    else:                               # source was credit
        new_source_amount   = -abs_amount
        new_category_amount =  abs_amount

    with db_transaction.atomic():
        source_line.amount = new_source_amount
        source_line.save(update_fields=['amount'])

        category_line.account = new_account
        category_line.amount  = new_category_amount
        category_line.save(update_fields=['account', 'amount'])

        if new_description:
            entry.description = new_description
            entry.save(update_fields=['description'])

        # Gap 2: persist the merchant link on the staged transaction so that
        # SyncMerchantHistoryService can cover this entry in the future.
        if staged_tx and payload.merchant_id:
            staged_tx.merchant = merchant
            staged_tx.save(update_fields=['merchant'])

    statement_id = staged_tx.statement_import_id if staged_tx else None
    
    # Grab raw description and institution ID for rule creation compatibility
    raw_description = staged_tx.raw_description if staged_tx else entry.description
    institution_id = fp_map.get(source_line.account_id) if source_line else None

    return {
        'journal_entry_id': entry.id,
        'date': entry.date,
        'amount': abs(float(category_line.amount)),
        'source_account': source_line.account.name if source_line else '—',
        'routed_to': new_account.name,
        'routed_to_id': new_account.id,
        'statement_id': statement_id,
        'raw_description': raw_description,
        'institution_id': institution_id,
    }


@router.get("/accounts/{account_id}/journal-entries", response=List[AccountTransactionOut])
def get_account_transactions(request, account_id: int, year: Optional[int] = None):
    """
    Returns all journal entries where any line touches this account or its descendants.
    Used to power the transaction review section on the account detail page.
    """
    from banking.models import FinancialProduct

    user = request.auth
    family = user.family
    account = get_object_or_404(Account, id=account_id, family=family)
    descendants = account.get_descendants(include_self=True)

    qs = JournalEntry.objects.filter(
        family=family,
        lines__account__in=descendants,
    )
    if year:
        qs = qs.filter(date__year=year)

    # Prefetch staged transactions to avoid N+1 queries
    entries = qs.distinct().prefetch_related('lines__account', 'staged_transactions').order_by('-date')[:500]

    fp_account_map = {
        fp.account_id: fp.institution_id
        for fp in FinancialProduct.objects.filter(family=family)
    }
    fp_account_ids = set(fp_account_map.keys())
    descendant_ids = set(descendants.values_list('id', flat=True))

    results = []
    for entry in entries:
        lines = list(entry.lines.all())
        source_line = next((l for l in lines if l.account_id in fp_account_ids), None)
        category_line = next((l for l in lines if l.account_id in descendant_ids), None)
        if not category_line:
            continue
        
        # Resolve statement_id if available
        st_tx = entry.staged_transactions.first()
        statement_id = st_tx.statement_import_id if st_tx else None

        results.append({
            'journal_entry_id': entry.id,
            'date': entry.date,
            'description': entry.description or '—',
            'amount': abs(float(category_line.amount)),
            'source_account': source_line.account.name if source_line else '—',
            'routed_to': category_line.account.name,
            'routed_to_id': category_line.account_id,
            'institution_id': fp_account_map.get(source_line.account_id) if source_line else None,
            'statement_id': statement_id,
        })

    return results


@router.get("/accounts-flat", response=List[FlatAccountOut])
def list_accounts_flat(request):
    """
    Returns all accounts for the family as a flat list with depth info,
    suitable for a searchable select/combobox.
    """
    user = request.auth
    accounts = Account.objects.filter(family=user.family).order_by('tree_id', 'lft')
    return [
        {'id': a.id, 'name': a.name, 'account_type': a.account_type, 'depth': a.level}
        for a in accounts
    ]


@router.get("/accounts/{account_id}", response=AccountDetailOut)
def get_account_detail(request, account_id: int, year: Optional[int] = None):
    """
    Returns full details for an account with CFA-grade analytical insights and monthly stacked breakdown.
    Supports cumulative (Stock) and period-isolated (Flow) calculations.
    """
    if year is None:
        year = date.today().year

    user = request.auth
    family = user.family
    account = get_object_or_404(Account, id=account_id, family=family)

    # Determine if this account requires cumulative (Stock) math
    is_cumulative = account.account_type in [Account.AccountType.ASSET, Account.AccountType.LIABILITY, Account.AccountType.EQUITY]

    # 1. Branch Data Context
    descendants = account.get_descendants(include_self=True)
    direct_children = account.get_children()

    if not is_cumulative:
        today = date.today()
        today_year = today.year

        descendant_ids = list(descendants.values_list('id', flat=True))
        direct_child_ids = {
            child.id: tuple(child.get_descendants(include_self=True).values_list('id', flat=True))
            for child in direct_children
        }
        account_to_child_id = {
            descendant_id: child_id
            for child_id, child_descendant_ids in direct_child_ids.items()
            for descendant_id in child_descendant_ids
        }

        history_start = min(year - 1, today_year - 5)
        history_end = max(year, today_year)

        descendant_rows = TransactionLine.objects.filter(
            journal_entry__family=family,
            account_id__in=descendant_ids,
            journal_entry__date__year__gte=history_start,
            journal_entry__date__year__lte=history_end,
        ).values('account_id', 'journal_entry__date__year', 'journal_entry__date__month').annotate(total=Sum('amount'))

        overall_year_totals = defaultdict(Decimal)
        overall_month_totals = defaultdict(Decimal)
        child_year_totals = {child.id: defaultdict(Decimal) for child in direct_children}
        child_month_totals = {child.id: defaultdict(Decimal) for child in direct_children}

        for row in descendant_rows:
            total = row['total'] or Decimal('0.00')
            row_year = row['journal_entry__date__year']
            row_month = row['journal_entry__date__month']
            account_id = row['account_id']

            overall_year_totals[row_year] += total
            overall_month_totals[(row_year, row_month)] += total

            child_id = account_to_child_id.get(account_id)
            if child_id is not None:
                child_year_totals[child_id][row_year] += total
                child_month_totals[child_id][(row_year, row_month)] += total

        def yearly_totals_for_ids(account_ids, target_years):
            if not account_ids:
                return {}

            rows = TransactionLine.objects.filter(
                journal_entry__family=family,
                account_id__in=account_ids,
                journal_entry__date__year__in=target_years,
            ).values('journal_entry__date__year').annotate(total=Sum('amount'))

            return {
                row['journal_entry__date__year']: abs(float(row['total'] or Decimal('0.00')))
                for row in rows
            }

        def cumulative_total_for_ids(account_ids, cutoff_year):
            if not account_ids:
                return 0.0

            total = TransactionLine.objects.filter(
                journal_entry__family=family,
                account_id__in=account_ids,
                journal_entry__date__lte=date(cutoff_year, 12, 31),
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            return abs(float(total))

        root_revenue = Account.objects.filter(name='Revenue', parent=None, family=family).first()
        revenue_descendant_ids = list(root_revenue.get_descendants(include_self=True).values_list('id', flat=True)) if root_revenue else []
        revenue_year_totals = yearly_totals_for_ids(revenue_descendant_ids, {year, year - 1})

        parent_account_ids = list(account.parent.get_descendants(include_self=True).values_list('id', flat=True)) if account.parent else descendant_ids
        parent_year_totals = yearly_totals_for_ids(parent_account_ids, {year})

        total_assets_root = Account.objects.filter(name='Assets', parent=None, family=family).first()
        total_assets = cumulative_total_for_ids(
            list(total_assets_root.get_descendants(include_self=True).values_list('id', flat=True)) if total_assets_root else [],
            year,
        )

        amt_current = abs(float(overall_year_totals.get(year, Decimal('0.00'))))
        amt_previous = abs(float(overall_year_totals.get(year - 1, Decimal('0.00'))))
        parent_amt = parent_year_totals.get(year, amt_current)

        children_list = []
        for child in direct_children:
            children_list.append({
                "id": child.id,
                "name": child.name,
                "account_type": child.account_type,
                "balance": abs(float(child_year_totals[child.id].get(year, Decimal('0.00')))),
            })
        children_list.sort(key=lambda x: x['balance'], reverse=True)

        direct_merchants_sums = TransactionLine.objects.filter(
            journal_entry__family=family,
            account=account,
            journal_entry__date__year=year
        ).values('journal_entry__description').annotate(total=Sum('amount'))

        direct_merchants = [
            {"id": 0, "name": item['journal_entry__description'], "balance": abs(float(item['total']))}
            for item in direct_merchants_sums if item['total']
        ]
        direct_merchants.sort(key=lambda x: x['balance'], reverse=True)

        monthly_breakdown = []
        for month_idx in range(1, 13):
            by_child = []
            month_total = 0.0

            for child in direct_children:
                child_amt = abs(float(child_month_totals[child.id].get((year, month_idx), Decimal('0.00'))))
                by_child.append({
                    "child_id": child.id,
                    "child_name": child.name,
                    "amount": child_amt
                })
                month_total += child_amt

            if not direct_children:
                month_total = abs(float(overall_month_totals.get((year, month_idx), Decimal('0.00'))))

            monthly_breakdown.append({
                "month": f"{year}-{month_idx:02d}",
                "total": month_total,
                "by_child": by_child
            })

        jan_1_today = date(today_year, 1, 1)
        days_elapsed = max((today - jan_1_today).days + 1, 1)
        annual_multiplier = 365.25 / days_elapsed

        logic_amt_current = amt_current * annual_multiplier if year == today_year else amt_current
        logic_amt_previous = amt_previous

        yoy_growth = (logic_amt_current - logic_amt_previous) / logic_amt_previous if logic_amt_previous > 0 else None
        revenue_growth = (revenue_year_totals.get(year, 0.0) - revenue_year_totals.get(year - 1, 0.0)) / revenue_year_totals.get(year - 1, 0.0) if revenue_year_totals.get(year - 1, 0.0) > 0 else 0
        drift = (yoy_growth - revenue_growth) if yoy_growth is not None else 0

        monthly_totals = [m['total'] for m in monthly_breakdown]
        volatility = float(np.std(monthly_totals)) if monthly_totals else 0.0

        top_driver_bal = children_list[0]['balance'] if children_list else amt_current
        concentration = (top_driver_bal / amt_current) if amt_current > 0 else 0.0

        health_tag = "stable"
        red_flag = None
        green_flag = None

        if account.account_type == 'EXPENSE' and drift > 0.05:
            health_tag = "drifting"
            red_flag = {"title": "Operational Drift", "detail": f"Category growing {drift*100:.1f}% faster than income."}
        elif concentration > 0.5:
            health_tag = "concentrated"
            red_flag = {"title": "Concentration Risk", "detail": f"Top driver accounts for {concentration*100:.0f}% of volume."}

        if yoy_growth is not None and yoy_growth < -0.1 and account.account_type == 'EXPENSE':
            green_flag = {"title": "Efficiency Gain", "detail": "Category spend reduced by >10% YoY."}

        historical_trends = []
        for y in range(today_year - 5, today_year + 1):
            y_total = abs(float(overall_year_totals.get(y, Decimal('0.00'))))
            y_income = revenue_year_totals.get(y, 0.0)

            realized = y_total
            estimated = 0.0

            if y == today_year and y_total > 0:
                projected_full = y_total * annual_multiplier
                estimated = projected_full - y_total
                display_total = projected_full
                monthly_avg = realized / (days_elapsed / (365.25 / 12))
            else:
                display_total = y_total
                monthly_avg = display_total / 12

            historical_trends.append({
                "year": y,
                "total": display_total,
                "realized_total": realized,
                "estimated_total": estimated,
                "monthly_avg": monthly_avg,
                "pct_of_income": round((display_total / y_income) * 100, 2) if y_income > 0 else 0.0,
            })

        total_valid = [t['total'] for t in historical_trends if t['total'] > 0]
        avg_yearly = sum(total_valid) / len(total_valid) if total_valid else 0.0

        return {
            "id": account.id,
            "name": account.name,
            "account_type": account.account_type,
            "parent_id": account.parent_id,
            "children": children_list,
            "direct_merchants": direct_merchants,
            "monthly_breakdown": monthly_breakdown,
            "insights": {
                "amount_current": amt_current,
                "amount_previous": amt_previous,
                "yoy_growth": yoy_growth,
                "share_of_parent": (amt_current / parent_amt) if parent_amt > 0 else 1.0,
                "share_of_total_inflow": (amt_current / revenue_year_totals.get(year, 0.0)) if revenue_year_totals.get(year, 0.0) > 0 else 0.0,
                "volatility_score": volatility,
                "concentration_top_1": concentration,
                "drift_spread": drift if account.account_type == 'EXPENSE' else None,
                "optimization_headroom": (top_driver_bal * 0.05),
                "burn_coverage_days": (total_assets / (amt_current / 365)) if amt_current > 0 else None,
                "health_tag": health_tag,
                "red_flag": red_flag,
                "green_flag": green_flag,
                "strategic_action": {
                    "action": f"Review {children_list[0]['name'] if children_list else 'drivers'} for 5% optimization." if health_tag == 'concentrated' else "Monitor for structural drift.",
                    "owner": "household",
                    "time_horizon": "30d"
                }
            },
            "historical_trends": historical_trends,
            "avg_yearly_total": avg_yearly,
            "avg_monthly_avg": avg_yearly / 12
        }
    
    # 2. Universal Sum Helper
    def get_sum(branch_qs, target_year, month=None, is_cumulative=False):
        if is_cumulative:
            # Stock Logic: Cumulative sum up to the end of the period
            if month:
                # Last day of month
                end_date = date(target_year, month, 1) + relativedelta(months=1) - relativedelta(days=1)
            else:
                end_date = date(target_year, 12, 31)
            q = Q(journal_entry__family=family, account__in=branch_qs, journal_entry__date__lte=end_date)
        else:
            # Flow Logic: Strictly the period
            q = Q(journal_entry__family=family, account__in=branch_qs, journal_entry__date__year=target_year)
            if month:
                q &= Q(journal_entry__date__month=month)
        
        val = TransactionLine.objects.filter(q).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        return abs(float(val))

    amt_current = get_sum(descendants, year, is_cumulative=is_cumulative)
    amt_previous = get_sum(descendants, year - 1, is_cumulative=is_cumulative)
    
    # 3. Denominators for Share calculations
    parent_amt = get_sum(account.parent.get_descendants(include_self=True) if account.parent else descendants, year, is_cumulative=is_cumulative)
    root_revenue = Account.objects.filter(name='Revenue', parent=None, family=family).first()
    total_revenue_curr = get_sum(root_revenue.get_descendants(include_self=True) if root_revenue else Account.objects.none(), year, is_cumulative=False)
    total_revenue_prev = get_sum(root_revenue.get_descendants(include_self=True) if root_revenue else Account.objects.none(), year - 1, is_cumulative=False)
    
    total_assets_ids = Account.objects.filter(name='Assets', parent=None, family=family).first()
    total_assets = get_sum(total_assets_ids.get_descendants(include_self=True) if total_assets_ids else Account.objects.none(), year, is_cumulative=True)

    # 4. Refactored Child List (with computed branch balances)
    children_list = []
    for child in direct_children:
        child_branch = child.get_descendants(include_self=True)
        children_list.append({
            "id": child.id,
            "name": child.name,
            "account_type": child.account_type,
            "balance": get_sum(child_branch, year, is_cumulative=is_cumulative)
        })
    children_list.sort(key=lambda x: x['balance'], reverse=True)

    # 5. Refactored Direct Merchants (ONLY transactions posted directly to this ID)
    # Merchant balances in this specific drill-down are still usually treated as flow-impact for the period
    # even for stock accounts, to see WHAT moved the needle this year.
    direct_merchants_sums = TransactionLine.objects.filter(
        journal_entry__family=family,
        account=account,
        journal_entry__date__year=year
    ).values('journal_entry__description').annotate(total=Sum('amount'))
    
    direct_merchants = [
        {"id": 0, "name": item['journal_entry__description'], "balance": abs(float(item['total']))}
        for item in direct_merchants_sums if item['total']
    ]
    direct_merchants.sort(key=lambda x: x['balance'], reverse=True)

    # 6. Monthly Stacked Breakdown (Always 12 months)
    monthly_breakdown = []
    for month_idx in range(1, 13):
        month_str = f"{year}-{month_idx:02d}"
        by_child = []
        month_total = 0.0
        
        for child in direct_children:
            child_amt = get_sum(child.get_descendants(include_self=True), year, month=month_idx, is_cumulative=is_cumulative)
            by_child.append({
                "child_id": child.id,
                "child_name": child.name,
                "amount": child_amt
            })
            # Note: For stock accounts, month_total is the aggregate snapshot, not sum of child snapshots
            # We'll re-calculate or sum depending on desired UI behavior. 
            # Usually, for stacked charts, sum of snapshots is the branch total at that time.
            month_total += child_amt
            
        if not direct_children:
            # If leaf node, month total is the node total at that time
            month_total = get_sum(descendants, year, month=month_idx, is_cumulative=is_cumulative)

        monthly_breakdown.append({
            "month": month_str,
            "total": month_total,
            "by_child": by_child
        })

    # 7. Math for CFA Insights
    today = date.today()
    today_year = today.year
    
    # Calculate days elapsed for current year annualization
    jan_1_today = date(today_year, 1, 1)
    days_elapsed = max((today - jan_1_today).days + 1, 1)
    annual_multiplier = 365.25 / days_elapsed

    revenue_descendants = root_revenue.get_descendants(include_self=True) if root_revenue else Account.objects.none()
    
    # logic_amt_current/previous used for the YoY stat
    logic_amt_current = amt_current
    logic_amt_previous = amt_previous
    if year == today_year and not is_cumulative:
        logic_amt_current = amt_current * annual_multiplier

    yoy_growth = (logic_amt_current - logic_amt_previous) / logic_amt_previous if logic_amt_previous > 0 else None
    revenue_growth = (total_revenue_curr - total_revenue_prev) / total_revenue_prev if total_revenue_prev > 0 else 0
    drift = (yoy_growth - revenue_growth) if yoy_growth is not None else 0
    
    # Volatility (Monthly variance)
    monthly_totals = [m['total'] for m in monthly_breakdown]
    volatility = float(np.std(monthly_totals)) if monthly_totals else 0.0
    
    # Concentration
    top_driver_bal = children_list[0]['balance'] if children_list else amt_current
    concentration = (top_driver_bal / amt_current) if amt_current > 0 else 0.0

    # CFA Flags & Tags
    health_tag = "stable"
    red_flag = None
    green_flag = None
    
    if account.account_type == 'EXPENSE' and drift > 0.05:
        health_tag = "drifting"
        red_flag = {"title": "Operational Drift", "detail": f"Category growing {drift*100:.1f}% faster than income."}
    elif concentration > 0.5:
        health_tag = "concentrated"
        red_flag = {"title": "Concentration Risk", "detail": f"Top driver accounts for {concentration*100:.0f}% of volume."}
    
    if yoy_growth is not None and yoy_growth < -0.1 and account.account_type == 'EXPENSE':
        green_flag = {"title": "Efficiency Gain", "detail": "Category spend reduced by >10% YoY."}

    # Historical trends — always anchored to today so the chart is a fixed map.
    # The selected `year` only controls the monthly detail; the map never shifts.
    historical_trends = []
    for y in range(today_year - 5, today_year + 1):
        y_total = get_sum(descendants, y, is_cumulative=is_cumulative)
        y_income = get_sum(revenue_descendants, y, is_cumulative=False)
        
        realized = y_total
        estimated = 0.0
        
        if y == today_year and not is_cumulative and y_total > 0:
            projected_full = y_total * annual_multiplier
            estimated = projected_full - y_total
            display_total = projected_full
        else:
            display_total = y_total

        historical_trends.append({
            "year": y,
            "total": display_total,
            "realized_total": realized,
            "estimated_total": estimated,
            "monthly_avg": (display_total / 12) if not (y == today_year and not is_cumulative) else (realized / (days_elapsed / (365.25/12))),
            "pct_of_income": round((display_total / y_income) * 100, 2) if y_income > 0 else 0.0,
        })
    
    # avg_yearly_total for reference lines
    total_valid = [t['total'] for t in historical_trends if t['total'] > 0]
    avg_yearly = sum(total_valid) / len(total_valid) if total_valid else 0.0

    return {
        "id": account.id,
        "name": account.name,
        "account_type": account.account_type,
        "parent_id": account.parent_id,
        "children": children_list,
        "direct_merchants": direct_merchants,
        "monthly_breakdown": monthly_breakdown,
        "insights": {
            "amount_current": amt_current,
            "amount_previous": amt_previous,
            "yoy_growth": yoy_growth,
            "share_of_parent": (amt_current / parent_amt) if parent_amt > 0 else 1.0,
            "share_of_total_inflow": (amt_current / total_revenue_curr) if total_revenue_curr > 0 else 0.0,
            "volatility_score": volatility,
            "concentration_top_1": concentration,
            "drift_spread": drift if account.account_type == 'EXPENSE' else None,
            "optimization_headroom": (top_driver_bal * 0.05),
            "burn_coverage_days": (total_assets / (amt_current / 365)) if amt_current > 0 else None,
            "health_tag": health_tag,
            "red_flag": red_flag,
            "green_flag": green_flag,
            "strategic_action": {
                "action": f"Review {children_list[0]['name'] if children_list else 'drivers'} for 5% optimization." if health_tag == 'concentrated' else "Monitor for structural drift.",
                "owner": "household",
                "time_horizon": "30d"
            }
        },
        "historical_trends": historical_trends,
        "avg_yearly_total": avg_yearly,
        "avg_monthly_avg": avg_yearly / 12
    }

@router.get("/dimension-evolution")
def get_dimension_evolution(
    request, 
    dimension: Literal['revenue', 'expenses', 'net-income', 'assets', 'liabilities', 'net-worth'],
    start_date: date, 
    end_date: date, 
    interval: Literal['bi-weekly', 'monthly'] = 'monthly'
):
    """
    Returns time-series data for any financial dimension with category-level breakdown.
    """
    user = request.auth
    family = user.family

    # Flow dimensions use period sums
    if dimension in ['revenue', 'expenses', 'net-income']:
        root_revenue = Account.objects.filter(family=family, name='Revenue', parent=None).first()
        root_expenses = Account.objects.filter(family=family, name='Expenses', parent=None).first()
        
        rev_ids = list(root_revenue.get_descendants(include_self=True).values_list('id', flat=True)) if root_revenue else []
        exp_ids = list(root_expenses.get_descendants(include_self=True).values_list('id', flat=True)) if root_expenses else []
        
        target_ids = []
        root = None
        if dimension == 'revenue':
            target_ids = rev_ids
            root = root_revenue
        elif dimension == 'expenses':
            target_ids = exp_ids
            root = root_expenses
        else: # net-income
            target_ids = rev_ids + exp_ids

        # Build account-to-category mapping for breakdown
        account_to_cat = {}
        if root and dimension != 'net-income':
            for child in root.get_children():
                d_ids = child.get_descendants(include_self=True).values_list('id', flat=True)
                for d_id in d_ids:
                    account_to_cat[d_id] = child.name

        queryset = TransactionLine.objects.filter(
            journal_entry__family=family,
            account_id__in=target_ids,
            journal_entry__date__range=[start_date, end_date]
        )

        trunc_func = TruncMonth('journal_entry__date') if interval == 'monthly' else TruncWeek('journal_entry__date')
        
        if dimension == 'net-income':
            results = queryset.annotate(period=trunc_func).values('period', 'account__account_type').annotate(total=Sum('amount')).order_by('period')
            period_map = {}
            for r in results:
                p = r['period']
                if p not in period_map: period_map[p] = 0.0
                val = float(r['total'])
                period_map[p] += -val
            
            final_results = [{"period": p, "amount": v} for p, v in period_map.items()]
            final_results.sort(key=lambda x: x['period'])
        else:
            results = queryset.annotate(period=trunc_func).values('period', 'account_id').annotate(total=Sum('amount')).order_by('period')
            period_map = {}
            for r in results:
                p = r['period']
                if p not in period_map:
                    period_map[p] = {"period": p, "amount": 0.0}
                
                val = float(r['total'])
                display_val = -val if dimension == 'revenue' else val
                period_map[p]["amount"] += display_val
                
                cat_name = account_to_cat.get(r['account_id'], f"Directly under {root.name}")
                period_map[p][cat_name] = period_map[p].get(cat_name, 0.0) + display_val
            
            final_results = list(period_map.values())
            final_results.sort(key=lambda x: x['period'])

        # Bi-weekly post-processing
        if interval == 'bi-weekly':
            bi_weekly = []
            for i in range(0, len(final_results), 2):
                item = final_results[i]
                # Merge two periods
                new_item = item.copy()
                if i + 1 < len(final_results):
                    next_item = final_results[i+1]
                    new_item["amount"] += next_item["amount"]
                    for k, v in next_item.items():
                        if k not in ["period", "amount"]:
                            new_item[k] = new_item.get(k, 0.0) + v
                
                new_item["period"] = new_item["period"].strftime("%Y-%m-%d")
                bi_weekly.append(new_item)
            return bi_weekly

        return [
            {**r, "period": r['period'].strftime("%Y-%m" if interval == 'monthly' else "%Y-%m-%d")}
            for r in final_results
        ]

    # Stock dimensions use cumulative ending balances
    else:
        root_assets = Account.objects.filter(family=family, name='Assets', parent=None).first()
        root_liabilities = Account.objects.filter(family=family, name='Liabilities', parent=None).first()
        
        root = None
        if dimension == 'assets': root = root_assets
        elif dimension == 'liabilities': root = root_liabilities
        else: root = None # net-worth handling below
        
        # Breakdown mapping for assets/liabilities
        account_to_cat = {}
        if root:
            for child in root.get_children():
                d_ids = child.get_descendants(include_self=True).values_list('id', flat=True)
                for d_id in d_ids:
                    account_to_cat[d_id] = child.name

        current_p = start_date.replace(day=1)
        results = []
        
        while current_p <= end_date:
            end_of_p = current_p + relativedelta(months=1) - relativedelta(days=1)
            
            period_data = {
                "period": current_p.strftime("%Y-%m"),
                "amount": 0.0
            }

            if dimension == 'net-worth':
                total = TransactionLine.objects.filter(
                    journal_entry__family=family,
                    account__account_type__in=[Account.AccountType.ASSET, Account.AccountType.LIABILITY],
                    journal_entry__date__lte=end_of_p
                ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
                period_data["amount"] = float(total)
            else:
                # Optimized breakdown query for stock dimensions
                branch_ids = list(root.get_descendants(include_self=True).values_list('id', flat=True)) if root else []
                qs = TransactionLine.objects.filter(
                    journal_entry__family=family,
                    account_id__in=branch_ids,
                    journal_entry__date__lte=end_of_p
                ).values('account_id').annotate(total=Sum('amount'))
                
                total_acc = 0.0
                for item in qs:
                    val = float(item['total'])
                    display_val = -val if dimension == 'liabilities' else val
                    total_acc += display_val
                    cat_name = account_to_cat.get(item['account_id'], f"Directly under {root.name}")
                    period_data[cat_name] = period_data.get(cat_name, 0.0) + display_val
                
                period_data["amount"] = total_acc
            
            results.append(period_data)
            current_p += relativedelta(months=1) if interval == 'monthly' else relativedelta(weeks=2)

        return results

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

    root_expenses = Account.objects.filter(family=family, name='Expenses', parent=None).first()
    if not root_expenses: return []
    
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
            "id": cat.id,
            "category": cat.name,
            "amount": float(total)
        })

    # Sort by highest spend
    results.sort(key=lambda x: x['amount'], reverse=True)
    return results


@router.get("/reports/expenses/monthly-overview", response=MonthlyExpenseReportOut)
def get_monthly_expense_overview(request, selected_month: Optional[str] = None):
    """
    Returns a full monthly expense series for each top-level expense category,
    plus the latest month comparison against all-time monthly average.
    """
    family = request.auth.family

    root_expenses = Account.objects.filter(
        family=family,
        name='Expenses',
        parent=None,
        account_type=Account.AccountType.EXPENSE,
    ).first()

    if not root_expenses:
        return {
            "latest_month": None,
            "totals_series": [],
            "categories": [],
            "top_transactions": [],
        }

    top_categories = list(root_expenses.get_children().order_by('name'))
    if not top_categories:
        return {
            "latest_month": None,
            "totals_series": [],
            "categories": [],
            "top_transactions": [],
        }

    category_to_descendants = {
        cat.id: list(cat.get_descendants(include_self=True).values_list('id', flat=True))
        for cat in top_categories
    }
    account_to_category = {
        account_id: cat_id
        for cat_id, descendant_ids in category_to_descendants.items()
        for account_id in descendant_ids
    }

    all_expense_ids = list(account_to_category.keys())
    if not all_expense_ids:
        return {
            "latest_month": None,
            "totals_series": [],
            "categories": [],
            "top_transactions": [],
        }

    raw_rows = list(
        TransactionLine.objects.filter(
            journal_entry__family=family,
            account_id__in=all_expense_ids,
        )
        .annotate(month=TruncMonth('journal_entry__date'))
        .values('month', 'account_id')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    if not raw_rows:
        return {
            "latest_month": None,
            "totals_series": [],
            "categories": [
                {
                    "category_id": cat.id,
                    "category_name": cat.name,
                    "all_time_average": 0.0,
                    "current_month_amount": 0.0,
                    "delta_vs_average": 0.0,
                    "delta_vs_average_pct": None,
                    "series": [],
                }
                for cat in top_categories
            ],
            "top_transactions": [],
        }

    min_month = raw_rows[0]['month']
    max_month = raw_rows[-1]['month']

    all_months = []
    current_month = min_month
    while current_month <= max_month:
        all_months.append(current_month)
        current_month += relativedelta(months=1)

    # Fetch Revenue data and categories
    root_revenue = Account.objects.filter(
        family=family,
        name='Revenue',
        parent=None,
        account_type=Account.AccountType.REVENUE,
    ).first()
    top_revenue_categories = list(root_revenue.get_children().order_by('name')) if root_revenue else []
    
    rev_cat_to_descendants = {
        cat.id: list(cat.get_descendants(include_self=True).values_list('id', flat=True))
        for cat in top_revenue_categories
    }
    rev_account_to_cat = {
        acc_id: cat_id
        for cat_id, acc_ids in rev_cat_to_descendants.items()
        for acc_id in acc_ids
    }

    all_revenue_ids = list(root_revenue.get_descendants(include_self=True).values_list('id', flat=True)) if root_revenue else []
    revenue_rows = TransactionLine.objects.filter(
        journal_entry__family=family,
        account_id__in=all_revenue_ids,
    ).annotate(month=TruncMonth('journal_entry__date')).values('month', 'account_id').annotate(total=Sum('amount'))

    revenue_month_values = {month: Decimal('0.00') for month in all_months}
    rev_cat_month_values = {
        cat.id: {month: Decimal('0.00') for month in all_months}
        for cat in top_revenue_categories
    }

    for row in revenue_rows:
        if row['month'] in revenue_month_values:
            val = -(row['total'] or Decimal('0.00'))
            revenue_month_values[row['month']] += val
            cat_id = rev_account_to_cat.get(row['account_id'])
            if cat_id:
                rev_cat_month_values[cat_id][row['month']] += val

    category_month_values = {
        cat.id: {month: Decimal('0.00') for month in all_months}
        for cat in top_categories
    }

    for row in raw_rows:
        mapped_category_id = account_to_category.get(row['account_id'])
        if not mapped_category_id:
            continue
        category_month_values[mapped_category_id][row['month']] += row['total'] or Decimal('0.00')

    latest_month = all_months[-1]
    selected_month_key = selected_month or latest_month.strftime("%Y-%m")
    selected_month_start = next((month for month in all_months if month.strftime("%Y-%m") == selected_month_key), latest_month)
    categories_payload = []
    revenue_categories_payload = []
    totals_series = []
    summary_series = []

    for month in all_months:
        month_expenses = Decimal('0.00')
        for cat in top_categories:
            month_expenses += category_month_values[cat.id][month]
        
        month_revenue = revenue_month_values[month]
        month_savings = month_revenue - month_expenses

        totals_series.append({
            "month": month.strftime("%Y-%m"),
            "amount": float(month_expenses),
        })
        summary_series.append({
            "month": month.strftime("%Y-%m"),
            "revenue": float(month_revenue),
            "expenses": float(month_expenses),
            "savings": float(month_savings),
        })

    def build_cat_payload(cats, month_values_map):
        payload = []
        for cat in cats:
            month_map = month_values_map[cat.id]
            ordered_values = [month_map[month] for month in all_months]
            total_amount = sum(ordered_values, Decimal('0.00'))
            month_count = Decimal(len(all_months))
            all_time_avg = total_amount / month_count if month_count else Decimal('0.00')
            latest_amount = month_map[latest_month]
            delta = latest_amount - all_time_avg
            delta_pct = None
            if all_time_avg != Decimal('0.00'):
                delta_pct = float((delta / all_time_avg) * Decimal('100.00'))

            payload.append({
                "category_id": cat.id,
                "category_name": cat.name,
                "all_time_average": float(all_time_avg),
                "current_month_amount": float(latest_amount),
                "delta_vs_average": float(delta),
                "delta_vs_average_pct": delta_pct,
                "series": [
                    {
                        "month": month.strftime("%Y-%m"),
                        "amount": float(month_map[month]),
                    }
                    for month in all_months
                ],
            })
        payload.sort(key=lambda item: item['current_month_amount'], reverse=True)
        return payload

    categories_payload = build_cat_payload(top_categories, category_month_values)
    revenue_categories_payload = build_cat_payload(top_revenue_categories, rev_cat_month_values)

    avg_revenue = sum(revenue_month_values.values()) / len(all_months) if all_months else Decimal('0.00')
    avg_expenses = sum(s['expenses'] for s in summary_series) / len(all_months) if all_months else 0.0
    avg_savings = sum(s['savings'] for s in summary_series) / len(all_months) if all_months else 0.0

    # Build merchant stacked series: select top N merchants by total across the period,
    # then order them alphabetically and produce a per-month series for each.
    TOP_N_MERCHANTS = 10

    # Total per merchant (by description) across the whole period
    merchant_totals_qs = TransactionLine.objects.filter(
        journal_entry__family=family,
        account_id__in=all_expense_ids,
    ).values('journal_entry__description').annotate(total=Sum('amount'))
    merchant_totals = []
    for m in merchant_totals_qs:
        merchant_totals.append((m['journal_entry__description'], m['total'] or Decimal('0.00')))

    # Pick top N by absolute total
    merchant_totals_sorted = sorted(merchant_totals, key=lambda t: abs(t[1]), reverse=True)[:TOP_N_MERCHANTS]
    merchant_names = [t[0] for t in merchant_totals_sorted]

    # Order alphabetically as requested
    merchant_names_sorted = sorted(merchant_names, key=lambda n: n.lower())

    # Initialize merchant -> month map
    merchant_month_values = {name: {month: Decimal('0.00') for month in all_months} for name in merchant_names_sorted}

    merchant_month_rows = TransactionLine.objects.filter(
        journal_entry__family=family,
        account_id__in=all_expense_ids,
    ).annotate(month=TruncMonth('journal_entry__date')).values('month', 'journal_entry__description').annotate(total=Sum('amount')).order_by('month')

    for row in merchant_month_rows:
        desc = row['journal_entry__description']
        if desc in merchant_month_values:
            merchant_month_values[desc][row['month']] += row['total'] or Decimal('0.00')

    merchants_payload = []
    for name in merchant_names_sorted:
        m_obj = Merchant.objects.filter(family=family, name=name).first()
        merchants_payload.append({
            "id": m_obj.id if m_obj else 0,
            "name": name,
            "series": [
                {"month": month.strftime("%Y-%m"), "amount": float(merchant_month_values[name][month])}
                for month in all_months
            ],
        })

    latest_month_start = selected_month_start
    latest_month_end = latest_month_start + relativedelta(months=1) - relativedelta(days=1)
    latest_month_rows = list(
        TransactionLine.objects.filter(
            journal_entry__family=family,
            account_id__in=all_expense_ids,
            journal_entry__date__range=[latest_month_start, latest_month_end],
        )
        .values('journal_entry_id', 'journal_entry__description', 'journal_entry__date')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:5]
    )

    latest_entry_ids = [row['journal_entry_id'] for row in latest_month_rows]
    latest_entries = JournalEntry.objects.filter(
        family=family,
        id__in=latest_entry_ids,
    ).prefetch_related('lines__account', 'staged_transactions__merchant')
    latest_entry_map = {entry.id: entry for entry in latest_entries}

    top_transactions_payload = []
    for row in latest_month_rows:
        entry = latest_entry_map.get(row['journal_entry_id'])
        if not entry:
            continue

        expense_lines = [line for line in entry.lines.all() if line.account_id in all_expense_ids]
        primary_line = max(expense_lines, key=lambda line: abs(line.amount)) if expense_lines else None
        category_name = 'Uncategorized'
        category_id = 0
        if primary_line and primary_line.account_id in account_to_category:
            category_id = account_to_category[primary_line.account_id]
            category_name = next((cat.name for cat in top_categories if cat.id == category_id), category_name)

        staged_transactions = list(entry.staged_transactions.all())
        staged_tx = staged_transactions[0] if staged_transactions else None
        merchant_name = staged_tx.merchant.name if staged_tx and staged_tx.merchant else None

        top_transactions_payload.append({
            "journal_entry_id": entry.id,
            "date": entry.date,
            "description": staged_tx.raw_description if staged_tx and staged_tx.raw_description else entry.description,
            "amount": float(row['total'] or Decimal('0.00')),
            "category_id": category_id,
            "category_name": category_name,
            "merchant_name": merchant_name,
            "statement_id": staged_tx.statement_import_id if staged_tx else None,
            "staged_transaction_id": staged_tx.id if staged_tx else None,
        })

    return {
        "latest_month": latest_month.strftime("%Y-%m"),
        "latest_revenue": float(revenue_month_values[latest_month]),
        "latest_expenses": float(sum(category_month_values[cat.id][latest_month] for cat in top_categories)),
        "latest_savings": float(revenue_month_values[latest_month] - sum(category_month_values[cat.id][latest_month] for cat in top_categories)),
        "avg_revenue": float(avg_revenue),
        "avg_expenses": float(avg_expenses),
        "avg_savings": float(avg_savings),
        "totals_series": totals_series,
        "summary_series": summary_series,
        "categories": categories_payload,
        "revenue_categories": revenue_categories_payload,
        "merchants": merchants_payload,
        "top_transactions": top_transactions_payload,
    }


@router.get("/reports/expenses/monthly-overview/pdf")
def get_monthly_expense_overview_pdf(request, selected_month: Optional[str] = None):
    """Return the monthly expense report as a polished PDF document."""
    report_data = get_monthly_expense_overview(request, selected_month=selected_month)
    pdf_bytes = build_monthly_expense_report_pdf(report_data, selected_month=selected_month)

    month_label = selected_month or report_data.get("latest_month") or "latest"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="monthly-expense-report-{month_label}.pdf"'
    return response

@router.get("/annual-statements/history", response=AnnualHistoryOut)
def get_annual_statements_history(request):
    """
    Returns Income Statement + Balance Sheet key metrics for ALL available years.
    Used to power the Historical Overview panel on the Dashboard.
    """
    family = request.auth.family

    years_qs = JournalEntry.objects.filter(family=family).dates('date', 'year')
    available_years = sorted(set(y.year for y in years_qs))

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

    result = []
    for year in available_years:
        jan_1 = date(year, 1, 1)
        dec_31 = date(year, 12, 31)
        revenue = get_sum('Revenue', jan_1, dec_31)
        expenses = get_sum('Expenses', jan_1, dec_31)
        assets = get_cumulative_sum('Assets', dec_31)
        liabilities = get_cumulative_sum('Liabilities', dec_31)
        result.append({
            "year": year,
            "revenue": float(-revenue),
            "expenses": float(expenses),
            "net_income": float(-revenue - expenses),
            "assets": float(assets),
            "liabilities": float(-liabilities),
            "net_worth": float(assets) - abs(float(liabilities)),
        })

    return {"years": result}


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
            "net_worth": float(assets) - abs(float(liabilities)),
            "check": float(assets + liabilities + equity) # Should be zero
        }
    }

@router.get("/available-years")
def get_available_years(request):
    """
    Returns a list of years that have transaction data.
    Dynamically sources from the transaction dates in the database.
    """
    user = request.auth
    family = user.family

    # Get all years from JournalEntry table for this family
    years = JournalEntry.objects.filter(family=family).dates('date', 'year')
    available_years = sorted(set([year.year for year in years]), reverse=True)

    # If no data, return current year as default
    if not available_years:
        from datetime import date as date_class
        available_years = [date_class.today().year]

    return {"available_years": available_years}
