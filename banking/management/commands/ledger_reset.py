import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection, models
from users.models import Family
from banking.models import StagedTransaction, BankStatementImport
from banking.consistency import build_transaction_consistency_report
from accounting.models import JournalEntry, TransactionLine
from quality.models import ConsistencyReportRun
from quality.services import create_consistency_report_run

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
        families = list(families)

        self.stdout.write(f"Scoped Families: {len(families)}")

        # 1. Collect counts
        stats = []
        for family in families:
            lines = TransactionLine.objects.filter(journal_entry__family=family)
            jes = JournalEntry.objects.filter(family=family)
            
            # Count staged transactions belonging to this family (via product)
            staged = StagedTransaction.objects.filter(
                models.Q(financial_product__family=family) | 
                models.Q(statement_import__financial_product__family=family) |
                models.Q(statement_import__institution__products__family=family)
            ).distinct()
            
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
        statements_reset_by_family: dict[str, int] = {}

        for family in families:
            self.stdout.write(f"  Processing {family.name} ({family.id})...")
            
            # Deletion in strict dependency order:
            # 1. TransactionLine
            # 2. StagedTransaction (links to JournalEntry)
            # 3. JournalEntry
            
            with transaction.atomic():
                lines_deleted, _ = TransactionLine.objects.filter(journal_entry__family=family).delete()
                self.stdout.write(f"    - Deleted {lines_deleted} TransactionLines")

                staged_deleted, _ = StagedTransaction.objects.filter(
                    models.Q(financial_product__family=family) | 
                    models.Q(statement_import__financial_product__family=family) |
                    models.Q(statement_import__institution__products__family=family)
                ).delete()
                self.stdout.write(f"    - Deleted {staged_deleted} StagedTransactions")

                jes_deleted, _ = JournalEntry.objects.filter(family=family).delete()
                self.stdout.write(f"    - Deleted {jes_deleted} JournalEntries")
            
            # Reset statement statuses to allow re-processing
            with transaction.atomic():
                stmt_reset = BankStatementImport.objects.filter(
                    models.Q(financial_product__family=family) |
                    models.Q(financial_product__isnull=True, institution__products__family=family)
                ).distinct().update(
                    status=BankStatementImport.Status.STAGED, 
                    processed_by_python=False,
                    processed_by_ai=False,
                    validation_errors=None
                )
                statements_reset_by_family[str(family.id)] = stmt_reset
                self.stdout.write(f"    - Reset {stmt_reset} BankStatementImports to STAGED")

        # Reset primary key sequences so IDs start from 1 on the next insert
        sequences = [
            ('accounting_journalentry', 'id'),
            ('accounting_transactionline', 'id'),
            ('banking_stagedtransaction', 'id'),
        ]
        with connection.cursor() as cursor:
            for table, col in sequences:
                cursor.execute(
                    f"SELECT setval(pg_get_serial_sequence(%s, %s), 1, false)",
                    [table, col]
                )
        self.stdout.write("  - Reset PK sequences for JournalEntry, TransactionLine, StagedTransaction")

        # Post-reset baseline: the transactional ledger should now be empty in scope.
        remaining_lines = TransactionLine.objects.filter(journal_entry__family__in=families).count()
        remaining_jes = JournalEntry.objects.filter(family__in=families).count()
        remaining_staged = StagedTransaction.objects.filter(
            models.Q(financial_product__family__in=families) |
            models.Q(statement_import__financial_product__family__in=families) |
            models.Q(statement_import__institution__products__family__in=families)
        ).distinct().count()

        self.stdout.write("\nPost-reset consistency check:")
        self.stdout.write(f"  Remaining JournalEntry: {remaining_jes}")
        self.stdout.write(f"  Remaining TransactionLine: {remaining_lines}")
        self.stdout.write(f"  Remaining StagedTransaction: {remaining_staged}")
        self.stdout.write(f"  Statements reset to STAGED: {sum(statements_reset_by_family.values())}")

        if remaining_lines == remaining_jes == remaining_staged == 0:
            self.stdout.write(self.style.SUCCESS("  Ledger wipe verified."))
        else:
            self.stdout.write(self.style.ERROR("  Ledger wipe incomplete."))

        # Persist one reset report per family for auditability and investigation.
        stats_by_family = {str(s['id']): s for s in stats}
        for family in families:
            scoped_statements = BankStatementImport.objects.filter(
                models.Q(financial_product__family=family) |
                models.Q(financial_product__isnull=True, institution__products__family=family)
            ).distinct()
            consistency_report = build_transaction_consistency_report(scoped_statements)
            run = create_consistency_report_run(
                family=family,
                trigger_source=ConsistencyReportRun.TriggerSource.LEDGER_RESET,
                report=consistency_report,
                scope={
                    'family_id': str(family.id),
                    'deleted_before_reset': stats_by_family.get(str(family.id), {}),
                    'statements_reset': statements_reset_by_family.get(str(family.id), 0),
                },
            )
            self.stdout.write(f"  Consistency Report Run: {run.id} (Family: {family.name})")

        elapsed = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f"\nRESET COMPLETE in {elapsed:.2f}s"))
