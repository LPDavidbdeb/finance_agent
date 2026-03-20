from django.core.management.base import BaseCommand
from django.db import transaction
from categorization.models import Merchant
from accounting.models import TransactionLine, Account

class Command(BaseCommand):
    help = "Syncs historical TransactionLine records to match current Merchant default accounts."

    def handle(self, *args, **options):
        # 1. Fetch all Merchant records that have a default_account assigned.
        merchants = Merchant.objects.filter(default_account__isnull=False)
        total_updated = 0

        with transaction.atomic():
            for merchant in merchants:
                # 2. Query & Update:
                # We only want to move the categorization side of the double-entry (Revenue/Expense),
                # NEVER the 'ASSET' or 'LIABILITY' bank side.
                lines = TransactionLine.objects.filter(
                    journal_entry__description=merchant.name,
                    account__family=merchant.family,
                    account__account_type__in=[Account.AccountType.REVENUE, Account.AccountType.EXPENSE]
                ).exclude(account_id=merchant.default_account_id)

                count = lines.update(account=merchant.default_account)
                total_updated += count

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully synced {total_updated} historical ledger lines to match current Merchant rules!"
            )
        )
