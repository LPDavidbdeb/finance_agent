from django.core.management.base import BaseCommand
from django.db import transaction
from banking.models import StagedTransaction
from banking.services import approve_staged_transaction
from accounting.models import Account
from users.models import CustomUser


class Command(BaseCommand):
    help = "Retroactively auto-approves transactions by ensuring accounts exist for the family."

    def handle(self, *args, **options):
        ready_txs = StagedTransaction.objects.filter(
            status=StagedTransaction.Status.UNPROCESSED,
            predicted_account__isnull=False
        ).select_related('statement_import__financial_product__family', 'predicted_account')

        count = ready_txs.count()
        if count == 0:
            self.stdout.write("No transactions ready.")
            return

        success_count = 0
        error_count = 0

        for tx in ready_txs:
            family = tx.statement_import.financial_product.family
            user = CustomUser.objects.filter(family=family).first()

            # THE FIX: Ensure the predicted account exists for THIS family
            predicted_acc = tx.predicted_account

            # Check if this family already has this account name
            family_acc = Account.objects.filter(name=predicted_acc.name, family=family).first()

            if not family_acc:
                # Create a local copy of the global account for this family
                family_acc = Account.objects.create(
                    name=predicted_acc.name,
                    account_type=predicted_acc.account_type,
                    parent=predicted_acc.parent,  # Keep the same tree structure
                    family=family
                )

            try:
                # Run approval using the family-specific account
                approve_staged_transaction(
                    transaction_id=tx.id,
                    target_account_id=family_acc.id,
                    user=user
                )
                success_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error on tx {tx.id}: {str(e)}"))
                error_count += 1

        self.stdout.write(self.style.SUCCESS(f"Processed: {success_count} | Failed: {error_count}"))