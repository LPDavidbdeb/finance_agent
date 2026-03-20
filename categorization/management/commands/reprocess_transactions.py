from django.core.management.base import BaseCommand
from banking.models import StagedTransaction
from categorization.models import Merchant


class Command(BaseCommand):
    help = (
        "Backfill merchant and predicted_account for staged transactions where predicted_account is NULL, "
        "using strict merchant integrity rules."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute and print counts without writing updates.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        targets = (
            StagedTransaction.objects.filter(predicted_account__isnull=True)
            .exclude(clean_description__isnull=True)
            .exclude(clean_description="")
            .select_related("merchant")
        )

        total_target_rows = targets.count()
        merchant_fk_backfilled = 0
        eligible_for_predicted_backfill = 0
        predicted_updated_rows = 0
        no_merchant_match = 0
        merchant_not_unique_provider = 0
        merchant_unique_but_default_account_null = 0

        for tx in targets.iterator(chunk_size=2000):
            normalized_clean = ""  # clean_description removed
            if not normalized_clean:
                no_merchant_match += 1
                continue

            merchant = Merchant.objects.filter(name__iexact=normalized_clean).order_by("id").first()
            if not merchant:
                no_merchant_match += 1
                continue

            changed_fields = []
            if tx.merchant_id != merchant.id:
                tx.merchant_id = merchant.id
                changed_fields.append("merchant")
                merchant_fk_backfilled += 1

            if merchant.is_unique_provider:
                if merchant.default_account_id:
                    eligible_for_predicted_backfill += 1
                    tx.predicted_account_id = merchant.default_account_id
                    changed_fields.append("predicted_account")
                    predicted_updated_rows += 1
                else:
                    merchant_unique_but_default_account_null += 1
            else:
                merchant_not_unique_provider += 1

            if not dry_run and changed_fields:
                tx.save(update_fields=changed_fields)

        residual_unmatched_rows = total_target_rows - predicted_updated_rows

        self.stdout.write(self.style.SUCCESS("Backfill diagnostics"))
        self.stdout.write(f"dry_run: {dry_run}")
        self.stdout.write(f"target_rows(predicted_account is NULL, clean_description set): {total_target_rows}")
        self.stdout.write(f"merchant_fk_backfilled: {merchant_fk_backfilled}")
        self.stdout.write(
            f"eligible_for_predicted_backfill(unique provider + default account): {eligible_for_predicted_backfill}"
        )
        self.stdout.write(f"predicted_updated_rows: {predicted_updated_rows}")
        self.stdout.write(f"residual_unmatched_rows: {residual_unmatched_rows}")
        self.stdout.write("--- residual breakdown ---")
        self.stdout.write(f"no_merchant_match(clean_description != Merchant.name normalized): {no_merchant_match}")
        self.stdout.write(f"merchant_not_unique_provider(must stay NULL): {merchant_not_unique_provider}")
        self.stdout.write(f"merchant_unique_but_default_account_null: {merchant_unique_but_default_account_null}")
