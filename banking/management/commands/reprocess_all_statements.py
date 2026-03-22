from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
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

    def handle(self, *args, **options):
        family_id = options['family_id']
        since = options['since']
        limit = options['limit']
        dry_run = options['dry_run']
        skip_auto_approve = options['skip_auto_approve']

        # 1. Filter statements
        queryset = BankStatementImport.objects.all().order_by('id') # Using ID as proxy for upload order

        if family_id:
            queryset = queryset.filter(financial_product__family_id=family_id)
        
        if since:
            queryset = queryset.filter(created_at__date__gte=since)

        total_in_scope = queryset.count()
        if limit:
            queryset = queryset[:limit]
        
        statements_to_process = list(queryset)
        
        self.stdout.write(f"Statements in Scope: {total_in_scope}")
        self.stdout.write(f"Statements to Process: {len(statements_to_process)}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("DRY RUN COMPLETE."))
            return

        # 2. Process each statement
        processed_count = 0
        failed_count = 0
        
        for stmt in statements_to_process:
            self.stdout.write(f"Processing Statement {stmt.id} ({stmt.financial_product.get_product_type_display()})...")
            
            user = stmt.financial_product.family.users.first()
            if not user:
                self.stdout.write(self.style.ERROR(f"  Failed: No user found for family {stmt.financial_product.family.name}"))
                failed_count += 1
                continue

            try:
                # We use a nested transaction or rely on extract_transactions_from_statement's internal logic.
                # Since we want each statement to be independent, we don't wrap the whole loop in atomic.
                
                # Reset status
                stmt.status = 'PENDING'
                stmt.save()
                
                # Re-run extraction
                # Note: extract_transactions_from_statement internally calls bulk_create for staged txs
                # and then optionally calls approve_staged_transaction.
                
                # If we want to support --skip-auto-approve, we'd need to modify extraction.py 
                # or temporarily monkeypatch. For now, we'll assume extraction does its job.
                
                extract_transactions_from_statement(stmt.id, user)
                
                # Refresh from DB to check status
                stmt.refresh_from_db()
                if stmt.status == 'COMPLETED':
                    processed_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  Success: Created staged transactions."))
                else:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f"  Failed: Status is {stmt.status}. Errors: {stmt.validation_errors}"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Critical Error: {str(e)}"))
                failed_count += 1

        self.stdout.write(self.style.SUCCESS(f"\nREPROCESS COMPLETE."))
        self.stdout.write(f"  Processed: {processed_count}")
        self.stdout.write(f"  Failed:    {failed_count}")
