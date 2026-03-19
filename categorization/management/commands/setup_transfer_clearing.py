from django.core.management.base import BaseCommand
from django.db import transaction
from users.models import Family
from accounting.models import Account
from categorization.models import Merchant, TransactionMappingRule
from categorization.services import find_matching_rule
from banking.models import StagedTransaction
from banking.services import approve_staged_transaction

class Command(BaseCommand):
    help = 'Sets up an Internal Transfers clearing account and configures transfer-related merchants.'

    def handle(self, *args, **options):
        with transaction.atomic():
            user_family = Family.objects.first()
            if not user_family:
                self.stdout.write(self.style.ERROR("No family found."))
                return

            primary_user = user_family.users.first()
            if not primary_user:
                self.stdout.write(self.style.ERROR("No primary user found."))
                return

            # 1. Create the Clearing Account
            assets_root = Account.objects.get(family=user_family, name='Assets', parent=None)
            clearing_account, created = Account.objects.get_or_create(
                family=user_family,
                name='Internal Transfers',
                parent=assets_root,
                defaults={'account_type': 'ASSET'}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created clearing account: {clearing_account.name}"))
            else:
                self.stdout.write(f"Using existing clearing account: {clearing_account.name}")

            # 2. Configure the Transfer Merchants
            transfer_keywords = ['DEPOSIT', 'TRANSFER', 'VIREMENT']
            updated_merchants = []
            
            for kw in transfer_keywords:
                merchant, m_created = Merchant.objects.get_or_create(
                    family=user_family,
                    name=kw,
                    defaults={
                        'default_account': clearing_account,
                        'is_unique_provider': True
                    }
                )
                if not m_created:
                    merchant.default_account = clearing_account
                    merchant.is_unique_provider = True
                    merchant.save()
                
                updated_merchants.append(merchant.name)
                
                # Also ensure there is a basic rule for each keyword if none exists
                TransactionMappingRule.objects.get_or_create(
                    merchant=merchant,
                    search_text=kw
                )

            self.stdout.write(self.style.SUCCESS(f"Configured merchants: {', '.join(updated_merchants)}"))

            # 3. Auto-Process the Backlog
            unprocessed_txs = StagedTransaction.objects.filter(
                status=StagedTransaction.Status.UNPROCESSED,
                statement_import__financial_product__family=user_family
            ).select_related('statement_import__financial_product')

            processed_count = 0
            for tx in unprocessed_txs:
                institution_id = tx.statement_import.financial_product.institution_id
                rule = find_matching_rule(tx.raw_description, institution_id)
                
                # If we matched one of our newly configured unique transfer merchants
                if rule and rule.merchant.is_unique_provider and rule.merchant.default_account:
                    tx.clean_description = rule.merchant.name
                    tx.predicted_account = rule.merchant.default_account
                    tx.save()
                    
                    try:
                        approve_staged_transaction(
                            transaction_id=tx.id,
                            target_account_id=rule.merchant.default_account.id,
                            user=primary_user
                        )
                        processed_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Failed to auto-approve tx {tx.id}: {str(e)}"))

            self.stdout.write(self.style.SUCCESS(f"Clearing Account Created, Merchants Updated, Backlog Processed: {processed_count}"))
