from django.core.management.base import BaseCommand
from django.db.models import Sum, Count
from accounting.models import JournalEntry, TransactionLine
from banking.models import StagedTransaction
from decimal import Decimal
import sys

class Command(BaseCommand):
    help = "Performs integrity checks on the Ledger and Staged Transactions."

    def add_arguments(self, parser):
        parser.add_argument('--family-id', type=str, help='Scope verification to a specific family UUID.')

    def handle(self, *args, **options):
        family_id = options['family_id']
        
        jes = JournalEntry.objects.all()
        if family_id:
            jes = jes.filter(family_id=family_id)

        self.stdout.write(f"Verifying {jes.count()} Journal Entries...")
        
        errors = []

        # 1. Sum(TransactionLine.amount) == 0 per JournalEntry
        for je in jes:
            total = TransactionLine.objects.filter(journal_entry=je).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
            if abs(total) > Decimal('0.001'):
                errors.append(f"JE {je.id} ({je.date}): Sum is {total} (Expected 0)")

        # 2. No RECONCILED staged tx without linked journal_entry
        reconciled_without_je = StagedTransaction.objects.filter(
            status=StagedTransaction.Status.RECONCILED,
            journal_entry__isnull=True
        )
        if family_id:
            reconciled_without_je = reconciled_without_je.filter(statement_import__financial_product__family_id=family_id)
        
        if reconciled_without_je.exists():
            errors.append(f"Found {reconciled_without_je.count()} RECONCILED StagedTransactions without a JournalEntry.")

        # 3. No RECONCILED staged tx with zero amount linked to non-zero JE
        # (Sanity check for orphaned mappings)
        
        # Output Results
        if not errors:
            self.stdout.write(self.style.SUCCESS("\nINTEGRITY CHECK PASSED!"))
            self.stdout.write(f"  All {jes.count()} Journal Entries sum to zero.")
            self.stdout.write(f"  All Reconciled transactions have valid Ledger anchors.")
        else:
            self.stdout.write(self.style.ERROR(f"\nINTEGRITY CHECK FAILED: {len(errors)} violations found."))
            for err in errors[:20]: # Print first 20
                self.stdout.write(f"  - {err}")
            
            if len(errors) > 20:
                self.stdout.write(f"  ... and {len(errors)-20} more.")
            
            sys.exit(1)
