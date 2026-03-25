from django.core.management.base import BaseCommand
from django.db import transaction
from users.models import Family
from banking.models import FinancialInstitution, StagedTransaction
from accounting.models import Account
from categorization.models import Merchant, TransactionMappingRule
from categorization.services import find_matching_rule
from banking.services import approve_staged_transaction
import os

# Create a shim or import from the file. 
# Since the file name has a space, we'll read it manually or rename it.
# Let's rename the file to something more pythonic if it's in our control, 
# but for now I'll just define the import path.
try:
    from vd_categories import banniere_dict_vd_categories
except ImportError:
    # Handle the file with space by using importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location("vd_categories", "vd_categories.py")
    vd_cat_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vd_cat_mod)
    banniere_dict_vd_categories = vd_cat_mod.banniere_dict_vd_categories

class Command(BaseCommand):
    help = 'Seeds Desjardins-specific mapping rules from vd_categories.py.'

    def handle(self, *args, **options):
        with transaction.atomic():
            # 1. Setup
            user_family = Family.objects.first()
            if not user_family:
                self.stdout.write(self.style.ERROR("No family found."))
                return
            
            primary_user = user_family.users.first()
            if not primary_user:
                self.stdout.write(self.style.ERROR("No user found."))
                return

            desjardins_inst = FinancialInstitution.objects.get(name='Desjardins')

            categories_processed = 0
            merchants_created = 0
            rules_seeded = 0

            # 2. Iterate through categories
            for category_name, merchants_dict in banniere_dict_vd_categories.items():
                # Fetch matching account
                account = Account.objects.filter(family=user_family, name__iexact=category_name).first()
                if not account:
                    self.stdout.write(self.style.WARNING(f"Account '{category_name}' not found for family. Skipping."))
                    continue
                
                categories_processed += 1

                # 3. Seed Merchants and Rules
                for merchant_name, search_strings in merchants_dict.items():
                    merchant, created = Merchant.objects.get_or_create(
                        family=user_family,
                        name=merchant_name.strip().upper(),
                        defaults={
                            'default_account': account,
                            'is_unique_provider': True
                        }
                    )
                    if not created:
                        merchant.default_account = account
                        merchant.is_unique_provider = True
                        merchant.save()
                    else:
                        merchants_created += 1

                    for search_string in search_strings:
                        _, r_created = TransactionMappingRule.objects.get_or_create(
                            merchant=merchant,
                            search_text=search_string,
                            institution=desjardins_inst
                        )
                        if r_created:
                            rules_seeded += 1

            # 4. Backlog Processing
            self.stdout.write("Processing backlog for Desjardins...")
            unprocessed_txs = StagedTransaction.objects.filter(
                status=StagedTransaction.Status.UNPROCESSED,
                statement_import__financial_product__institution=desjardins_inst,
                statement_import__financial_product__family=user_family
            ).select_related('statement_import__financial_product')

            reconciled_count = 0
            for tx in unprocessed_txs:
                institution_id = tx.statement_import.financial_product.institution_id
                rule = find_matching_rule(tx.raw_description, institution_id, user_family.id)
                
                if rule and rule.merchant.is_unique_provider and rule.merchant.default_account:
                    tx.merchant = rule.merchant
                    tx.predicted_account = rule.merchant.default_account
                    tx.save()
                    
                    try:
                        approve_staged_transaction(
                            transaction_id=tx.id,
                            target_account_id=rule.merchant.default_account.id,
                            user=primary_user
                        )
                        reconciled_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Failed to auto-approve tx {tx.id}: {str(e)}"))

            self.stdout.write(self.style.SUCCESS(
                f"Categories Processed: {categories_processed}, "
                f"Merchants Created: {merchants_created}, "
                f"VD Rules Seeded: {rules_seeded}, "
                f"Transactions Reconciled: {reconciled_count}"
            ))
