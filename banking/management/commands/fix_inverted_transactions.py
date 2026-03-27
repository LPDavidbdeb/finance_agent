from django.core.management.base import BaseCommand
from django.db import transaction

from accounting.models import Account, JournalEntry
from banking.models import FinancialProduct


class Command(BaseCommand):
    help = (
        "Repair inverted liability/expense journal entries created from staged credit-card/loan "
        "transactions where signs are reversed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview fixes without writing changes.")
        parser.add_argument("--from-date", type=str, default=None, help="Inclusive start date (YYYY-MM-DD).")
        parser.add_argument("--to-date", type=str, default=None, help="Inclusive end date (YYYY-MM-DD).")
        parser.add_argument("--family-id", type=int, default=None, help="Limit to one family id.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        from_date = options["from_date"]
        to_date = options["to_date"]
        family_id = options["family_id"]

        liability_products = FinancialProduct.objects.filter(
            product_type__in=[
                FinancialProduct.ProductType.CREDIT_CARD,
                FinancialProduct.ProductType.LOAN,
            ]
        )

        staged_qs = (
            liability_products
            .values_list("statement_imports__staged_transactions__id", flat=True)
        )

        je_qs = JournalEntry.objects.filter(
            staged_transactions__id__in=staged_qs,
        ).distinct().prefetch_related("lines", "staged_transactions", "staged_transactions__statement_import__financial_product")

        if from_date:
            je_qs = je_qs.filter(date__gte=from_date)
        if to_date:
            je_qs = je_qs.filter(date__lte=to_date)
        if family_id:
            je_qs = je_qs.filter(family_id=family_id)

        candidates = []
        for je in je_qs:
            lines = list(je.lines.all())
            if len(lines) != 2:
                continue

            line_a, line_b = lines[0], lines[1]
            acc_types = {line_a.account.account_type, line_b.account.account_type}
            if acc_types != {Account.AccountType.LIABILITY, Account.AccountType.EXPENSE}:
                continue

            liability_line = line_a if line_a.account.account_type == Account.AccountType.LIABILITY else line_b
            expense_line = line_a if line_a.account.account_type == Account.AccountType.EXPENSE else line_b

            staged = je.staged_transactions.first()
            if not staged:
                continue

            amount = staged.amount
            expected_expense_sign = 1 if amount < 0 else -1
            expected_liability_sign = -expected_expense_sign

            expense_sign = 1 if expense_line.amount > 0 else -1
            liability_sign = 1 if liability_line.amount > 0 else -1

            mismatch = expense_sign != expected_expense_sign or liability_sign != expected_liability_sign
            if mismatch:
                candidates.append((je, staged, liability_line, expense_line))

        self.stdout.write(f"Found {len(candidates)} inverted journal entr{'y' if len(candidates) == 1 else 'ies'}.")

        if not candidates:
            self.stdout.write(self.style.SUCCESS("No anomalies detected. Nothing to fix."))
            return

        fixed_count = 0
        write_block = transaction.atomic if not dry_run else _noop_context

        with write_block():
            for je, staged, liability_line, expense_line in candidates:
                before = self._fmt_pair(liability_line, expense_line)

                liability_new = -liability_line.amount
                expense_new = -expense_line.amount

                if not dry_run:
                    liability_line.amount = liability_new
                    expense_line.amount = expense_new
                    liability_line.save(update_fields=["amount"])
                    expense_line.save(update_fields=["amount"])

                after = (
                    f"[{liability_line.account.name} ({liability_line.account.account_type}) {liability_new}, "
                    f"{expense_line.account.name} ({expense_line.account.account_type}) {expense_new}]"
                )
                desc = staged.raw_description or je.description or "(no description)"
                self.stdout.write(
                    f"JE #{je.id} | Date: {je.date} | Desc: {desc} | "
                    f"Before: {before} -> After: {after}"
                )
                fixed_count += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN: {fixed_count} journal entries would be fixed."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Fixed {fixed_count} journal entries."))

    @staticmethod
    def _fmt_pair(liability_line, expense_line):
        return (
            f"[{liability_line.account.name} ({liability_line.account.account_type}) {liability_line.amount}, "
            f"{expense_line.account.name} ({expense_line.account.account_type}) {expense_line.amount}]"
        )


class _noop_context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
