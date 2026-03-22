import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from users.models import Family
from banking.models import StagedTransaction, BankStatementImport
from accounting.models import JournalEntry, TransactionLine

class Command(BaseCommand):
    help = "Safely resets derived transactional layers (TransactionLine, JournalEntry, StagedTransaction)."

    def add_arguments(self, parser):
        parser.add_argument('--family-id', type=str, help='Scope reset to a specific family UUID.')
        parser.add_argument('--dry-run', action='store_true', help='Report counts without deleting.')
        parser.add_argument('--confirm', action='store_true', help='Execute the destructive deletion.')
        parser.add_argument('--batch-size', type=int, default=1000, help='Deletion batch size.')

    def handle(self, *args, **options):
        family_id = options['family_id']
        dry_run = options['dry_run']
        confirm = options['confirm']
        batch_size = options['batch_size']

        if not dry_run and not confirm:
            raise CommandError("Safety Check: You must provide either --dry-run or --confirm.")
        
        if dry_run and confirm:
            raise CommandError("Safety Check: Cannot provide both --dry-run and --confirm.")

        # Resolve family scope
        if family_id:
            try:
                families = Family.objects.filter(id=family_id)
                if not families.exists():
                    raise CommandError(f"Family with ID {family_id} not found.")
            except Exception as e:
                raise CommandError(f"Invalid family ID format: {e}")
        else:
            families = Family.objects.all()

        self.stdout.write(f"Scoped Families: {families.count()}")
        
        # 1. Collect counts
        stats = []
        for family in families:
            lines = TransactionLine.objects.filter(journal_entry__family=family)
            jes = JournalEntry.objects.filter(family=family)
            staged = StagedTransaction.objects.filter(statement_import__financial_product__family=family)
            
            stats.append({
                'name': family.name,
                'id': family.id,
                'lines': lines.count(),
                'jes': jes.count(),
                'staged': staged.count()
            })

        # Summary output
        total_lines = sum(s['lines'] for s in stats)
        total_jes = sum(s['jes'] for s in stats)
        total_staged = sum(s['staged'] for s in stats)

        self.stdout.write("\nSummary of records to be deleted:")
        self.stdout.write(f"  TransactionLine:  {total_lines}")
        self.stdout.write(f"  JournalEntry:     {total_jes}")
        self.stdout.write(f"  StagedTransaction: {total_staged}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\nDRY RUN COMPLETE. No data was mutated."))
            return

        # 2. Destructive execution
        start_time = time.time()
        self.stdout.write(self.style.WARNING("\nDESTRUCTIVE RESET STARTED..."))

        for family in families:
            self.stdout.write(f"  Processing {family.name} ({family.id})...")
            
            # Deletion in strict dependency order
            # TransactionLine -> JournalEntry -> StagedTransaction
            
            # TransactionLine
            with transaction.atomic():
                lines_deleted, _ = TransactionLine.objects.filter(journal_entry__family=family).delete()
                self.stdout.write(f"    - Deleted {lines_deleted} TransactionLines")

            # JournalEntry
            with transaction.atomic():
                jes_deleted, _ = JournalEntry.objects.filter(family=family).delete()
                self.stdout.write(f"    - Deleted {jes_deleted} JournalEntries")

            # StagedTransaction
            with transaction.atomic():
                staged_deleted, _ = StagedTransaction.objects.filter(statement_import__financial_product__family=family).delete()
                self.stdout.write(f"    - Deleted {staged_deleted} StagedTransactions")
            
            # Reset statement statuses to allow re-processing
            with transaction.atomic():
                stmt_reset = BankStatementImport.objects.filter(financial_product__family=family).update(status='PENDING', validation_errors=None)
                self.stdout.write(f"    - Reset {stmt_reset} BankStatementImports to PENDING")

        elapsed = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f"\nRESET COMPLETE in {elapsed:.2f}s"))
