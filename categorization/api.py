from ninja import Router, errors
from django.db import transaction, models
from django.db.models import Sum, Min
from django.db.models.functions import Abs
from django.shortcuts import get_object_or_404
from ninja_jwt.authentication import JWTAuth
from typing import List
from datetime import date

from .schemas import RuleCreateAndApplyIn, MerchantOut, MerchantUpdateIn, MerchantDetailOut, MerchantMergeIn, MerchantStatsOut
from .models import TransactionMappingRule, Merchant
from .services import find_matching_rule, update_merchant_category
from banking.models import StagedTransaction
from banking.services import approve_staged_transaction
from accounting.models import Account

router = Router(auth=JWTAuth())

@router.post("/create-and-apply")
@transaction.atomic
def create_and_apply_mapping_rule(request, payload: RuleCreateAndApplyIn):
    """
    Creates a new mapping rule and immediately applies it to all UNPROCESSED 
    transactions matching the search criteria.
    """
    user = request.auth
    
    # 1. Normalize merchant name for lookup
    merchant_name = payload.merchant_name.strip().upper()
    
    # 2. Get or create the Merchant (using case-insensitive logic or just matching the normalized name)
    merchant = Merchant.objects.filter(family=user.family, name=merchant_name).first()
    
    if not merchant:
        # Determine target account if provided
        target_account = None
        if payload.target_account_id:
            target_account = get_object_or_404(Account, id=payload.target_account_id, family=user.family)
            
        merchant = Merchant.objects.create(
            family=user.family,
            name=merchant_name,
            default_account=target_account,
            is_unique_provider=payload.is_unique_provider
        )
    
    # 3. Create the TransactionMappingRule
    clean_search_text = payload.search_text.strip()
    rule = TransactionMappingRule.objects.create(
        merchant=merchant,
        search_text=clean_search_text,
        institution_id=payload.institution_id,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount
    )
    
    # 4. Query UNPROCESSED transactions for the current family
    queryset = StagedTransaction.objects.filter(
        statement_import__financial_product__family=user.family,
        status=StagedTransaction.Status.UNPROCESSED
    )
    
    # 5. Optional institution filtering
    if payload.institution_id:
        queryset = queryset.filter(statement_import__financial_product__institution_id=payload.institution_id)
    
    # 6. Filter transactions by the new rule's search_text (case-insensitive) for performance
    candidate_transactions = queryset.filter(raw_description__icontains=clean_search_text)

    # 7. Apply and Auto-Approve using the canonical matching engine
    updated_count = 0
    can_auto_approve = bool(merchant.is_unique_provider and merchant.default_account)
    family_id = user.family.id
    
    for tx in candidate_transactions:
        # Verify that the canonical engine actually selects the NEW rule for this transaction
        # (This handles amount bounds and prioritization vs existing rules)
        matched_rule = find_matching_rule(
            tx.raw_description, 
            tx.statement_import.financial_product.institution_id,
            family_id,
            transaction_amount=tx.amount
        )
        
        if not matched_rule or matched_rule.id != rule.id:
            continue

        tx.merchant = merchant

        if can_auto_approve:
            target_account = merchant.default_account
            
            # CRITICAL: Resolve family-specific account if the default is global (NULL family)
            if target_account.family_id != user.family_id:
                resolved_account = Account.objects.filter(name=target_account.name, family=user.family).first()
                if not resolved_account:
                    resolved_account = Account.objects.create(
                        name=target_account.name,
                        account_type=target_account.account_type,
                        family=user.family,
                        parent=Account.objects.filter(name=target_account.parent.name, family=user.family).first() if target_account.parent else None
                    )
                target_account = resolved_account

            tx.predicted_account = target_account
            tx.save()
            try:
                approve_staged_transaction(
                    transaction_id=tx.id,
                    target_account_id=target_account.id,
                    user=user
                )
                updated_count += 1
            except Exception as e:
                import logging
                logging.error(f"Auto-approve failed for tx {tx.id} during rule creation: {e}")
                continue
        else:
            # Leave as UNPROCESSED, clear predicted if not unique
            tx.predicted_account = merchant.default_account if merchant.is_unique_provider else None
            tx.save()
            updated_count += 1 # We still "updated" it with metadata
        
    return {
        "success": True, 
        "updated_count": updated_count,
        "rule_id": rule.id,
        "auto_approved": can_auto_approve
    }

