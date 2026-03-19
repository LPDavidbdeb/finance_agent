import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q, Count
from accounting.models import Account, TransactionLine
from users.models import Family
from banking.models import FinancialProduct
from categorization.models import TransactionMappingRule
from chart_of_account_exemple import CPI_categories

class Command(BaseCommand):
    help = 'Final clean rebuild of accounting tree with strictly 5 flattened root nodes.'

    @transaction.atomic
    def handle(self, *args, **options):
        with Account.objects.disable_mptt_updates():
            # 1. Identify Protected Accounts
            self.stdout.write("Identifying protected accounts...")
            
            # Accounts with transactions MUST be handled to avoid ProtectedError
            tx_account_ids = set(TransactionLine.objects.values_list('account_id', flat=True))
            # Accounts linked to financial products
            fp_account_ids = set(FinancialProduct.objects.values_list('account_id', flat=True))
            
            protected_ids = tx_account_ids | fp_account_ids
            protected_accounts = list(Account.objects.filter(id__in=protected_ids))
            
            self.stdout.write(f"Protecting {len(protected_accounts)} accounts.")
            # Detach protected accounts
            Account.objects.filter(id__in=protected_ids).update(parent=None, level=0, lft=1, rght=2)

            # 2. Total Wipe of everything else
            self.stdout.write("Wiping all other accounts...")
            Account.objects.exclude(id__in=protected_ids).delete()

            # 3. Hardcoded Master Structure
            flat_chart_of_accounts = {
                'Assets': {
                    'Cash': [],
                    'Bank Accounts': [],
                    'Investments': [],
                    'Accounts Receivable': [],
                    'Inventory': [],
                    'Property': []
                },
                'Liabilities': {
                    'Accounts Payable': [],
                    'Credit Cards': [],
                    'Loans': []
                },
                'Equity': ['Equity'],
                'Revenue': {
                    'Salary': ['Salary from Employer A', 'Salary from Employer B'],
                    'Government Transfers': ['Government Cash Transfers'],
                    'Investment Income': {
                        'Interest Income': [],
                        'Capital Gains': ['Capital Gains'],
                        'Other Income': []
                    }
                },
                'Expenses': CPI_categories
            }

            # 4. Re-Seed Global Standard
            self.stdout.write("Re-seeding Golden Standard...")
            
            def get_account_type(name, current_type):
                type_mapping = {
                    'Assets': 'ASSET',
                    'Liabilities': 'LIABILITY',
                    'Equity': 'EQUITY',
                    'Revenue': 'REVENUE',
                    'Expenses': 'EXPENSE'
                }
                return type_mapping.get(name, current_type)

            def seed_recursive(data, parent=None, current_type=None):
                if isinstance(data, dict):
                    for name, children in data.items():
                        new_type = get_account_type(name, current_type)
                        acc = Account.objects.create(
                            name=name,
                            parent=parent,
                            account_type=new_type or 'EXPENSE',
                            family=None
                        )
                        seed_recursive(children, acc, new_type)
                elif isinstance(data, list):
                    for name in data:
                        new_type = get_account_type(name, current_type)
                        Account.objects.create(
                            name=name,
                            parent=parent,
                            account_type=new_type or 'EXPENSE',
                            family=None
                        )
                elif isinstance(data, str):
                    new_type = get_account_type(data, current_type)
                    Account.objects.create(
                        name=data,
                        parent=parent,
                        account_type=new_type or 'EXPENSE',
                        family=None
                    )

            seed_recursive(flat_chart_of_accounts)

            # 5. Clone for Families
            self.stdout.write("Cloning for families...")
            families = Family.objects.all()
            global_nodes = Account.objects.filter(family__isnull=True).order_by('level', 'id')
            
            for family in families:
                self.stdout.write(f"  Family: {family.name}")
                family_map = {} # global_id -> cloned_node
                
                for g_node in global_nodes:
                    parent = family_map.get(g_node.parent_id) if g_node.parent_id else None
                    f_node = Account.objects.create(
                        name=g_node.name,
                        account_type=g_node.account_type,
                        family=family,
                        parent=parent
                    )
                    family_map[g_node.id] = f_node
                
                # 6. Repoint and Clean Protected Accounts
                self.stdout.write(f"  Repointing protected accounts for {family.name}...")
                
                # Fuzzy/Manual Mapping for known name differences
                name_mappings = {
                    'Health & Pharmacy': 'Medicinal and pharmaceutical products',
                    'Home Improvement': "Homeowners' maintenance and repairs",
                    'Public Transportation': 'Public transportation',
                    'Interest Income': 'Interest Income',
                    'Other Income': 'Other Income',
                    'Alcoholic beverages': 'Alcoholic beverages',
                    'Food purchased from stores': 'Food purchased from stores',
                    'Food purchased from restaurants': 'Food purchased from restaurants',
                    'Recreation': 'Recreation',
                    'Furniture': 'Furniture',
                    'Women\'s clothing': "Women's clothing",
                }

                isolated_for_family = Account.objects.filter(family=family, id__in=protected_ids)
                new_family_nodes = Account.objects.filter(family=family).exclude(id__in=protected_ids)
                
                for old_acc in isolated_for_family:
                    # Determine target node in new tree
                    target_name = name_mappings.get(old_acc.name, old_acc.name)
                    new_acc = new_family_nodes.filter(name=target_name).first()
                    
                    if new_acc and old_acc.account_type in ['EXPENSE', 'REVENUE']:
                        TransactionLine.objects.filter(account=old_acc).update(account=new_acc)
                        TransactionMappingRule.objects.filter(target_account=old_acc).update(target_account=new_acc)
                        old_acc.delete()
                        self.stdout.write(f"    Repointed and deleted: {old_acc.name} -> {new_acc.name}")
                    else:
                        # For ASSET/LIABILITY/EQUITY, we reattach
                        new_parent = None
                        name_lower = old_acc.name.lower()
                        
                        f_assets = new_family_nodes.filter(name='Assets').first()
                        f_bank = new_family_nodes.filter(name='Bank Accounts').first()
                        f_inv = new_family_nodes.filter(name='Investments').first()
                        f_liab = new_family_nodes.filter(name='Liabilities').first()
                        f_cc = new_family_nodes.filter(name='Credit Cards').first()
                        f_equity = new_family_nodes.filter(name='Equity').first()

                        if 'visa' in name_lower or 'credit' in name_lower or 'card' in name_lower:
                            new_parent = f_cc or f_liab
                        elif 'checking' in name_lower or 'courante' in name_lower or 'cash' in name_lower:
                            new_parent = f_bank or f_assets
                        elif 'savings' in name_lower or 'épargne' in name_lower:
                            new_parent = f_bank or f_assets
                        elif 'celi' in name_lower or 'rrsp' in name_lower or 'reer' in name_lower or 'execution' in name_lower:
                            new_parent = f_inv or f_assets
                        elif 'suspense' in name_lower:
                            new_parent = f_assets
                        elif old_acc.account_type == 'ASSET':
                            new_parent = f_assets
                        elif old_acc.account_type == 'LIABILITY':
                            new_parent = f_liab
                        elif old_acc.account_type == 'EQUITY':
                            new_parent = f_equity
                        
                        if new_parent:
                            old_acc.parent = new_parent
                            old_acc.save()
                            self.stdout.write(f"    Reattached: {old_acc.name} under {new_parent.name}")
                        else:
                            self.stdout.write(f"    Warning: Could not reattach {old_acc.name}")

        # 7. Rebuild
        self.stdout.write("Rebuilding MPTT tree...")
        Account.objects.rebuild()
        self.stdout.write(self.style.SUCCESS("Accounting tree successfully rebuilt with strictly 5 flattened root nodes."))
