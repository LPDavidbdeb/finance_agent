from django.core.management.base import BaseCommand
from django.db import transaction
from banking.models import StagedTransaction
from accounting.models import Account, TransactionLine

class Command(BaseCommand):
    help = "Fixes historically inverted double-entry lines for Credit Card (Liability) purchases."

    def handle(self, *args, **options):
        # 1. Identify transactions that were potentially inverted:
        # Reconciled CC purchases (amount > 0)
        staged_txs = StagedTransaction.objects.filter(
            status=StagedTransaction.Status.RECONCILED,
            statement_import__financial_product__account__account_type=Account.AccountType.LIABILITY,
            amount__gt=0,
            journal_entry__isnull=False
        ).select_related('journal_entry', 'statement_import__financial_product__account')

        total_fixed = 0
        
        with transaction.atomic():
            for tx in staged_txs:
                je = tx.journal_entry
                lines = list(je.lines.all())
                
                if len(lines) != 2:
                    continue
                
                cc_account = tx.statement_import.financial_product.account
                
                # Find the CC line and the Category line
                cc_line = next((l for l in lines if l.account_id == cc_account.id), None)
                cat_line = next((l for l in lines if l.account_id != cc_account.id), None)
                
                if not cc_line or not cat_line:
                    continue
                
                # If CC line is positive (Debit), it's inverted for a purchase
                if cc_line.amount > 0:
                    # Swap the accounts while keeping the amounts (or swap the signs)
                    # Correct state: Expense is Debit (+), CC is Credit (-)
                    
                    cc_line.amount = -abs(tx.amount)
                    cat_line.amount = abs(tx.amount)
                    
                    cc_line.save()
                    cat_line.save()
                    total_fixed += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully fixed {total_fixed} inverted credit card transaction entries!"))
