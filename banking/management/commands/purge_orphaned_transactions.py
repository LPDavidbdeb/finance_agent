from django.core.management.base import BaseCommand
from banking.models import StagedTransaction


class Command(BaseCommand):
    help = (
        "Purge orphaned StagedTransaction rows: set clean_description and predicted_account to NULL "
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

        # Target: rows with merchant_id IS NULL (orphaned)
        orphaned_qs = StagedTransaction.objects.filter(merchant__isnull=True)

        total_orphaned = orphaned_qs.count()
        to_purge = orphaned_qs.exclude(clean_description__isnull=True).exclude(clean_description='')
        purge_count = to_purge.count()

        self.stdout.write(self.style.SUCCESS("Orphaned Transaction Purge"))
        self.stdout.write(f"dry_run: {dry_run}")
        self.stdout.write(f"total_orphaned_rows (merchant_id is NULL): {total_orphaned}")
        self.stdout.write(f"rows_to_purge (clean_description set): {purge_count}")

        if not dry_run and purge_count > 0:
            # Set both clean_description and predicted_account to NULL for orphaned rows
            updated = to_purge.update(clean_description=None, predicted_account_id=None)
            self.stdout.write(
                self.style.SUCCESS(f"\n✓ Successfully purged {updated} orphaned rows.")
                + f"\n  clean_description set to NULL\n  predicted_account_id set to NULL"
            )
        elif dry_run:
            self.stdout.write(f"\nDry-run: Would purge {purge_count} rows if executed without --dry-run")
        else:
            self.stdout.write("\nNo orphaned rows to purge.")

