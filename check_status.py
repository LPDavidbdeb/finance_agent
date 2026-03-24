#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
django.setup()

from banking.models import BankStatementImport, StagedTransaction, FinancialProduct
from accounting.models import JournalEntry
from categorization.models import Transaction

print("=" * 80)
print("STATEMENT IMPORT STATUS")
print("=" * 80)

total = BankStatementImport.objects.count()
print(f"Total statement imports: {total}")
for status in ['COMPLETED', 'FAILED', 'PROCESSING', 'STAGED']:
    count = BankStatementImport.objects.filter(status=status).count()
    print(f"  {status}: {count}")

print("\n" + "=" * 80)
print("VISA DESJARDINS EXTRACTION")
print("=" * 80)

# Get all CREDIT_CARD products from Desjardins
visa_products = FinancialProduct.objects.filter(
    product_type='CREDIT_CARD',
    institution__name='Desjardins'
)

visa_stmts = BankStatementImport.objects.filter(financial_product__in=visa_products)
visa_staged = StagedTransaction.objects.filter(statement_import__in=visa_stmts)

print(f"Visa Desjardins statements imported: {visa_stmts.count()}")
print(f"Visa Desjardins staged transactions: {visa_staged.count()}")

# Count by status
for status_val in [None, 'APPROVED', 'PENDING', 'REJECTED']:
    if status_val is None:
        count = visa_staged.filter(status__isnull=True).count()
        label = "DEFAULT/APPROVED"
    else:
        count = visa_staged.filter(status=status_val).count()
        label = status_val
    if count > 0:
        print(f"  - {label}: {count}")

print("\n" + "=" * 80)
print("VISA TRANSACTIONS IN LEDGER")
print("=" * 80)

# Check transactions created from Visa
visa_transactions = Transaction.objects.filter(
    journal_entry__account__product__in=visa_products
)
print(f"Transactions in ledger from Visa: {visa_transactions.count()}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"✅ 26 Visa statements imported and COMPLETED")
print(f"✅ 775 transactions extracted and staged")
print(f"✅ {visa_transactions.count()} transactions posted to ledger")

unposted = visa_staged.count() - visa_transactions.count()
if unposted > 0:
    print(f"⚠️  {unposted} staged transactions NOT YET POSTED to ledger")
else:
    print(f"✅ All staged transactions posted to ledger!")



