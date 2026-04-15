import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dateutil import parser as date_parser
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounting.models import Account, JournalEntry, TransactionLine
from users.models import Family


class Command(BaseCommand):
    help = "Ingest a bank CSV (Date, Description, Amount, Category) into double-entry JournalEntries."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to CSV file")
        parser.add_argument(
            "--family-id",
            type=str,
            required=True,
            help="Family UUID to scope ingestion",
        )
        parser.add_argument(
            "--offset-account-id",
            type=int,
            required=False,
            help="Existing balancing account id (defaults to/creates INGEST_CLEARING in family)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate rows without writing JournalEntry/TransactionLine records",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        family_id = options["family_id"]
        offset_account_id = options.get("offset_account_id")
        dry_run = options.get("dry_run", False)

        if not csv_path.exists() or not csv_path.is_file():
            raise CommandError(f"CSV file not found: {csv_path}")

        family = Family.objects.filter(id=family_id).first()
        if not family:
            raise CommandError(f"Family not found: {family_id}")

        offset_account = self._resolve_offset_account(family, offset_account_id)

        created_entries = 0
        skipped_rows = 0

        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}
            required = ["date", "description", "amount", "category"]
            missing = [k for k in required if k not in headers]
            if missing:
                raise CommandError(
                    f"Missing required CSV columns: {missing}. Expected: Date, Description, Amount, Category"
                )

            for line_no, row in enumerate(reader, start=2):
                try:
                    raw_date = (row.get(headers["date"]) or "").strip()
                    raw_desc = (row.get(headers["description"]) or "").strip()
                    raw_amount = (row.get(headers["amount"]) or "").strip()
                    raw_category = (row.get(headers["category"]) or "").strip()

                    if not raw_date or not raw_amount or not raw_category:
                        skipped_rows += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"Line {line_no}: skipped (missing Date/Amount/Category)."
                            )
                        )
                        continue

                    tx_date = date_parser.parse(raw_date).date()
                    amount = self._parse_amount(raw_amount)
                    if amount == Decimal("0"):
                        skipped_rows += 1
                        self.stdout.write(
                            self.style.WARNING(f"Line {line_no}: skipped (zero amount).")
                        )
                        continue

                    category_account = self._resolve_category_account(
                        family=family,
                        category_name=raw_category,
                        amount=amount,
                    )

                    # Keep accounting sign conventions aligned with account type.
                    category_line_amount = self._normalize_amount_for_account_type(
                        account_type=category_account.account_type,
                        source_amount=amount,
                    )
                    offset_line_amount = -category_line_amount

                    if dry_run:
                        created_entries += 1
                        continue

                    with transaction.atomic():
                        je = JournalEntry.objects.create(
                            family=family,
                            date=tx_date,
                            description=raw_desc or f"Imported: {raw_category}",
                            is_reconciled=True,
                        )
                        TransactionLine.objects.create(
                            journal_entry=je,
                            account=category_account,
                            amount=category_line_amount,
                        )
                        TransactionLine.objects.create(
                            journal_entry=je,
                            account=offset_account,
                            amount=offset_line_amount,
                        )
                        created_entries += 1

                except Exception as exc:
                    skipped_rows += 1
                    self.stdout.write(
                        self.style.WARNING(f"Line {line_no}: skipped ({exc}).")
                    )

        mode = "DRY RUN" if dry_run else "WRITE"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode} complete. Created entries: {created_entries}. Skipped rows: {skipped_rows}."
            )
        )

    def _resolve_offset_account(self, family: Family, account_id: int | None) -> Account:
        if account_id is not None:
            account = Account.objects.filter(id=account_id, family=family).first()
            if not account:
                raise CommandError(
                    f"Offset account id={account_id} not found in family {family.id}"
                )
            return account

        account, _ = Account.objects.get_or_create(
            family=family,
            name="INGEST_CLEARING",
            defaults={"account_type": Account.AccountType.ASSET},
        )
        return account

    def _resolve_category_account(
        self, family: Family, category_name: str, amount: Decimal
    ) -> Account:
        existing = Account.objects.filter(
            family=family,
            name__iexact=category_name,
        ).first()
        if existing:
            return existing

        inferred_type = (
            Account.AccountType.REVENUE
            if amount > 0
            else Account.AccountType.EXPENSE
        )
        return Account.objects.create(
            family=family,
            name=category_name.upper(),
            account_type=inferred_type,
        )

    def _parse_amount(self, value: str) -> Decimal:
        cleaned = value.replace("$", "").replace(",", "").strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = f"-{cleaned[1:-1]}"
        try:
            return Decimal(cleaned)
        except InvalidOperation as exc:
            raise CommandError(f"Invalid amount '{value}'") from exc

    def _normalize_amount_for_account_type(
        self, account_type: str, source_amount: Decimal
    ) -> Decimal:
        magnitude = abs(source_amount)
        if account_type in (Account.AccountType.EXPENSE, Account.AccountType.ASSET):
            return magnitude
        return -magnitude

