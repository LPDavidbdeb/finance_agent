from django.db import migrations

def create_default_accounts(apps, schema_editor):
    Account = apps.get_model('accounting', 'Account')
    AccountType = apps.get_model('accounting', 'AccountType')

    # Create root nodes
    assets = Account.objects.create(name='Assets', account_type='ASSET', parent=None)
    liabilities = Account.objects.create(name='Liabilities', account_type='LIABILITY', parent=None)
    Account.objects.create(name='Equity', account_type='EQUITY', parent=None)
    Account.objects.create(name='Revenue', account_type='REVENUE', parent=None)
    expenses = Account.objects.create(name='Expenses', account_type='EXPENSE', parent=None)

    # Create children for Assets
    current_assets = Account.objects.create(name='Current Assets', account_type='ASSET', parent=assets)
    Account.objects.create(name='Bank Accounts', account_type='ASSET', parent=current_assets)
    fixed_assets = Account.objects.create(name='Fixed Assets', account_type='ASSET', parent=assets)
    Account.objects.create(name='Real Estate', account_type='ASSET', parent=fixed_assets)

    # Create children for Expenses (StatCan CPI hierarchy)
    food = Account.objects.create(name='Food', account_type='EXPENSE', parent=expenses)
    Account.objects.create(name='Groceries', account_type='EXPENSE', parent=food)
    Account.objects.create(name='Restaurant', account_type='EXPENSE', parent=food)

    shelter = Account.objects.create(name='Shelter', account_type='EXPENSE', parent=expenses)
    Account.objects.create(name='Rent', account_type='EXPENSE', parent=shelter)
    Account.objects.create(name='Mortgage', account_type='EXPENSE', parent=shelter)
    Account.objects.create(name='Utilities', account_type='EXPENSE', parent=shelter)

    Account.objects.create(name='Household Operations', account_type='EXPENSE', parent=expenses)
    Account.objects.create(name='Transportation', account_type='EXPENSE', parent=expenses)

    recreation_education = Account.objects.create(name='Recreation & Education', account_type='EXPENSE', parent=expenses)
    Account.objects.create(name='Streaming Services', account_type='EXPENSE', parent=recreation_education)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_accounts),
    ]
