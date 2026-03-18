from ninja import Router
from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja_jwt.authentication import JWTAuth
from typing import List

from .schemas import RuleCreateAndApplyIn
from .models import TransactionMappingRule
from banking.models import StagedTransaction
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
    
    # 1. Ensure target account exists and belongs to the family (multi-tenant safety)
    target_account = get_object_or_404(Account, id=payload.target_account_id, family=user.family)
    
    # 2. Create and save the new TransactionMappingRule
    rule = TransactionMappingRule.objects.create(
        search_text=payload.search_text,
        merchant_name=payload.merchant_name,
        target_account=target_account,
        institution_id=payload.institution_id
    )
    
    # 3. Query UNPROCESSED transactions for the current family
    queryset = StagedTransaction.objects.filter(
        statement_import__financial_product__family=user.family,
        status=StagedTransaction.Status.UNPROCESSED
    )
    
    # 4. Optional institution filtering
    if payload.institution_id:
        queryset = queryset.filter(statement_import__financial_product__institution_id=payload.institution_id)
    
    # 5. Filter transactions by the new rule's search_text (case-insensitive)
    matching_transactions = queryset.filter(raw_description__icontains=payload.search_text)
    
    # 6. Apply the new rule's metadata to matches
    to_update = []
    for tx in matching_transactions:
        tx.clean_description = payload.merchant_name
        tx.predicted_account = target_account
        to_update.append(tx)
        
    if to_update:
        StagedTransaction.objects.bulk_update(to_update, ['clean_description', 'predicted_account'])
        
    return {
        "success": True, 
        "updated_count": len(to_update),
        "rule_id": rule.id
    }
