from django.core.management.base import BaseCommand
from django.db import transaction
from accounting.models import Account


class Command(BaseCommand):
    help = 'Seeds the global chart-of-accounts template (no family scope). Safe to run multiple times.'

    @transaction.atomic
    def handle(self, *args, **options):
        asset_tree = {
            "Current Assets": ["Bank Accounts", "Cash"],
            "Investments": ["TFSA", "RRSP", "Non-Registered"],
            "Fixed Assets": ["Real Estate", "Vehicles"],
        }
        liability_tree = {
            "Current Liabilities": ["Credit Cards", "Lines of Credit"],
            "Long-Term Liabilities": ["Mortgages", "Auto Loans", "Student Loans"],
        }
        equity_tree = {"Retained Earnings": []}
        revenue_tree = {
            "Employment Income": ["Salary", "Bonus"],
            "Investment Income": ["Interest", "Dividends", "Capital Gains"],
            "Other Income": [],
        }
        expense_tree = {
            "Food": ["Groceries", "Restaurant"],
            "Shelter": ["Rent", "Mortgage", "Utilities"],
            "Household Operations": [],
            "Transportation": [],
            "Recreation & Education": ["Streaming Services"],
        }

        def build(node, parent, acc_type):
            if isinstance(node, dict):
                for key, val in node.items():
                    acct, _ = Account.objects.get_or_create(
                        name=key, account_type=acc_type, parent=parent, family=None
                    )
                    build(val, acct, acc_type)
            elif isinstance(node, list):
                for item in node:
                    if isinstance(item, dict):
                        build(item, parent, acc_type)
                    else:
                        Account.objects.get_or_create(
                            name=item, account_type=acc_type, parent=parent, family=None
                        )

        for label, tree, acc_type in [
            ("Assets", asset_tree, "ASSET"),
            ("Liabilities", liability_tree, "LIABILITY"),
            ("Equity", equity_tree, "EQUITY"),
            ("Revenue", revenue_tree, "REVENUE"),
            ("Expenses", expense_tree, "EXPENSE"),
        ]:
            self.stdout.write(f"Seeding {label}...")
            root, _ = Account.objects.get_or_create(
                name=label, account_type=acc_type, parent=None, family=None
            )
            build(tree, root, acc_type)

        self.stdout.write("Rebuilding MPTT structure...")
        Account.objects.rebuild()
        self.stdout.write(self.style.SUCCESS("Done."))
