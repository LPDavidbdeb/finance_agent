from decimal import Decimal
from datetime import date
import django
django.setup()

from users.models import Family, CustomUser
from banking.models import FinancialInstitution, FinancialProduct, BankStatementImport, StagedTransaction
from accounting.models import Account
from assets.services import OriginationService
from planning.models import AnnuitySchedule
from banking.services import approve_staged_transaction

def run_debug():
    family_name = 'Debug Family'
    Family.objects.filter(name=family_name).delete() # This might still fail if protected
    
    # Alternative: find the family and delete everything related manually if needed
    families = Family.objects.filter(name=family_name)
    for f in families:
        FinancialProduct.objects.filter(family=f).delete()
        Account.objects.filter(family=f).delete()
        f.delete()

    family = Family.objects.create(name=family_name)
    user = CustomUser.objects.create_user(email='u@example.com', password='pw', family=family)
    inst, _ = FinancialInstitution.objects.get_or_create(name='DBG Bank')
    bank_acc = Account.objects.create(name='DBG Checking', account_type=Account.AccountType.ASSET, family=family)
    bank_prod = FinancialProduct.objects.create(institution=inst, family=family, account=bank_acc, product_type=FinancialProduct.ProductType.CHECKING)
    loan_acc = Account.objects.create(name='DBG Loan', account_type=Account.AccountType.LIABILITY, family=family)

    asset = OriginationService.acquire_financed_asset(
        name='Debug Car',
        family=family,
        total_cost=Decimal('30000'),
        down_payment=Decimal('5000'),
        financed_amount=Decimal('25000'),
        origination_date=date(2026,1,1),
        loan_term_years=5,
        annual_rate=Decimal('5.0'),
        cash_account=bank_acc,
        liability_account=loan_acc
    )
    schedule = asset.annuity_schedule
    # delete any interest accounts
    Account.objects.filter(family=family, account_type=Account.AccountType.EXPENSE).delete()

    period1 = schedule.periods.get(period_number=1)
    stmt = BankStatementImport.objects.create(institution=inst, financial_product=bank_prod, document_date=date(2026,2,1))
    staged_tx = StagedTransaction.objects.create(statement_import=stmt, bank_date=period1.payment_date, raw_description='Debug Car', amount=-period1.payment_amount, status=StagedTransaction.Status.UNPROCESSED)

    je = approve_staged_transaction(transaction_id=staged_tx.id, target_account_id=bank_acc.id, user=user)
    print('JE created:', je.id)
    all_accounts = Account.objects.all().values('id', 'name', 'account_type', 'family_id')
    print('All accounts:', list(all_accounts))
    interest_accounts = Account.objects.filter(family=family, account_type=Account.AccountType.EXPENSE)
    print('Expense accounts:', list(interest_accounts.values('id','name','family_id')))

if __name__ == '__main__':
    run_debug()
