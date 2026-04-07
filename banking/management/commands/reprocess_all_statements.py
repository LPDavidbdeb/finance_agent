from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from users.models import Family
from banking.models import BankStatementImport, StagedTransaction
from banking.extraction import extract_transactions_from_statement
import logging

class Command(BaseCommand):
    help = "Reprocesses all BankStatementImport records to recreate StagedTransactions and Ledger entries."

    def add_arguments(self, parser):
        parser.add_argument('--family-id', type=str, help='Scope to a specific family UUID.')
        parser.add_argument('--since', type=str, help='Process statements uploaded since YYYY-MM-DD.')
        parser.add_argument('--limit', type=int, help='Limit the number of statements to process.')
        parser.add_argument('--dry-run', action='store_true', help='Report scope without executing.')
        parser.add_argument('--skip-auto-approve', action='store_true', help='Disable automatic reconciliation during extraction.')
        parser.add_argument(
            '--tangerine',
            action='store_true',
            default=False,
            help=(
                'Reprocess only Tangerine statements. For each statement, clears '
                'financial_product before extraction to force the multi-product '
                'consolidated path (TangerineExtractor).'
            ),
        )

    def handle(self, *args, **options):
        family_id = options['family_id']
        since = options['since']
        limit = options['limit']
        dry_run = options['dry_run']
        skip_auto_approve = options['skip_auto_approve']
        tangerine_mode = options['tangerine']

        # 1. Filter statements
        queryset = BankStatementImport.objects.all().order_by('id')

        if tangerine_mode:
            # Match statements uploaded via either path:
            #   - consolidated: institution FK set to Tangerine
            #   - legacy: financial_product FK points to a Tangerine product
            #   - orphaned: a previous partial run cleared financial_product but
            #     never set institution — catch these by filename
            queryset = queryset.filter(
                Q(institution__name__icontains='Tangerine') |
                Q(financial_product__institution__name__icontains='Tangerine') |
                Q(file__icontains='tangerine', institution__isnull=True, financial_product__isnull=True)
            ).distinct()

        if family_id:
            queryset = queryset.filter(financial_product__family_id=family_id)

        if since:
            queryset = queryset.filter(upload_date__date__gte=since)

        total_in_scope = queryset.count()
        if limit:
            queryset = queryset[:limit]

        statements_to_process = list(queryset)

        self.stdout.write(f"Statements in Scope: {total_in_scope}")
        self.stdout.write(f"Statements to Process: {len(statements_to_process)}")
        if tangerine_mode:
            self.stdout.write(
                self.style.WARNING(
                    "Tangerine mode: financial_product will be cleared on each statement "
                    "before extraction to use the consolidated multi-product path.\n"
                )
            )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("DRY RUN COMPLETE."))
            return

        # 2. Process each statement
        processed_count = 0
        failed_count = 0

        for stmt in statements_to_process:
            # Resolve user before potentially clearing financial_product
            try:
                if stmt.financial_product:
                    user = stmt.financial_product.family.users.first()
                    label = stmt.financial_product.get_product_type_display()
                else:
                    # Consolidated or orphaned path — resolve user via family
                    family = Family.objects.filter(id=family_id).first() if family_id else Family.objects.first()
                    user = family.users.first() if family else None
                    label = stmt.institution.name if stmt.institution else f"stmt {stmt.id}"
            except Exception:
                user = None
                label = f"stmt {stmt.id}"

            self.stdout.write(f"Processing Statement {stmt.id} ({label})...")

            if not user:
                self.stdout.write(self.style.ERROR(f"  Failed: No user found for statement {stmt.id}"))
                failed_count += 1
                continue

            try:
                if tangerine_mode:
                    # Backfill institution before clearing product so the
                    # extraction engine can still resolve the institution path.
                    if stmt.institution is None:
                        if stmt.financial_product is not None:
                            stmt.institution = stmt.financial_product.institution
                        else:
                            # Orphaned statement: look up institution by name
                            from banking.models import FinancialInstitution
                            stmt.institution = FinancialInstitution.objects.filter(
                                name__icontains='Tangerine'
                            ).first()
                    if stmt.financial_product is not None:
                        stmt.financial_product = None
                    stmt.save(update_fields=['institution', 'financial_product'])

                # Reset status so extraction runs cleanly
                stmt.status = BankStatementImport.Status.STAGED
                stmt.save(update_fields=['status'])

                extract_transactions_from_statement(stmt.id, user)

                stmt.refresh_from_db()
                if stmt.status == BankStatementImport.Status.COMPLETED:
                    tx_count = StagedTransaction.objects.filter(statement_import=stmt).count()
                    processed_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  OK: {tx_count} transaction(s)."))
                else:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f"  Failed: Status={stmt.status}  Errors: {stmt.validation_errors}"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Critical Error: {str(e)}"))
                failed_count += 1

        self.stdout.write(self.style.SUCCESS(f"\nREPROCESS COMPLETE."))
        self.stdout.write(f"  Processed: {processed_count}")
        self.stdout.write(f"  Failed:    {failed_count}")
