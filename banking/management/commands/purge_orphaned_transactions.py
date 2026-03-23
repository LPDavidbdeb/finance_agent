from django.core.management.base import BaseCommand
from banking.models import StagedTransaction


class Command(BaseCommand):
    help = (
        "Purge orphaned StagedTransaction rows: set predicted_account to NULL "
        "for all rows where merchant_id is NULL. This restores them to unprocessed raw transactions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show count of rows to be purged without writing changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Target: rows with merchant_id IS NULL (orphaned) that still have a predicted account
        to_purge = StagedTransaction.objects.filter(merchant__isnull=True, predicted_account__isnull=False)
        purge_count = to_purge.count()

        self.stdout.write(self.style.SUCCESS("Orphaned Transaction Purge"))
        self.stdout.write(f"dry_run: {dry_run}")
        self.stdout.write(f"rows_to_purge (merchant_id is NULL but predicted_account set): {purge_count}")

        if not dry_run and purge_count > 0:
            # Set predicted_account to NULL for orphaned rows
            updated = to_purge.update(predicted_account_id=None)
            self.stdout.write(
                self.style.SUCCESS(f"\n✓ Successfully purged {updated} orphaned rows.")
                + f"\n  predicted_account_id set to NULL"
            )
        elif dry_run:
            self.stdout.write(f"\nDry-run: Would purge {purge_count} rows if executed without --dry-run")
        else:
            self.stdout.write("\nNo orphaned rows to purge.")
