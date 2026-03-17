import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
django.setup()

from accounting.models import Account

def seed_master_template():
    print("Starting database seed...")
    
    # 1. Define the complete Master Dictionary for all Account Types
    
    # ASSETS
    asset_tree = {
        "Current Assets": ["Bank Accounts", "Cash"],
        "Investments": ["TFSA", "RRSP", "Non-Registered"],
        "Fixed Assets": ["Real Estate", "Vehicles"]
    }
    
    # LIABILITIES
    liability_tree = {
        "Current Liabilities": ["Credit Cards", "Lines of Credit"],
        "Long-Term Liabilities": ["Mortgages", "Auto Loans", "Student Loans"]
    }
    
    # EQUITY
    equity_tree = {
        "Retained Earnings": []
    }
    
    # REVENUE
    revenue_tree = {
        "Employment Income": ["Salary", "Bonus"],
        "Investment Income": ["Interest", "Dividends", "Capital Gains"],
        "Other Income": []
    }
    
    # EXPENSES (Statistics Canada Dictionary)
    expense_tree = {
        "Food": ["Groceries", "Restaurant"],
        "Shelter": ["Rent", "Mortgage", "Utilities"],
        "Household Operations": [],
        "Transportation": [],
        "Recreation & Education": ["Streaming Services"]
    }

    # 2. The Execution Logic: Recursive Tree Builder
    def build_tree(data_node, parent_node, acc_type):
        if isinstance(data_node, dict):
            for key, value in data_node.items():
                node, _ = Account.objects.get_or_create(
                    name=key, 
                    account_type=acc_type, 
                    parent=parent_node, 
                    family=None # Global template
                )
                build_tree(value, node, acc_type)
        elif isinstance(data_node, list):
            for item in data_node:
                if isinstance(item, dict):
                    build_tree(item, parent_node, acc_type)
                else:
                    Account.objects.get_or_create(
                        name=item, 
                        account_type=acc_type, 
                        parent=parent_node, 
                        family=None # Global template
                    )

    # 3. Create the Root Nodes and Build the Trees
    print("Seeding Assets...")
    asset_root, _ = Account.objects.get_or_create(name='Assets', account_type='ASSET', parent=None, family=None)
    build_tree(asset_tree, asset_root, 'ASSET')
    
    print("Seeding Liabilities...")
    liability_root, _ = Account.objects.get_or_create(name='Liabilities', account_type='LIABILITY', parent=None, family=None)
    build_tree(liability_tree, liability_root, 'LIABILITY')
    
    print("Seeding Equity...")
    equity_root, _ = Account.objects.get_or_create(name='Equity', account_type='EQUITY', parent=None, family=None)
    build_tree(equity_tree, equity_root, 'EQUITY')
    
    print("Seeding Revenue...")
    revenue_root, _ = Account.objects.get_or_create(name='Revenue', account_type='REVENUE', parent=None, family=None)
    build_tree(revenue_tree, revenue_root, 'REVENUE')
    
    print("Seeding Expenses...")
    expense_root, _ = Account.objects.get_or_create(name='Expenses', account_type='EXPENSE', parent=None, family=None)
    build_tree(expense_tree, expense_root, 'EXPENSE')

    # 4. FIX: Rebuild the MPTT tree mathematically to ensure integrity
    print("Rebuilding MPTT structure mathematically...")
    Account.objects.rebuild()
    
    print("Seeding complete!")

if __name__ == '__main__':
    seed_master_template()
