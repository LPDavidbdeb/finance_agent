from typing import Optional
from decimal import Decimal
from django.db.models import Q, Value, CharField, Case, When, IntegerField, F
from django.db.models.functions import Lower, Length
from django.db import transaction
from .models import TransactionMappingRule, Merchant
from banking.models import StagedTransaction
from accounting.models import Account, TransactionLine


def find_matching_rule(
    raw_description: str,
    institution_id: int,
    family_id: int,
    transaction_amount: Decimal = None,
) -> Optional[TransactionMappingRule]:
    if not raw_description:
        return None

    description = raw_description.strip().lower()
    if not description:
        return None

    amount_filter = Q()
    if transaction_amount is not None:
        abs_amount = abs(Decimal(str(transaction_amount)))
        amount_filter = (
            (Q(min_amount__isnull=True) | Q(min_amount__lte=abs_amount))
            & (Q(max_amount__isnull=True) | Q(max_amount__gte=abs_amount))
        )

    # We want to find rules where search_text is a substring of description.
    # We prioritize rules for the specific institution, then fall back to global (null) rules.
    # We also strictly filter by the family of the merchant.
    # Length-based matching: use .annotate(search_len=Length('search_text')).order_by('-search_len')
    
    # Check for specific institution first
    institution_match = (
        TransactionMappingRule.objects.filter(
            institution_id=institution_id,
            merchant__family_id=family_id
        )
        .filter(amount_filter)
        .select_related('merchant', 'merchant__default_account')
        .annotate(
            desc=Value(description, output_field=CharField()),
            search_len=Length('search_text'),
            has_amount_bounds=Case(
                When(Q(min_amount__isnull=False) | Q(max_amount__isnull=False), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )
        .filter(desc__icontains=F('search_text'))
        .order_by('-search_len', '-has_amount_bounds', '-search_text') # Prefer longer and then bounded matches
        .first()
    )
    if institution_match:
        return institution_match

    # Fallback to global rules for this family
    return (
        TransactionMappingRule.objects.filter(
            institution__isnull=True,
            merchant__family_id=family_id
        )
        .filter(amount_filter)
        .select_related('merchant', 'merchant__default_account')
        .annotate(
            desc=Value(description, output_field=CharField()),
            search_len=Length('search_text'),
            has_amount_bounds=Case(
                When(Q(min_amount__isnull=False) | Q(max_amount__isnull=False), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )
        .filter(desc__icontains=F('search_text'))
        .order_by('-search_len', '-has_amount_bounds', '-search_text') # Prefer longer and then bounded matches
        .first()
    )

class SyncMerchantHistoryService:
    @staticmethod
    @transaction.atomic
    def sync(merchant: Merchant, update_reconciled: bool = False):
        """
        Synchronizes historical transactions to match the merchant's current default category.
        Durable Anchoring: Joins via merchant_id Foreign Key.
        """
        if not merchant.default_account:
            return 0
            
        new_account = merchant.default_account
        
        # 1. Update all StagedTransactions linked to this merchant ID
        txs = StagedTransaction.objects.filter(merchant=merchant)
        txs.update(predicted_account=new_account)
        
        updated_count = 0
        
        if update_reconciled:
            # 2. Update JournalEntry lines for RECONCILED transactions
            reconciled_txs = txs.filter(status='RECONCILED', journal_entry__isnull=False).select_related('journal_entry')
            
            for tx in reconciled_txs:
                # Durable Anchoring: We search for lines in the JE that belong to the family 
                # and are NOT bank accounts (REVENUE/EXPENSE)
                lines = tx.journal_entry.lines.all()
                for line in lines:
                    # We check if it's a category line (not linked to a financial product)
                    if not hasattr(line.account, 'financial_product'):
                        if line.account_id != new_account.id:
                            line.account = new_account
                            line.save()
                            updated_count += 1
                        break # Only one category line per staged tx entry
        
        return updated_count

def update_merchant_category(merchant_id: int, new_account_id: int, update_history: bool = False):
    """
    Updates a merchant's default account and optionally retrofits historical transactions.
    """
    merchant = Merchant.objects.get(id=merchant_id)
    new_account = Account.objects.get(id=new_account_id)
    
    merchant.default_account = new_account
    merchant.save()
    
    if update_history:
        SyncMerchantHistoryService.sync(merchant, update_reconciled=True)
    
    return True
