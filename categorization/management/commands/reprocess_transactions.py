from django.core.management.base import BaseCommand
from django.db import transaction
from users.models import Family, CustomUser
from banking.models import StagedTransaction
from accounting.models import Account
from categorization.services import find_matching_rule
from banking.services import approve_staged_transaction
import logging

class Command(BaseCommand):
    help = 'Re-runs the categorization engine against all UNPROCESSED transactions.'

    def handle(self, *args, **options):
        logger = logging.getLogger(__name__)
        
        # We'll process for all families or just the first one found
        families = Family.objects.all()
        
        total_categorized = 0
        total_approved = 0

        for family in families:
            self.stdout.write(f"Processing for family: {family.name}")
            
            # Get a representative user for the approval service
            user = family.users.first()
            if not user:
                self.stdout.write(self.style.WARNING(f"  No user found for family {family.name}. Skipping."))
                continue

            unprocessed_txs = StagedTransaction.objects.filter(
                status=StagedTransaction.Status.UNPROCESSED,
                statement_import__financial_product__family=family
            ).select_related('statement_import__financial_product', 'statement_import__financial_product__institution')

            for tx in unprocessed_txs:
                institution_id = tx.statement_import.financial_product.institution_id
                rule = find_matching_rule(tx.raw_description, institution_id)
                
                if rule:
                    tx.clean_description = rule.merchant.name
                    
                    # Logic: Unique providers with default accounts can be auto-approved
                    if rule.merchant.is_unique_provider and rule.merchant.default_account:
                        target_account = rule.merchant.default_account
                        
                        # Resolve family-specific account if the default is global
                        if target_account.family_id != family.id:
                            resolved_account = Account.objects.filter(name=target_account.name, family=family).first()
                            if not resolved_account:
                                # Recursively find/create parent in family
                                parent = None
                                if target_account.parent:
                                    parent = Account.objects.filter(name=target_account.parent.name, family=family).first()
                                
                                resolved_account = Account.objects.create(
                                    name=target_account.name,
                                    account_type=target_account.account_type,
                                    family=family,
                                    parent=parent
                                )
                            target_account = resolved_account

                        tx.predicted_account = target_account
                        tx.save()
                        total_categorized += 1
                        
                        try:
                            approve_staged_transaction(
                                transaction_id=tx.id,
                                target_account_id=target_account.id,
                                user=user
                            )
                            total_approved += 1
                        except Exception as e:
                            logger.error(f"Reprocess failed to approve tx {tx.id}: {e}")
                    else:
                        # Non-unique or no category: just set description
                        tx.predicted_account = None
                        tx.save()
                        total_categorized += 1

        self.stdout.write(self.style.SUCCESS(
            f"Reprocessing Complete.\n"
            f"Transactions Categorized: {total_categorized}\n"
            f"Transactions Auto-Approved: {total_approved}"
        ))
