from categorization.models import Merchant, TransactionMappingRule
from banking.models import StagedTransaction
from accounting.models import Account
from categorization.services import SyncMerchantHistoryService
from users.models import Family
import logging

def split_merchant():
    fam = Family.objects.get(name='709rueBeaudoin')
    old_merchant = Merchant.objects.get(id=285) # BENEVA
    auto_acc = Account.objects.get(id=2256) # Passenger vehicle insurance premiums

    # 1. Create new merchant
    new_merchant, created = Merchant.objects.get_or_create(
        name='BENEVA Car insurer',
        family=fam,
        defaults={'default_account': auto_acc, 'is_unique_provider': False}
    )

    if not created:
        new_merchant.default_account = auto_acc
        new_merchant.save()

    # 2. Reassign Rule
    rule = TransactionMappingRule.objects.get(id=482)
    rule.merchant = new_merchant
    rule.save()

    # 3. Re-route StagedTransactions mapped to old_merchant that match this rule
    # The rule is 'paiement / beneva' with amount between 123 and 125 (rule bounds are absolute)
    txns = StagedTransaction.objects.filter(
        merchant=old_merchant,
        raw_description__icontains='paiement / beneva'
    )
    
    count = txns.count()
    txns.update(merchant=new_merchant, predicted_account=auto_acc)

    # 4. Sync history to update Reconciled JournalEntries
    updated_lines = SyncMerchantHistoryService.sync(new_merchant, update_reconciled=True)

    print(f"Created new merchant: {new_merchant.name} (ID: {new_merchant.id})")
    print(f"Reassigned rule '{rule.search_text}' to {new_merchant.name}")
    print(f"Re-routed {count} staged transactions.")
    print(f"Updated {updated_lines} historical journal entries.")

if __name__ == '__main__':
    split_merchant()
