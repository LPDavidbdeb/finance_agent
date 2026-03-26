#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
django.setup()

from banking.models import BankStatementImport, StagedTransaction, FinancialProduct
from accounting.models import JournalEntry, TransactionLine

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
for status_val in ['RECONCILED', 'PENDING_REVIEW', 'UNPROCESSED']:
    count = visa_staged.filter(status=status_val).count()
    print(f"  - {status_val}: {count}")

print("\n" + "=" * 80)
print("VISA TRANSACTIONS IN LEDGER")
print("=" * 80)

# Check transaction lines created from Visa
visa_transaction_lines = TransactionLine.objects.filter(
    journal_entry__staged_transactions__statement_import__financial_product__in=visa_products
).distinct()
print(f"Transaction lines in ledger from Visa: {visa_transaction_lines.count()}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
if total == 0:
    print("Empty instance: No data found.")
else:
    print(f"✅ {visa_stmts.filter(status='COMPLETED').count()} Visa statements imported and COMPLETED")
    print(f"✅ {visa_staged.count()} transactions extracted and staged")
    print(f"✅ {visa_transaction_lines.count()} lines posted to ledger")



