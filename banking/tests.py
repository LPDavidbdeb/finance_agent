from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from decimal import Decimal
from datetime import date
from users.models import Family, FamilyMember
from accounting.models import Account, JournalEntry, TransactionLine
from banking.models import FinancialInstitution, FinancialProduct, BankStatementImport, StagedTransaction
from banking.services import approve_staged_transaction
from finance_backend.api import api

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

    def test_liability_negative_purchase_increases_liability(self):
        liability_account = Account.objects.create(
            name="Visa", account_type=Account.AccountType.LIABILITY, family=self.family_a
        )
        cc_product = FinancialProduct.objects.create(
            institution=self.institution,
            family=self.family_a,
            owner=self.member_a,
            account=liability_account,
            product_type=FinancialProduct.ProductType.CREDIT_CARD,
        )
        cc_import = BankStatementImport.objects.create(financial_product=cc_product)
        staged = StagedTransaction.objects.create(
            statement_import=cc_import,
            bank_date=date(2026, 3, 10),
            raw_description="Restaurant",
            amount=Decimal("-775.00"),
            status=StagedTransaction.Status.UNPROCESSED,
        )
        expense_account = Account.objects.create(
            name="Dining", account_type=Account.AccountType.EXPENSE, family=self.family_a
        )

        je = approve_staged_transaction(staged.id, expense_account.id, self.user_a)
        debit_line = je.lines.get(amount=Decimal("775.00"))
        credit_line = je.lines.get(amount=Decimal("-775.00"))

        self.assertEqual(debit_line.account, expense_account)
        self.assertEqual(credit_line.account, liability_account)

    def test_liability_positive_refund_or_payment_reduces_liability(self):
        liability_account = Account.objects.create(
            name="Visa 2", account_type=Account.AccountType.LIABILITY, family=self.family_a
        )
        cc_product = FinancialProduct.objects.create(
            institution=self.institution,
            family=self.family_a,
            owner=self.member_a,
            account=liability_account,
            product_type=FinancialProduct.ProductType.CREDIT_CARD,
        )
        cc_import = BankStatementImport.objects.create(financial_product=cc_product)
        staged = StagedTransaction.objects.create(
            statement_import=cc_import,
            bank_date=date(2026, 3, 11),
            raw_description="Refund",
            amount=Decimal("45.00"),
            status=StagedTransaction.Status.UNPROCESSED,
        )
        expense_account = Account.objects.create(
            name="Dining", account_type=Account.AccountType.EXPENSE, family=self.family_a
        )

        je = approve_staged_transaction(staged.id, expense_account.id, self.user_a)
        debit_line = je.lines.get(amount=Decimal("45.00"))
        credit_line = je.lines.get(amount=Decimal("-45.00"))

        self.assertEqual(debit_line.account, liability_account)
        self.assertEqual(credit_line.account, expense_account)

    def test_transfer_checking_to_visa_cross_type_balance_sheet(self):
        checking_account = Account.objects.create(
            name="Checking Transfer", account_type=Account.AccountType.ASSET, family=self.family_a
        )
        checking_product = FinancialProduct.objects.create(
            institution=self.institution,
            family=self.family_a,
            owner=self.member_a,
            account=checking_account,
            product_type=FinancialProduct.ProductType.CHECKING,
        )
        checking_import = BankStatementImport.objects.create(financial_product=checking_product)

        visa_account = Account.objects.create(
            name="Visa Transfer", account_type=Account.AccountType.LIABILITY, family=self.family_a
        )

        staged = StagedTransaction.objects.create(
            statement_import=checking_import,
            bank_date=date(2026, 3, 12),
            raw_description="Visa Payment",
            amount=Decimal("-300.00"),
            status=StagedTransaction.Status.UNPROCESSED,
        )

        je = approve_staged_transaction(staged.id, visa_account.id, self.user_a)
        debit_line = je.lines.get(amount=Decimal("300.00"))
        credit_line = je.lines.get(amount=Decimal("-300.00"))

        self.assertEqual(debit_line.account, visa_account)
        self.assertEqual(credit_line.account, checking_account)

class UploadStatementDeduplicationTest(TestCase):
    def setUp(self):
        self.client = api.client
        self.family = Family.objects.create(name="Upload Family")
        self.user = User.objects.create_user(email="upload@example.com", password="password", family=self.family)
        self.member = FamilyMember.objects.create(
            family=self.family,
            first_name="Uploader",
            last_name="User",
            date_of_birth="1985-01-01",
            sex="M",
            role="PARENT"
        )
        self.institution = FinancialInstitution.objects.create(name="Test Bank")
        self.account = Account.objects.create(
            name="Checking Upload",
            account_type=Account.AccountType.ASSET,
            family=self.family,
        )
        self.product = FinancialProduct.objects.create(
            institution=self.institution,
            family=self.family,
            owner=self.member,
            account=self.account,
            product_type=FinancialProduct.ProductType.CHECKING,
        )

    @patch("banking.tasks.extract_transactions_task.delay")
    def test_duplicate_pdf_upload_returns_409(self, mock_delay):
        payload_bytes = b"%PDF-1.4 fake statement bytes for duplicate test"
        file_one = SimpleUploadedFile("statement.pdf", payload_bytes, content_type="application/pdf")

        first_response = self.client.post(
            f"/api/banking/products/{self.product.id}/statements/upload",
            FILES={"file": file_one},
            data={"document_date": "2026-03-22"},
            user=self.user,
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(BankStatementImport.objects.count(), 1)
        self.assertEqual(mock_delay.call_count, 1)

        file_two = SimpleUploadedFile("same-content-different-name.pdf", payload_bytes, content_type="application/pdf")
        second_response = self.client.post(
            f"/api/banking/products/{self.product.id}/statements/upload",
            FILES={"file": file_two},
            data={"document_date": "2026-03-22"},
            user=self.user,
        )

        self.assertEqual(second_response.status_code, 409)
        self.assertIn("already been uploaded", second_response.json()["detail"])
        self.assertEqual(BankStatementImport.objects.count(), 1)
        self.assertEqual(mock_delay.call_count, 1)
