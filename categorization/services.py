from typing import Optional
from django.db.models import Q, Value, CharField
from django.db.models.functions import Lower
from django.db import transaction
from .models import TransactionMappingRule, Merchant
from banking.models import StagedTransaction
from accounting.models import Account, TransactionLine

def find_matching_rule(raw_description: str, institution_id: int) -> Optional[TransactionMappingRule]:
    if not raw_description:
        return None

    description = raw_description.strip().lower()
    if not description:
        return None

    # We want to find rules where search_text is a substring of description.
    # We prioritize rules for the specific institution, then fall back to global (null) rules.
    # We use order_by('-institution_id') because specific IDs are > 0 and NULL is last/first depending on DB,
    # but more reliably we can just filter and combine.
    
    # Check for specific institution first
    institution_match = (
        TransactionMappingRule.objects.filter(
            institution_id=institution_id,
        )
        .select_related('merchant', 'merchant__default_account')
        .annotate(desc=Value(description, output_field=CharField()))
        .filter(desc__icontains=Lower('search_text'))
        .order_by('-search_text') # Prefer longer matches
        .first()
    )
    if institution_match:
        return institution_match

    # Fallback to global rules
    return (
        TransactionMappingRule.objects.filter(institution__isnull=True)
        .select_related('merchant', 'merchant__default_account')
        .annotate(desc=Value(description, output_field=CharField()))
        .filter(desc__icontains=Lower('search_text'))
        .order_by('-search_text') # Prefer longer matches
        .first()
    )

def update_merchant_category(merchant_id: int, new_account_id: int, update_history: bool = False):
    """
    Updates a merchant's default account and optionally retrofits historical transactions.
    """
    merchant = Merchant.objects.get(id=merchant_id)
    new_account = Account.objects.get(id=new_account_id)
    
    old_account_id = merchant.default_account_id
    merchant.default_account = new_account
    merchant.save()
    
    if update_history:
        # 1. Update all StagedTransactions categorized by this merchant name
        # We use clean_description as the anchor for "categorized by this merchant"
        txs = StagedTransaction.objects.filter(clean_description=merchant.name)
        txs.update(predicted_account=new_account)
        
        # 2. Update JournalEntry lines for RECONCILED transactions
        # We need to find the specific TransactionLine that corresponds to the category
        # (the one that doesn't belong to a financial product)
        reconciled_txs = txs.filter(status='RECONCILED', journal_entry__isnull=False).select_related('journal_entry')
        
        for tx in reconciled_txs:
            # Locate the line that points to the category. 
            # If we know the old_account_id, we can be precise. 
            # If not (e.g. it was null), we look for the non-bank line.
            lines = tx.journal_entry.lines.all()
            for line in lines:
                is_category_line = False
                if old_account_id and line.account_id == old_account_id:
                    is_category_line = True
                elif not hasattr(line.account, 'financial_product'):
                    is_category_line = True
                
                if is_category_line:
                    line.account = new_account
                    line.save()
                    break # Usually only one category line per staged tx entry
    
    return True
