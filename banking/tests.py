from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date
from users.models import Family, FamilyMember
from accounting.models import Account, JournalEntry, TransactionLine
from banking.models import FinancialInstitution, FinancialProduct, BankStatementImport, StagedTransaction
from banking.services import approve_staged_transaction

User = get_user_model()

class ApproveStagedTransactionTest(TestCase):
    def setUp(self):
        # Create Family A
        self.family_a = Family.objects.create(name="Family A")
        self.user_a = User.objects.create_user(email="user_a@example.com", password="password", family=self.family_a)
        self.member_a = FamilyMember.objects.create(
            family=self.family_a, 
            first_name="Alice", 
            last_name="Smith", 
            date_of_birth="1980-01-01",
            sex="F",
            role="PARENT"
        )
        
        # Create Family B
        self.family_b = Family.objects.create(name="Family B")
        self.user_b = User.objects.create_user(email="user_b@example.com", password="password", family=self.family_b)
        
        # Common setup
        self.institution = FinancialInstitution.objects.create(name="Bank of Canada")
        
        # Product for Family A
        self.account_a = Account.objects.create(name="Checking A", account_type=Account.AccountType.ASSET, family=self.family_a)
        self.product_a = FinancialProduct.objects.create(
            institution=self.institution,
            family=self.family_a,
            owner=self.member_a,
            account=self.account_a,
            product_type=FinancialProduct.ProductType.CHECKING
        )
        self.import_a = BankStatementImport.objects.create(financial_product=self.product_a)
        self.staged_tx_a = StagedTransaction.objects.create(
            statement_import=self.import_a,
            bank_date=date(2023, 1, 1),
            raw_description="Grocery Store",
            amount=Decimal("-50.00"),
            status=StagedTransaction.Status.UNPROCESSED
        )
        self.target_account_a = Account.objects.create(name="Groceries", account_type=Account.AccountType.EXPENSE, family=self.family_a)

    def test_approve_staged_transaction_success(self):
        """Test successful approval of a transaction."""
        journal_entry = approve_staged_transaction(
            transaction_id=self.staged_tx_a.id,
            target_account_id=self.target_account_a.id,
            user=self.user_a
        )
        
        # Verify journal entry
        self.assertEqual(journal_entry.family, self.family_a)
        self.assertEqual(journal_entry.description, "Grocery Store")
        
        # Verify lines
        lines = journal_entry.lines.all()
        self.assertEqual(lines.count(), 2)
        
        # Amount is -50.00 (Expense)
        # Debit: target_account (Groceries) +50
        # Credit: source_account (Checking A) -50
        line_debit = lines.get(amount=Decimal("50.00"))
        line_credit = lines.get(amount=Decimal("-50.00"))
        
        self.assertEqual(line_debit.account, self.target_account_a)
        self.assertEqual(line_credit.account, self.account_a)
        
        # Verify staged transaction status
        self.staged_tx_a.refresh_from_db()
        self.assertEqual(self.staged_tx_a.status, StagedTransaction.Status.RECONCILED)
        self.assertEqual(self.staged_tx_a.journal_entry, journal_entry)

    def test_approve_staged_transaction_tenant_isolation(self):
        """Test that a user cannot approve a transaction from another family."""
        with self.assertRaises(PermissionError):
            approve_staged_transaction(
                transaction_id=self.staged_tx_a.id,
                target_account_id=self.target_account_a.id,
                user=self.user_b
            )

    def test_approve_staged_transaction_target_account_wrong_family(self):
        """Test that the target account must belong to the same family as the transaction."""
        target_account_b = Account.objects.create(name="Groceries B", account_type=Account.AccountType.EXPENSE, family=self.family_b)
        
        with self.assertRaises(ValueError) as cm:
            approve_staged_transaction(
                transaction_id=self.staged_tx_a.id,
                target_account_id=target_account_b.id,
                user=self.user_a
            )
        self.assertEqual(str(cm.exception), "Target account not found for this family.")

    def test_approve_staged_transaction_already_processed(self):
        """Test that an already processed transaction cannot be approved again."""
        self.staged_tx_a.status = StagedTransaction.Status.RECONCILED
        self.staged_tx_a.save()
        
        with self.assertRaises(ValueError) as cm:
            approve_staged_transaction(
                transaction_id=self.staged_tx_a.id,
                target_account_id=self.target_account_a.id,
                user=self.user_a
            )
        self.assertIn("already processed", str(cm.exception))
