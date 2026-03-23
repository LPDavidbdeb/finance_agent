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
        
        families = Family.objects.all()
        
        total_categorized = 0
        total_approved = 0

        for family in families:
            self.stdout.write(f"Processing for family: {family.name}")
            
            user = family.users.first()
            if not user:
                self.stdout.write(self.style.WARNING(f"  No user found for family {family.name}. Skipping."))
                continue

            unprocessed_txs = StagedTransaction.objects.filter(
                status__in=[
                    StagedTransaction.Status.UNPROCESSED,
                    StagedTransaction.Status.PENDING_REVIEW,
                ],
                statement_import__financial_product__family=family
            ).select_related('statement_import__financial_product', 'statement_import__financial_product__institution')

            for tx in unprocessed_txs:
                institution_id = tx.statement_import.financial_product.institution_id
                # Multi-tenancy & Amount Range: Pass family.id and tx.amount
                rule = find_matching_rule(tx.raw_description, institution_id, family.id, transaction_amount=tx.amount)
                
                if rule:
                    tx.merchant = rule.merchant
                    
                    # 1. ONLY grab the target account if the merchant is a unique provider
                    if rule.merchant.is_unique_provider:
                        target_account = rule.merchant.default_account
                        
                        if target_account:
                            # Resolve family-specific account if the default is global
                            if target_account.family_id != family.id:
                                resolved_account = Account.objects.filter(name=target_account.name, family=family).first()
                                if not resolved_account:
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
                            
                            # Save prediction
                            tx.predicted_account = target_account
                            tx.save()
                            total_categorized += 1
                            
                            # 2. AUTO-APPROVE based on the existence of the target_account
                            try:
                                approve_staged_transaction(
                                    transaction_id=tx.id,
                                    target_account_id=target_account.id,
                                    user=user
                                )
                                total_approved += 1
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(f"Failed to approve tx {tx.id}: {e}"))
                                
                        else:
                            # Unique provider, but no default account exists. Leave in Inbox.
                            tx.predicted_account = None
                            tx.save()
                            total_categorized += 1
                    else:
                        # NOT a unique provider (e.g. Walmart, Amazon). 
                        # We identify the merchant, but leave it in the inbox for manual review.
                        tx.predicted_account = None
                        tx.save()
                        total_categorized += 1

        self.stdout.write(self.style.SUCCESS(
            f"Reprocessing Complete.\n"
            f"Transactions Categorized: {total_categorized}\n"
            f"Transactions Auto-Approved: {total_approved}"
        ))
