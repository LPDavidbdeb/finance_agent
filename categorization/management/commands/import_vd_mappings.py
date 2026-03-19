from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from users.models import Family
from banking.models import FinancialInstitution, StagedTransaction
from accounting.models import Account
from categorization.models import Merchant, TransactionMappingRule
from categorization.services import find_matching_rule
from banking.services import approve_staged_transaction
from dictionairies import banniere_dict_vd, categorie_comptable

class Command(BaseCommand):
    help = 'Backfills WS rules, imports VD mappings for Desjardins, and reconciles backlog.'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Step A: Setup Institutions & Family
            user_family = Family.objects.first()
            if not user_family:
                self.stdout.write(self.style.ERROR("No family found."))
                return
            
            primary_user = user_family.users.first()
            if not primary_user:
                self.stdout.write(self.style.ERROR("No user found."))
                return

            ws_inst = FinancialInstitution.objects.get(name='Wealthsimple')
            vd_inst = FinancialInstitution.objects.get(name='Desjardins')

            # Step B: Backfill WS Rules
            ws_updated = TransactionMappingRule.objects.filter(institution__isnull=True).update(institution=ws_inst)
            self.stdout.write(f"Backfilled {ws_updated} rules to Wealthsimple.")

            # Step D: Seed VD Merchants & Rules
            self.stdout.write("Seeding VD mappings for Desjardins...")
            vd_merchants_count = 0
            vd_rules_count = 0

            # Iterate through categories to find merchants
            for cpi_name, merchant_names in categorie_comptable.items():
                target_account = Account.objects.filter(name=cpi_name, family=user_family).first()
                
                for merchant_name in merchant_names:
                    # Only process if this merchant has a VD bank string defined
                    if merchant_name in banniere_dict_vd:
                        # Get or create merchant and ensure category is linked
                        merchant, m_created = Merchant.objects.get_or_create(
                            family=user_family,
                            name=merchant_name,
                            defaults={'default_account': target_account}
                        )
                        if not m_created and target_account and not merchant.default_account:
                            merchant.default_account = target_account
                            merchant.save()
                        
                        if m_created: vd_merchants_count += 1

                        # Create the rule for Desjardins
                        # Use the first bank string in the list as the search text
                        bank_strings = banniere_dict_vd[merchant_name]
                        if bank_strings:
                            rule, r_created = TransactionMappingRule.objects.get_or_create(
                                merchant=merchant,
                                search_text=bank_strings[0],
                                institution=vd_inst
                            )
                            if r_created: vd_rules_count += 1

            # Step E: Auto-Process the Backlog
            self.stdout.write("Auto-processing backlog...")
            unprocessed_txs = StagedTransaction.objects.filter(
                status=StagedTransaction.Status.UNPROCESSED,
                statement_import__financial_product__family=user_family
            ).select_related('statement_import__financial_product')

            reconciled_count = 0
            for tx in unprocessed_txs:
                institution_id = tx.statement_import.financial_product.institution_id
                rule = find_matching_rule(tx.raw_description, institution_id)
                
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
                        reconciled_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Failed to auto-approve tx {tx.id}: {str(e)}"))

            self.stdout.write(self.style.SUCCESS(
                f"WS Rules Backfilled: {ws_updated}, "
                f"VD Rules Created: {vd_rules_count}, "
                f"Transactions Reconciled: {reconciled_count}"
            ))