@router.get("/merchants", response=List[MerchantOut])
def list_merchants(request):
    """
    Returns a list of all Merchant records for the authenticated user's family.
    """
    user = request.auth
    merchants = Merchant.objects.filter(family=user.family).select_related('default_account').order_by('name')
    
    # Manually map to include account details for the schema
    result = []
    for m in merchants:
        result.append({
            "id": m.id,
            "name": m.name,
            "is_unique_provider": m.is_unique_provider,
            "default_account_id": m.default_account.id if m.default_account else None,
            "default_account_name": m.default_account.name if m.default_account else None,
        })
    return result

@router.post("/merchants/merge")
@transaction.atomic
def merge_merchants_endpoint(request, payload: MerchantMergeIn):
    """
    Merges source merchants into a target merchant. 
    Transfers rules and updates historical descriptions.
    """
    user = request.auth
    target_merchant = get_object_or_404(Merchant, id=payload.target_id, family=user.family)
    source_merchants = Merchant.objects.filter(id__in=payload.source_ids, family=user.family)
    
    if source_merchants.count() != len(payload.source_ids):
        raise errors.HttpError(404, "One or more source merchants not found.")
        
    source_names = list(source_merchants.values_list('name', flat=True))
    
    # 1. Transfer Rules
    TransactionMappingRule.objects.filter(merchant_id__in=payload.source_ids).update(merchant=target_merchant)
    
    # 2. Historical Cleanup (StagedTransactions)
    StagedTransaction.objects.filter(merchant_id__in=payload.source_ids).update(merchant=target_merchant)
    
    # 3. Delete sources
    source_merchants.delete()
    
    return {"success": True, "merged_count": len(source_names)}

@router.patch("/merchants/{merchant_id}")
@transaction.atomic
def update_merchant(request, merchant_id: int, payload: MerchantUpdateIn):
    """
    Updates a specific merchant.
    """
    user = request.auth
    merchant = get_object_or_404(Merchant, id=merchant_id, family=user.family)
    
    if payload.name:
        merchant.name = payload.name.strip().upper()
        merchant.save()
        
    if payload.is_unique_provider is not None:
        merchant.is_unique_provider = payload.is_unique_provider
        merchant.save()

    if payload.default_account_id is not None:
        # Use service for complex account update + historical retrofitting
        update_merchant_category(
            merchant_id=merchant.id, 
            new_account_id=payload.default_account_id, 
            update_history=payload.update_history
        )
        
    return {"success": True}

@router.get("/merchants/{merchant_id}/stats", response=MerchantStatsOut)
def get_merchant_stats(request, merchant_id: int):
    """
    Calculates spending statistics and daily activity for a specific merchant.
    """
    user = request.auth
    merchant = get_object_or_404(Merchant, id=merchant_id, family=user.family)
    
    # Base queryset for reconciled transactions
    qs = StagedTransaction.objects.filter(
        merchant=merchant,
        status='RECONCILED',
        statement_import__financial_product__family=user.family
    )
    
    # 1. Total Amount (Absolute sum of expenses/revenues)
    total_amount = qs.aggregate(total=Sum(Abs('amount')))['total'] or 0.0
    
    # 2. Historical Monthly Average
    historical_monthly_avg = 0.0
    earliest_date = qs.aggregate(min_date=Min('bank_date'))['min_date']
    if earliest_date:
        today = date.today()
        # Calculate month difference
        months_diff = (today.year - earliest_date.year) * 12 + (today.month - earliest_date.month)
        months_diff = max(1, months_diff)
        historical_monthly_avg = float(total_amount) / months_diff
        
    # 3. Current Year Monthly Average
    current_year = date.today().year
    current_month_num = date.today().month
    current_year_total = qs.filter(bank_date__year=current_year).aggregate(total=Sum(Abs('amount')))['total'] or 0.0
    current_year_monthly_avg = float(current_year_total) / current_month_num
    
    # 4. Daily Activity
    # Group by bank_date and sum absolute amounts
    daily_qs = qs.values('bank_date').annotate(total=Sum(Abs('amount'))).order_by('bank_date')
    daily_activity = [
        {"date": item['bank_date'].strftime("%Y-%m-%d"), "amount": float(item['total'])}
        for item in daily_qs
    ]
    
    return {
        "total_amount": float(total_amount),
        "historical_monthly_avg": float(historical_monthly_avg),
        "current_year_monthly_avg": float(current_year_monthly_avg),
        "daily_activity": daily_activity
    }

@router.get("/merchants/{merchant_id}", response=MerchantDetailOut)
def get_merchant_detail(request, merchant_id: int):
    """
    Returns full details for a merchant, including its mapping rules.
    """
    user = request.auth
    merchant = get_object_or_404(
        Merchant.objects.select_related('default_account').prefetch_related('mapping_rules__institution'), 
        id=merchant_id, 
        family=user.family
    )
    return merchant
