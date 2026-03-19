from django.core.management.base import BaseCommand
from django.db import transaction
from users.models import Family
from accounting.models import Account
from categorization.models import Merchant, TransactionMappingRule
from categorization.services import find_matching_rule
from banking.models import StagedTransaction
from banking.services import approve_staged_transaction
from dictionairies import banniere_dict_ws, categorie_comptable

class Command(BaseCommand):
    help = 'Bulk-seed Merchant and TransactionMappingRule tables from dictionairies.py and auto-process backlog.'

    def handle(self, *args, **options):
        with transaction.atomic():
            user_family = Family.objects.first()
            if not user_family:
                self.stdout.write(self.style.ERROR("No family found in the database."))
                return

            primary_user = user_family.users.first()
            if not primary_user:
                self.stdout.write(self.style.ERROR(f"No user found for family {user_family.name}."))
                return

            merchants_count = 0
            rules_count = 0
            tx_processed_count = 0

            # 2. Seed Merchants & Link Accounts (categorie_comptable)
            self.stdout.write("Seeding Merchants and linking accounts...")
            for cpi_name, merchant_names in categorie_comptable.items():
                target_account = Account.objects.filter(name=cpi_name, family=user_family).first()
                if not target_account:
                    self.stdout.write(self.style.WARNING(f"Account '{cpi_name}' not found for family {user_family.name}. Skipping merchants for this category."))
                    continue

                for merchant_name in merchant_names:
                    merchant, created = Merchant.objects.get_or_create(
                        family=user_family,
                        name=merchant_name,
                        defaults={'default_account': target_account}
                    )
                    if not created:
                        merchant.default_account = target_account
                        merchant.save()
                    merchants_count += 1

            # 3. Seed Bank Rules (banniere_dict_ws)
            self.stdout.write("Seeding Bank Rules...")
            for merchant_name, bank_strings in banniere_dict_ws.items():
                merchant, created = Merchant.objects.get_or_create(
                    family=user_family,
                    name=merchant_name
                )
                if created:
                    merchants_count += 1

                for bank_string in bank_strings:
                    rule, rule_created = TransactionMappingRule.objects.get_or_create(
                        merchant=merchant,
                        search_text=bank_string
                    )
                    if rule_created:
                        rules_count += 1

            # 4. Auto-Process the Backlog
            self.stdout.write("Auto-processing unprocessed transactions...")
            unprocessed_txs = StagedTransaction.objects.filter(
                status=StagedTransaction.Status.UNPROCESSED,
                statement_import__financial_product__family=user_family
            ).select_related('statement_import__financial_product')

            for tx in unprocessed_txs:
                institution_id = tx.statement_import.financial_product.institution_id
                rule = find_matching_rule(tx.raw_description, institution_id)
                
                if rule and rule.merchant.default_account:
                    tx.clean_description = rule.merchant.name
                    tx.predicted_account = rule.merchant.default_account
                    tx.save()
                    
                    try:
                        approve_staged_transaction(
                            transaction_id=tx.id,
                            target_account_id=tx.predicted_account.id,
                            user=primary_user
                        )
                        tx_processed_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Failed to approve transaction {tx.id}: {str(e)}"))

            self.stdout.write(self.style.SUCCESS(
                f'Summary: Merchants Created/Updated: {merchants_count}, '
                f'Rules Created: {rules_count}, '
                f'Transactions Processed: {tx_processed_count}'
            ))
