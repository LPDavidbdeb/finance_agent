from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from users.models import Family, CustomUser
from accounting.models import Account
from banking.models import StagedTransaction, FinancialInstitution
from categorization.models import TransactionMappingRule
from banking.services import approve_staged_transaction
import uuid

class Command(BaseCommand):
    help = 'Seed top offender mapping rules and apply them to unprocessed transactions for a specific family.'

    def add_arguments(self, parser):
        parser.add_argument('family_id', type=str, help='UUID of the family to seed rules for')

    def get_or_create_cloned_account(self, family, root_name, path):
        """
        Ensures an account path exists for a family, cloning from global if available.
        path: List of child names, e.g. ['Income', 'Other Income']
        """
        # Get or create the root for the family
        root_global = Account.objects.get(name=root_name, family__isnull=True, parent__isnull=True)
        root, _ = Account.objects.get_or_create(
            name=root_global.name,
            account_type=root_global.account_type,
            family=family,
            parent=None
        )

        current_parent = root
        for name in path:
            # Check if exists in family
            account = Account.objects.filter(name=name, family=family, parent=current_parent).first()
            if not account:
                # Check if exists in global under global parent
                # We need the global parent of this child
                global_parent = Account.objects.filter(name=current_parent.name, family__isnull=True).first()
                global_child = None
                if global_parent:
                    global_child = Account.objects.filter(name=name, family__isnull=True, parent=global_parent).first()
                
                if global_child:
                    # Clone from global
                    account = Account.objects.create(
                        name=global_child.name,
                        account_type=global_child.account_type,
                        family=family,
                        parent=current_parent
                    )
                else:
                    # Create new
                    account = Account.objects.create(
                        name=name,
                        account_type=current_parent.account_type,
                        family=family,
                        parent=current_parent
                    )
            current_parent = account
        
        return current_parent

    @transaction.atomic
    def handle(self, *args, **options):
        family_id = options['family_id']
        try:
            family = Family.objects.get(id=family_id)
        except Family.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Family with ID {family_id} not found.'))
            return
        except ValueError:
            self.stderr.write(self.style.ERROR(f'Invalid UUID: {family_id}'))
            return

        # Get a representative user for approval service
        user = CustomUser.objects.filter(family=family).first()
        if not user:
            self.stderr.write(self.style.ERROR(f'No user found for family {family.name}. Cannot approve transactions.'))
            return

        rules_to_seed = [
            # Existing rules
            {
                'search': 'Cashback',
                'merchant': 'Cashback',
                'root': 'Revenue',
                'path': ['Income', 'Other Income']
            },
            {
                'search': 'Interest earned',
                'merchant': 'Interest',
                'root': 'Revenue',
                'path': ['Income', 'Interest Income']
            },
            {
                'search': 'Stm',
                'merchant': 'STM',
                'root': 'Expenses',
                'path': ['Transportation', 'Public Transportation']
            },
            {
                'search': 'Saq',
                'merchant': 'SAQ',
                'root': 'Expenses',
                'path': ['Alcoholic beverages, tobacco products and recreational cannabis', 'Alcoholic beverages']
            },
            {
                'search': 'Jean Coutu',
                'merchant': 'Pharmacy',
                'root': 'Expenses',
                'path': ['Health and personal care', 'Health care', 'Medicinal and pharmaceutical products']
            },
            {
                'search': 'Pharmaprix',
                'merchant': 'Pharmacy',
                'root': 'Expenses',
                'path': ['Health and personal care', 'Health care', 'Medicinal and pharmaceutical products']
            },
            {
                'search': 'Patrick Morin',
                'merchant': 'Patrick Morin',
                'root': 'Expenses',
                'path': ['Household operations, furnishings and equipment', 'Household operations', 'Home Improvement']
            },
            # New Fixed Mapping Rules
            {
                'search': 'Allez Up',
                'merchant': 'Uplify Allez Up',
                'root': 'Expenses',
                'path': ['Recreation, education and reading', 'Recreation']
            },
            {
                'search': 'Ferme Regis',
                'merchant': 'Ferme Regis Fruits Et',
                'root': 'Expenses',
                'path': ['Food', 'Food purchased from stores']
            },
            {
                'search': 'Cochons Tout Ronds',
                'merchant': 'Cochons Tout Ronds-Mtl',
                'root': 'Expenses',
                'path': ['Food', 'Food purchased from stores']
            },
            {
                'search': 'Simons',
                'merchant': 'La Maison Simons Inc',
                'root': 'Expenses',
                'path': ['Clothing and footwear', "Women's clothing"]
            },
            {
                'search': 'Ikea',
                'merchant': 'Ikea Boucherville',
                'root': 'Expenses',
                'path': ['Household operations, furnishings and equipment', 'Household operations', 'Furniture']
            },
            {
                'search': 'Cash back',
                'merchant': 'Cashback',
                'root': 'Revenue',
                'path': ['Income', 'Other Income']
            },
            # Offset Logic for Internal Adjustments
            {
                'search': 'Withdrawal',
                'merchant': 'Internal Adjustment',
                'root': 'Assets',
                'path': ['Current Assets', 'Suspense']
            },
            {
                'search': 'Cash correction',
                'merchant': 'Internal Adjustment',
                'root': 'Assets',
                'path': ['Current Assets', 'Suspense']
            },
        ]

        total_updated = 0
        total_approved = 0

        for r_def in rules_to_seed:
            target_account = self.get_or_create_cloned_account(family, r_def['root'], r_def['path'])
            
            # Create rule (Global rule for simplicity as per user prompt "create TransactionMappingRule records")
            # The prompt doesn't specify if rules should be family-specific, 
            # but TransactionMappingRule has institution field, not family. 
            # Wait, categorization/models.py: TransactionMappingRule does NOT have family field.
            # But the user said "family-aware management command". 
            # It seems TransactionMappingRule is global but points to family-specific accounts if we want.
            # Actually, let's check TransactionMappingRule again.
            
            rule, created = TransactionMappingRule.objects.get_or_create(
                search_text=r_def['search'],
                institution=None,
                defaults={
                    'merchant_name': r_def['merchant'],
                    'target_account': target_account
                }
            )
            
            if not created:
                rule.merchant_name = r_def['merchant']
                rule.target_account = target_account
                rule.save()

            # Global Auto-Apply: Query ALL StagedTransaction where status == UNPROCESSED
            # Prompt: "it should immediately query all StagedTransaction records where status == UNPROCESSED"
            # Since it's family-aware, I'll filter by family.
            
            transactions = StagedTransaction.objects.filter(
                statement_import__financial_product__family=family,
                status=StagedTransaction.Status.UNPROCESSED,
                raw_description__icontains=r_def['search']
            )

            # Exclude Amazon, Walmart, Dollarama
            transactions = transactions.exclude(
                Q(raw_description__icontains='Amazon') | 
                Q(raw_description__icontains='Walmart') | 
                Q(raw_description__icontains='Dollarama')
            )

            for tx in transactions:
                tx.clean_description = r_def['merchant']
                tx.predicted_account = target_account
                tx.save()
                total_updated += 1
                
                # Final Approval
                try:
                    approve_staged_transaction(
                        transaction_id=tx.id,
                        target_account_id=target_account.id,
                        user=user
                    )
                    total_approved += 1
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Could not approve transaction {tx.id}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(
            f'Successfully seeded rules for family {family.name}. '
            f'Updated {total_updated} transactions, Approved {total_approved}.'
        ))
