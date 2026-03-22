from django.core.management.base import BaseCommand
from django.db import transaction
from banking.models import FinancialProduct, StagedTransaction
from accounting.models import JournalEntry, TransactionLine

class Command(BaseCommand):
    help = "Repairs historical liability transactions by inverting the signs of all related ledger lines."

    def handle(self, *args, **options):
        # 1. Find all FinancialProduct records where product_type is CREDIT_CARD or LOAN.
        liability_products = FinancialProduct.objects.filter(
            product_type__in=[
                FinancialProduct.ProductType.CREDIT_CARD,
                FinancialProduct.ProductType.LOAN
            ]
        )

        # 2. Find all JournalEntry records linked to StagedTransactions from these products.
        # Use distinct to avoid processing the same JE multiple times if referenced by multiple lines
        jes_to_fix = JournalEntry.objects.filter(
            staged_transactions__statement_import__financial_product__in=liability_products
        ).distinct()

        total_jes = jes_to_fix.count()
        corrected_count = 0

        self.stdout.write(f"Found {total_jes} Journal Entries to repair...")

        with transaction.atomic():
            for je in jes_to_fix:
                # 3. Find its two TransactionLines.
                lines = je.lines.all()
                
                # 4. Multiply the amount of both TransactionLines by -1.
                for line in lines:
                    line.amount = line.amount * -1
                    line.save()
                
                corrected_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Successfully corrected {corrected_count} Journal Entries!")
        )
