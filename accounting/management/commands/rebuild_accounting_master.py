import os
from django.core.management.base import BaseCommand
from django.db import transaction
from accounting.models import Account, TransactionLine
from users.models import Family
from banking.models import FinancialProduct
from chart_of_account_exemple import CPI_categories

class Command(BaseCommand):
    help = 'Rebuilds the global accounting tree with correct root nodes and clones it for families.'

    @transaction.atomic
    def handle(self, *args, **options):
        with Account.objects.disable_mptt_updates():
            # 1. Isolate Protected Accounts
            self.stdout.write("Identifying protected accounts...")
            fp_account_ids = set(FinancialProduct.objects.values_list('account_id', flat=True))
            tx_account_ids = set(TransactionLine.objects.values_list('account_id', flat=True))
            
            protected_ids = fp_account_ids | tx_account_ids
            protected_accounts = list(Account.objects.filter(id__in=protected_ids))
            
            self.stdout.write(f"Protecting {len(protected_accounts)} accounts.")
            # Reset MPTT fields to safe defaults while detached
            Account.objects.filter(id__in=protected_ids).update(parent=None, level=0, lft=1, rght=2)

            # 2. Wipe the Global and non-protected Family accounts
            self.stdout.write("Wiping non-protected accounts...")
            Account.objects.filter(family__isnull=True).delete()
            Account.objects.filter(family__isnull=False).exclude(id__in=protected_ids).delete()

            # 3. Load and Merge the Data Structures
            self.stdout.write("Preparing corrected data structure...")
            
            chart_of_accounts = {
                'Assets': {
                    'Cash': [],
                    'Bank Accounts': [], # Ensuring attachment point
                    'Investments': [],   # Ensuring attachment point
                    'Accounts Receivable': [],
                    'Inventory': [],
                    'Property': []
                },
                'Liabilities': {
                    'Accounts Payable': [],
                    'Credit Cards': [],  # Ensuring attachment point
                    'Loans': []
                },
                'Equity': ['Equity'],
                'Revenue': {
                    'Salary': ['Salary from Employer A', 'Salary from Employer B'],
                    'Government Transfers': ['Government Cash Transfers'],
                    'Investment Income': {
                        'Interest': ['Interest Income'],
                        'Capital Gains': ['Capital Gains']
                    }
                },
                'Expenses': {
                    'Essential': ['Groceries', 'Utilities', 'Rent/Mortgage'],
                    'Discretionary': ['Restaurant Meals', 'Entertainment', 'Clothing']
                }
            }

            # DIRECTLY MERGE the CPI categories into Expenses
            chart_of_accounts['Expenses'].update(CPI_categories)

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

            seed_recursive(chart_of_accounts)

            # 5. Generate Family Clone
            self.stdout.write("Generating Family Clone...")
            families = Family.objects.all()
            global_nodes = Account.objects.filter(family__isnull=True).order_by('level', 'id')
            
            for family in families:
                self.stdout.write(f"Cloning for family: {family.name}")
                family_map = {} # global_id -> cloned_family_node
                reattached_protected_ids = set()

                for g_node in global_nodes:
                    parent = family_map.get(g_node.parent_id) if g_node.parent_id else None
                    
                    # Try to match protected account by name
                    f_node = Account.objects.filter(
                        family=family, 
                        name=g_node.name, 
                        id__in=protected_ids
                    ).exclude(id__in=reattached_protected_ids).first()
                    
                    if f_node:
                        f_node.parent = parent
                        f_node.account_type = g_node.account_type
                        f_node.save()
                        reattached_protected_ids.add(f_node.id)
                    else:
                        f_node = Account.objects.create(
                            name=g_node.name,
                            account_type=g_node.account_type,
                            family=family,
                            parent=parent
                        )
                    family_map[g_node.id] = f_node
                
                # 6. Reattach Remaining Protected
                self.stdout.write(f"Reattaching remaining rescued accounts for family: {family.name}")
                
                f_cash = Account.objects.filter(family=family, name='Cash').first()
                f_bank = Account.objects.filter(family=family, name='Bank Accounts').first()
                f_inv = Account.objects.filter(family=family, name='Investments').first()
                f_cc = Account.objects.filter(family=family, name='Credit Cards').first()
                f_suspense_parent = Account.objects.filter(family=family, name='Assets').first()
                f_exp = Account.objects.filter(family=family, name='Expenses').first()
                f_rev = Account.objects.filter(family=family, name='Revenue').first()

                remaining_protected = Account.objects.filter(
                    family=family, 
                    id__in=protected_ids
                ).exclude(id__in=reattached_protected_ids)

                for acc in remaining_protected:
                    new_parent = None
                    name_lower = acc.name.lower()
                    if 'visa' in name_lower or 'credit' in name_lower or 'card' in name_lower:
                        new_parent = f_cc
                    elif 'checking' in name_lower or 'courante' in name_lower or 'cash' in name_lower:
                        new_parent = f_bank or f_cash
                    elif 'savings' in name_lower or 'épargne' in name_lower:
                        new_parent = f_bank or f_cash
                    elif 'celi' in name_lower or 'rrsp' in name_lower or 'reer' in name_lower or 'execution' in name_lower:
                        new_parent = f_inv or f_cash
                    elif 'suspense' in name_lower:
                        new_parent = f_suspense_parent
                    elif acc.account_type == 'REVENUE':
                        new_parent = f_rev
                    elif acc.account_type == 'EXPENSE':
                        new_parent = f_exp
                    
                    if new_parent:
                        acc.parent = new_parent
                        acc.save()

        # 7. Rebuild the Mathematics
        self.stdout.write("Rebuilding MPTT tree...")
        Account.objects.rebuild()
        self.stdout.write(self.style.SUCCESS("Accounting tree successfully rebuilt with corrected structure."))
