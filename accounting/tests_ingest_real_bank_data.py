import csv
import tempfile
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from accounting.models import Account, JournalEntry, TransactionLine
from users.models import Family


class IngestRealBankDataCommandTests(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Ingestion Family")
        self.offset = Account.objects.create(
            family=self.family,
            name="CHEQUING",
            account_type=Account.AccountType.ASSET,
        )

    def _write_csv(self, rows):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
        with tmp as handle:
            writer = csv.writer(handle)
            writer.writerow(["Date", "Description", "Amount", "Category"])
            writer.writerows(rows)
        return tmp.name

    def test_ingests_csv_into_double_entry_journal(self):
        csv_path = self._write_csv(
            [
                ["2026-01-05", "Metro", "-125.30", "Groceries"],
                ["2026-01-09", "Hydro", "-88.11", "Utilities"],
            ]
        )

        call_command(
            "ingest_real_bank_data",
            csv_path,
            family_id=str(self.family.id),
            offset_account_id=self.offset.id,
        )

        self.assertEqual(JournalEntry.objects.filter(family=self.family).count(), 2)
        self.assertEqual(TransactionLine.objects.count(), 4)
        self.assertEqual(
            JournalEntry.objects.filter(family=self.family, is_reconciled=True).count(),
            2,
        )

        groceries = Account.objects.get(family=self.family, name="GROCERIES")
        self.assertEqual(groceries.account_type, Account.AccountType.EXPENSE)

        for je in JournalEntry.objects.filter(family=self.family):
            total = sum(je.lines.values_list("amount", flat=True), Decimal("0"))
            self.assertEqual(total, Decimal("0"))

    def test_dry_run_does_not_write(self):
        csv_path = self._write_csv(
            [["2026-01-05", "Metro", "-125.30", "Groceries"]]
        )

        call_command(
            "ingest_real_bank_data",
            csv_path,
            family_id=str(self.family.id),
            dry_run=True,
        )

        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(TransactionLine.objects.count(), 0)

