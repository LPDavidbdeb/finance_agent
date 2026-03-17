from django.core.management.base import BaseCommand
from django.db.models import Q

from accounting.models import Account
from categorization.models import TransactionMappingRule
from dictionairies import categorie_comptable


class Command(BaseCommand):
    help = "Assign target_account for TransactionMappingRule entries from ategorie_comptable mapping"

    def handle(self, *args, **options):
        expenses_root = self._get_or_create_expenses_root()

        for category_name, merchant_names in categorie_comptable.items():
            if not isinstance(merchant_names, list):
                self.stdout.write(self.style.WARNING(f"Skipping category '{category_name}' because value is not a list."))
                continue

            account = self._get_or_create_category_account(category_name, expenses_root)

            updated_for_category = 0
            for merchant_name in merchant_names:
                if not merchant_name:
                    continue

                merchant = merchant_name.strip()
                if not merchant:
                    continue

                rules = TransactionMappingRule.objects.filter(
                    Q(merchant_name__iexact=merchant) | Q(search_text__icontains=merchant)
                )

                # Idempotent update: only write when a different account is needed.
                updated_count = rules.exclude(target_account=account).update(target_account=account)
                updated_for_category += updated_count

            self.stdout.write(
                self.style.SUCCESS(
                    f"Category '{category_name}': updated {updated_for_category} rule(s)."
                )
            )

    def _get_or_create_expenses_root(self):
        root = Account.objects.filter(
            name__iexact="Expenses",
            account_type=Account.AccountType.EXPENSE,
            parent__isnull=True,
            family__isnull=True,
        ).first()
        if root:
            return root

        root, _ = Account.objects.get_or_create(
            name="Expenses",
            account_type=Account.AccountType.EXPENSE,
            parent=None,
            family=None,
            defaults={"global_reference": None},
        )
        return root

    def _get_or_create_category_account(self, category_name, expenses_root):
        account = Account.objects.filter(
            name__iexact=category_name,
            account_type=Account.AccountType.EXPENSE,
            family__isnull=True,
        ).first()
        if account:
            if account.parent_id is None and expenses_root is not None and account.id != expenses_root.id:
                account.parent = expenses_root
                account.save(update_fields=["parent"])
            return account

        account, _ = Account.objects.get_or_create(
            name=category_name,
            account_type=Account.AccountType.EXPENSE,
            family=None,
            defaults={
                "parent": expenses_root,
                "global_reference": None,
            },
        )
        return account

