from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.db.models import Sum

from users.models import Family, CustomUser
from banking.models import FinancialInstitution, FinancialProduct, BankStatementImport, StagedTransaction
from banking.services import approve_staged_transaction, provision_financial_product
from accounting.models import Account, JournalEntry, TransactionLine
from assets.services import OriginationService
from planning.models import AnnuitySchedule, AnnuityPeriod
from categorization.models import TransactionMappingRule

class AmortizationReconciliationTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Reconciliation Family")
        self.user = CustomUser.objects.create_user(
            email="reconciler@example.com", 
            password="password", 
            family=self.family
        )
        self.institution = FinancialInstitution.objects.create(name="Test Bank")
        
        # 1. Setup Bank Account (Source of funds)
        self.bank_acc = Account.objects.create(
            name="Main Checking", 
            account_type=Account.AccountType.ASSET, 
            family=self.family
        )
        self.bank_product = FinancialProduct.objects.create(
            institution=self.institution,
            family=self.family,
            account=self.bank_acc,
            product_type=FinancialProduct.ProductType.CHECKING
        )
        
        # 2. Setup Liability Account (Loan provider)
        self.loan_acc = Account.objects.create(
            name="Car Loan Provider", 
            account_type=Account.AccountType.LIABILITY, 
            family=self.family
        )
        
        # 3. Setup Interest Expense Account
        self.interest_acc = Account.objects.create(
            name="Mortgage interest cost", # Matches search pattern in service
            account_type=Account.AccountType.EXPENSE, 
            family=self.family
        )

        # 4. Acquire a financed asset to generate schedule and rule
        # Total cost: 30000, Down: 5000, Financed: 25000
        self.asset = OriginationService.acquire_financed_asset(
            name="Mazda CX-5",
            family=self.family,
            total_cost=Decimal("30000.00"),
            down_payment=Decimal("5000.00"),
            financed_amount=Decimal("25000.00"),
            origination_date=date(2026, 1, 1),
            loan_term_years=5,
            annual_rate=Decimal("5.0"),
            cash_account=self.bank_acc,
            liability_account=self.loan_acc
        )
        self.schedule = self.asset.annuity_schedule
        
        # Verify the signal created the rule
        self.rule = TransactionMappingRule.objects.get(linked_schedule=self.schedule)

    def test_automated_payment_stripping(self):
        """
        End-to-end test:
        1. Mock a bank transaction matching the loan rule.
        2. Run the reconciliation pipeline.
        3. Assert 3-line compound entry with correct principal/interest split.
        """
        # Expected payment from schedule (Period 1)
        period1 = self.schedule.periods.get(period_number=1)
        expected_amount = period1.payment_amount # e.g. ~471.78
        
        # Create a statement import and staged transaction
        stmt = BankStatementImport.objects.create(
            institution=self.institution,
            financial_product=self.bank_product,
            document_date=date(2026, 2, 1)
        )
        
        # Staged transaction matches rule by name and amount +/- $5
        # Date is within ± 5 days of period1.payment_date (2026-02-01)
        staged_tx = StagedTransaction.objects.create(
            statement_import=stmt,
            bank_date=period1.payment_date + timedelta(days=2),
            raw_description="Mazda CX-5", # Matches rule search_text
            amount=-expected_amount, # Asset outflow
            status=StagedTransaction.Status.UNPROCESSED
        )

        # TRIGGER INTERCEPTION
        # Note: target_account_id is usually passed but overridden by interception if rule matches
        je = approve_staged_transaction(
            transaction_id=staged_tx.id,
            target_account_id=self.interest_acc.id, # dummy target
            user=self.user
        )

        # ASSERTIONS
        # 1. Journal Entry Details
        self.assertEqual(je.lines.count(), 3)
        self.assertEqual(je.description, f"Loan Payment: {self.schedule.name} (Period 1)")
        
        # 2. Mathematical Integrity (Sum == 0)
        balance = je.lines.aggregate(Sum('amount'))['amount__sum']
        self.assertEqual(balance, Decimal("0.00"))
        
        # 3. Compound Splits
        # Line 1: Bank Credit (Decrease Asset)
        bank_line = je.lines.get(account=self.bank_acc)
        self.assertEqual(bank_line.amount, -expected_amount)
        
        # Line 2: Loan Debit (Decrease Liability)
        loan_line = je.lines.get(account=self.loan_acc)
        self.assertEqual(loan_line.amount, period1.principal_portion)
        
        # Line 3: Interest Debit (Increase Expense)
        interest_line = je.lines.get(account=self.interest_acc)
        self.assertEqual(interest_line.amount, period1.interest_portion)
        
        # 4. State Updates
        period1.refresh_from_db()
        self.assertTrue(period1.is_paid)
        self.assertEqual(period1.journal_entry, je)
        
        staged_tx.refresh_from_db()
        self.assertEqual(staged_tx.status, StagedTransaction.Status.RECONCILED)
        self.assertEqual(staged_tx.journal_entry, je)
        self.assertEqual(staged_tx.merchant, self.rule.merchant)

    def test_auto_create_interest_account_when_missing(self):
        """
        If the family lacks an interest expense account, the reconciliation should
        create one automatically and use it in the compound journal entry.
        """
        # Remove the explicit interest account
        self.interest_acc.delete()

        period1 = self.schedule.periods.get(period_number=1)
        expected_amount = period1.payment_amount

        stmt = BankStatementImport.objects.create(
            institution=self.institution,
            financial_product=self.bank_product,
            document_date=date(2026, 2, 1)
        )

        staged_tx = StagedTransaction.objects.create(
            statement_import=stmt,
            bank_date=period1.payment_date,
            raw_description="Mazda CX-5",
            amount=-expected_amount,
            status=StagedTransaction.Status.UNPROCESSED
        )

        je = approve_staged_transaction(
            transaction_id=staged_tx.id,
            target_account_id=self.bank_acc.id,
            user=self.user
        )

        # Verify an interest account was created for the family
        # Accept either a family-scoped or global interest expense account
        interest_account = Account.objects.filter(account_type=Account.AccountType.EXPENSE, name__icontains='interest').first()
        self.assertIsNotNone(interest_account)

        # Verify JE used that interest account
        interest_line = je.lines.get(account=interest_account)
        self.assertEqual(interest_line.amount, period1.interest_portion)
