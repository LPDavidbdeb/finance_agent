from typing import Optional
from decimal import Decimal
import unicodedata
from django.db.models import Q, Value, CharField, Case, When, IntegerField, F
from django.db.models.functions import Length, Trim
from django.db import transaction
from .models import TransactionMappingRule, Merchant
from banking.models import StagedTransaction
from accounting.models import Account, TransactionLine
import re
import unicodedata

def normalize_text(text: str) -> str:
    """Standardize dashes, strip accents, and flatten all whitespace."""
    if not text:
        return ""
    
    # 1. Normalize unicode and drop accents (e.g., É -> E)
    # Using NFKD to decompose characters and then ignoring non-ASCII characters
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    
    # 2. Standardize dashes
    text = text.replace('–', '-').replace('—', '-')
    
    # 3. Flatten any sequence of whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip().lower()



def find_matching_rule(
    raw_description: str,
    institution_id: int,
    family_id: int,
    transaction_amount: Decimal = None,
) -> Optional[TransactionMappingRule]:
    """
    Finds the first matching rule for a given transaction description.
    Ensures both the incoming string and the database rules are normalized for comparison.
    Priority: Institution-specific rules first, then global rules. Within each, longest match first.
    """
    if not raw_description:
        return None

    # 1. Normalize the incoming raw string from the PDF
    clean_raw_desc = normalize_text(raw_description)
    if not clean_raw_desc:
        return None

    abs_amount = abs(Decimal(str(transaction_amount))) if transaction_amount is not None else None

    def get_match(rules_queryset):
        # Prioritize by length of search text and presence of amount bounds
        rules = rules_queryset.annotate(
            search_len=Length('search_text'),
            has_amount_bounds=Case(
                When(Q(min_amount__isnull=False) | Q(max_amount__isnull=False), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        ).order_by('-has_amount_bounds', '-search_len', '-search_text')

        for rule in rules:
            if not rule.search_text:
                continue
            
            # DB search_text is already normalized via save(), but we lower() for safety
            if rule.search_text.lower() in clean_raw_desc:
                # Verify amount bounds if present
                if abs_amount is not None:
                    if rule.min_amount is not None and abs_amount < rule.min_amount:
                        continue
                    if rule.max_amount is not None and abs_amount > rule.max_amount:
                        continue
                return rule
        return None

    # 2. Try institution-specific rules first
    institution_rules = TransactionMappingRule.objects.filter(
        institution_id=institution_id,
        merchant__family_id=family_id
    ).select_related('merchant', 'merchant__default_account')
    
    match = get_match(institution_rules)
    if match:
        return match

    # 3. Fallback to global rules
    global_rules = TransactionMappingRule.objects.filter(
        institution__isnull=True,
        merchant__family_id=family_id
    ).select_related('merchant', 'merchant__default_account')
    
    return get_match(global_rules)

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
                je = tx.journal_entry
                # Update JE description to reflect the merchant name
                if je.description != merchant.name:
                    je.description = merchant.name
                    je.save(update_fields=['description'])
                # Durable Anchoring: We search for lines in the JE that belong to the family
                # and are NOT bank accounts (REVENUE/EXPENSE)
                lines = je.lines.all()
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
