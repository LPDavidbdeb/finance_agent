import shutil
import tempfile

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import date

import pandas as pd

from users.models import Family, FamilyMember
from accounting.models import Account, JournalEntry, TransactionLine
from banking.models import FinancialInstitution, FinancialProduct, BankStatementImport, StagedTransaction
from banking.services import approve_staged_transaction
from banking.extraction import extract_transactions_from_statement
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
        from ninja_jwt.tokens import AccessToken
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
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(self.user)}"}

    @patch("banking.tasks.extract_transactions_task.delay")
    def test_duplicate_pdf_upload_returns_409(self, mock_delay):
        payload_bytes = b"%PDF-1.4 fake statement bytes for duplicate test"
        file_one = SimpleUploadedFile("statement.pdf", payload_bytes, content_type="application/pdf")

        first_response = self.client.post(
            f"/api/banking/products/{self.product.id}/statements/upload",
            data={"file": file_one, "document_date": "2026-03-22"},
            **self.auth,
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(BankStatementImport.objects.count(), 1)
        self.assertEqual(mock_delay.call_count, 1)

        file_two = SimpleUploadedFile("same-content-different-name.pdf", payload_bytes, content_type="application/pdf")
        second_response = self.client.post(
            f"/api/banking/products/{self.product.id}/statements/upload",
            data={"file": file_two, "document_date": "2026-03-22"},
            **self.auth,
        )

        self.assertEqual(second_response.status_code, 409)
        self.assertIn("already been uploaded", second_response.json()["detail"])
        self.assertEqual(BankStatementImport.objects.count(), 1)
        self.assertEqual(mock_delay.call_count, 1)

    @patch("banking.tasks.extract_transactions_task.delay")
    def test_non_pdf_single_upload_returns_400(self, mock_delay):
        invalid_file = SimpleUploadedFile("statement.txt", b"not-a-pdf", content_type="text/plain")

        response = self.client.post(
            f"/api/banking/products/{self.product.id}/statements/upload",
            data={"file": invalid_file, "document_date": "2026-03-22"},
            **self.auth,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Only PDF files are accepted.")
        self.assertEqual(BankStatementImport.objects.count(), 0)
        self.assertEqual(mock_delay.call_count, 0)

    @patch("banking.tasks.extract_transactions_task.delay")
    def test_non_pdf_batch_upload_returns_400(self, mock_delay):
        invalid_file = SimpleUploadedFile("batch.txt", b"not-a-pdf", content_type="text/plain")

        response = self.client.post(
            f"/api/banking/products/{self.product.id}/statements/batch-upload",
            data={"files": [invalid_file]},
            **self.auth,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Only PDF files are accepted.")
        self.assertEqual(BankStatementImport.objects.count(), 0)
        self.assertEqual(mock_delay.call_count, 0)

    @patch("banking.tasks.extract_transactions_task.delay")
    def test_non_pdf_consolidated_upload_returns_400(self, mock_delay):
        invalid_file = SimpleUploadedFile("consolidated.txt", b"not-a-pdf", content_type="text/plain")

        response = self.client.post(
            f"/api/banking/institutions/{self.institution.id}/statements/upload",
            data={"file": invalid_file, "document_date": "2026-03-22"},
            **self.auth,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Only PDF files are accepted.")
        self.assertEqual(BankStatementImport.objects.count(), 0)
        self.assertEqual(mock_delay.call_count, 0)

    @patch("banking.api.BankStatementImport.objects.create", side_effect=RuntimeError("sensitive DB details"))
    @patch("banking.tasks.extract_transactions_task.delay")
    def test_single_upload_unexpected_error_returns_generic_500(self, mock_delay, _mock_create):
        payload_bytes = b"%PDF-1.4 force-create-failure"
        file_one = SimpleUploadedFile("statement.pdf", payload_bytes, content_type="application/pdf")

        response = self.client.post(
            f"/api/banking/products/{self.product.id}/statements/upload",
            data={"file": file_one, "document_date": "2026-03-22"},
            **self.auth,
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Internal server error.")
        self.assertEqual(mock_delay.call_count, 0)

    @patch("banking.api.BankStatementImport.objects.create", side_effect=RuntimeError("sensitive DB details"))
    @patch("banking.tasks.extract_transactions_task.delay")
    def test_consolidated_upload_unexpected_error_returns_generic_500(self, mock_delay, _mock_create):
        payload_bytes = b"%PDF-1.4 force-create-failure"
        file_one = SimpleUploadedFile("consolidated.pdf", payload_bytes, content_type="application/pdf")

        response = self.client.post(
            f"/api/banking/institutions/{self.institution.id}/statements/upload",
            data={"file": file_one, "document_date": "2026-03-22"},
            **self.auth,
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Internal server error.")
        self.assertEqual(mock_delay.call_count, 0)



class ConsolidatedIngestionIntegrationTest(TestCase):
    """
    End-to-end integration tests for the multi-product ingestion pipeline.

    Strategy:
      - The PDF extractor is mocked to return a pre-built DataFrame, so we are
        testing the STAGING LAYER logic (auto-spawn, caching, routing), not PDF
        parsing.
      - `get_statement_date_from_pdf` is mocked to return (None, None) so the
        pipeline falls back to the `document_date` already set on the import.
      - A real MEDIA_ROOT temp directory is used so Django's FileField validation
        passes without hitting production storage.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.family = Family.objects.create(name="Integration Family")
        self.user = get_user_model().objects.create_user(
            email="integration@example.com",
            password="password",
            family=self.family,
        )
        self.institution = FinancialInstitution.objects.create(name="Tangerine")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_import(self, document_date=date(2026, 2, 1)):
        """
        Create a BankStatementImport linked to the institution (no financial_product).
        A dummy PDF file is attached so the file-presence guard inside
        extract_transactions_from_statement does not raise.
        """
        dummy_pdf = SimpleUploadedFile(
            "tangerine_statement.pdf", b"%PDF-1.4 dummy", content_type="application/pdf"
        )
        with self.settings(MEDIA_ROOT=self.tmpdir):
            return BankStatementImport.objects.create(
                institution=self.institution,
                financial_product=None,
                document_date=document_date,
                status=BankStatementImport.Status.STAGED,
                file=dummy_pdf,
                processing_log=[],
            )

    def _mock_extractor(self, df: pd.DataFrame):
        """Return a mock extractor whose .extract() returns (df, False)."""
        extractor = MagicMock()
        extractor.extract.return_value = (df, False)
        return extractor

    def _run_extraction(self, statement_import, mock_df: pd.DataFrame):
        """
        Run extract_transactions_from_statement with the extractor mocked to
        return mock_df and date-detection mocked to fall back on document_date.
        """
        with self.settings(MEDIA_ROOT=self.tmpdir), \
             patch('banking.extraction.get_statement_date_from_pdf', return_value=(None, None)), \
             patch('banking.extraction.PDFExtractorFactory') as mock_factory:
            mock_factory.get_extractor.return_value = self._mock_extractor(mock_df)
            extract_transactions_from_statement(statement_import.id, self.user)

    # ------------------------------------------------------------------
    # Test Case 1: Auto-Spawning & Routing
    # ------------------------------------------------------------------

    def test_auto_spawn_creates_products_accounts_and_routes_transactions(self):
        """
        A 3-row DataFrame with 2 distinct account_numbers must:
          - auto-spawn exactly 2 FinancialProducts (one per unique account_number)
          - auto-spawn exactly 2 family-scoped Accounts, both ASSET type
          - stage exactly 3 StagedTransactions
          - link the first two rows to product '111' and the third to product '222'
          - complete the import successfully
        """
        mock_df = pd.DataFrame([
            {
                'date': pd.Timestamp('2026-02-10'), 'description': 'Coffee',
                'amount': 100.0, 'account_number': '111', 'inferred_product_type': 'CHECKING',
            },
            {
                'date': pd.Timestamp('2026-02-11'), 'description': 'Grocery Store',
                'amount': -50.0, 'account_number': '111', 'inferred_product_type': 'CHECKING',
            },
            {
                'date': pd.Timestamp('2026-02-15'), 'description': 'RRSP Contribution',
                'amount': 5000.0, 'account_number': '222', 'inferred_product_type': 'INVESTMENT',
            },
        ])

        statement = self._make_import()
        self._run_extraction(statement, mock_df)

        # --- 2 FinancialProducts auto-spawned ---
        products = FinancialProduct.objects.filter(family=self.family)
        self.assertEqual(products.count(), 2, "Expected exactly 2 auto-spawned FinancialProducts")

        product_111 = products.get(account_number='111')
        product_222 = products.get(account_number='222')
        self.assertEqual(product_111.product_type, FinancialProduct.ProductType.CHECKING)
        self.assertEqual(product_222.product_type, FinancialProduct.ProductType.INVESTMENT)

        # --- 2 family-scoped Accounts, both ASSET ---
        family_accounts = Account.objects.filter(family=self.family)
        self.assertEqual(family_accounts.count(), 2, "Expected exactly 2 new family-scoped Accounts")
        account_types = set(family_accounts.values_list('account_type', flat=True))
        self.assertEqual(
            account_types, {Account.AccountType.ASSET},
            "CHECKING and INVESTMENT both map to ASSET in the ledger tree",
        )

        # --- 3 StagedTransactions created ---
        staged = StagedTransaction.objects.filter(statement_import=statement)
        self.assertEqual(staged.count(), 3, "Expected exactly 3 StagedTransactions")

        # --- Correct per-row routing ---
        txs_111 = staged.filter(financial_product=product_111)
        txs_222 = staged.filter(financial_product=product_222)
        self.assertEqual(txs_111.count(), 2, "2 transactions must be linked to account '111'")
        self.assertEqual(txs_222.count(), 1, "1 transaction must be linked to account '222'")

        # --- Amounts preserved correctly ---
        descriptions_111 = set(txs_111.values_list('raw_description', flat=True))
        self.assertEqual(descriptions_111, {'Coffee', 'Grocery Store'})
        self.assertEqual(txs_222.first().amount, Decimal('5000.00'))

        # --- Import marked COMPLETED ---
        statement.refresh_from_db()
        self.assertEqual(statement.status, BankStatementImport.Status.COMPLETED)

    # ------------------------------------------------------------------
    # Test Case 2: Cache Hit / Idempotency
    # ------------------------------------------------------------------

    def test_cache_hit_reuses_existing_product_and_only_spawns_new_one(self):
        """
        When a FinancialProduct for account '333' already exists, the pipeline must:
          - reuse it (cache hit on the pre-built product_by_account_number dict)
          - auto-spawn exactly 1 new product for the new account '444'
          - create exactly 1 new family Account (for '444')
          - NOT duplicate the existing product or account for '333'
          - stage 2 transactions, each linked to the correct product
        """
        # Pre-create the parent account that provision_financial_product would get_or_create
        parent_account = Account.objects.create(
            name="Bank Accounts",
            account_type=Account.AccountType.ASSET,
            family=None,  # system-wide
        )
        existing_account = Account.objects.create(
            name="Tangerine 333",
            account_type=Account.AccountType.ASSET,
            family=self.family,
            parent=parent_account,
        )
        existing_product = FinancialProduct.objects.create(
            institution=self.institution,
            family=self.family,
            account=existing_account,
            product_type=FinancialProduct.ProductType.CHECKING,
            account_number='333',
        )

        products_before = FinancialProduct.objects.count()
        family_accounts_before = Account.objects.filter(family=self.family).count()

        mock_df = pd.DataFrame([
            {
                'date': pd.Timestamp('2026-02-10'), 'description': 'Bill Payment',
                'amount': -200.0, 'account_number': '333', 'inferred_product_type': 'CHECKING',
            },
            {
                'date': pd.Timestamp('2026-02-12'), 'description': 'Savings Deposit',
                'amount': 1000.0, 'account_number': '444', 'inferred_product_type': 'SAVINGS',
            },
        ])

        statement = self._make_import()
        self._run_extraction(statement, mock_df)

        # --- Exactly 1 new product spawned (for '444') ---
        self.assertEqual(
            FinancialProduct.objects.count(), products_before + 1,
            "Exactly 1 new FinancialProduct should be created (for account '444')",
        )
        # --- Exactly 1 new family Account spawned (for '444') ---
        self.assertEqual(
            Account.objects.filter(family=self.family).count(), family_accounts_before + 1,
            "Exactly 1 new family Account should be created (for account '444')",
        )

        # --- Product '333' not duplicated ---
        self.assertEqual(
            FinancialProduct.objects.filter(
                institution=self.institution, account_number='333'
            ).count(),
            1,
            "Product '333' must not be duplicated",
        )

        # --- 2 staged transactions, correctly routed ---
        staged = StagedTransaction.objects.filter(statement_import=statement)
        self.assertEqual(staged.count(), 2)

        tx_333 = staged.get(raw_description='Bill Payment')
        tx_444 = staged.get(raw_description='Savings Deposit')

        self.assertEqual(
            tx_333.financial_product, existing_product,
            "Transaction for '333' must be linked to the pre-existing product",
        )
        self.assertNotEqual(
            tx_444.financial_product, existing_product,
            "Transaction for '444' must be linked to the newly spawned product",
        )
        self.assertEqual(tx_444.financial_product.account_number, '444')
        self.assertEqual(tx_444.financial_product.product_type, FinancialProduct.ProductType.SAVINGS)

        # --- Import completed cleanly ---
        statement.refresh_from_db()
        self.assertEqual(statement.status, BankStatementImport.Status.COMPLETED)

    # ------------------------------------------------------------------
    # Test Case 3: Multi-Statement Product Lifecycle (The Timeline)
    # ------------------------------------------------------------------

    def test_product_lifecycle_across_two_statements(self):
        """
        Simulates the real-world product lifecycle across two consecutive monthly
        statements, proving that the pipeline builds the product roster incrementally.

        Month 1 — The Birth:
          Statement A contains 1 row for account '111' (CHECKING).
          Must spawn exactly 1 FinancialProduct and 1 Account.

        Month 2 — The Life / Cache Hit:
          Statement B contains account '111' again (cache hit) AND a new account
          '222' (INVESTMENT).
          Must spawn exactly 1 NEW product (for '222').
          Must NOT duplicate the product or account for '111'.
        """
        # ---- Month 1 ----
        df_month1 = pd.DataFrame([{
            'date': pd.Timestamp('2023-01-15'), 'description': 'PAYROLL DEPOSIT',
            'amount': 2000.0, 'account_number': '111', 'inferred_product_type': 'CHECKING',
        }])
        statement_a = self._make_import(document_date=date(2023, 1, 1))
        self._run_extraction(statement_a, df_month1)

        self.assertEqual(
            FinancialProduct.objects.filter(family=self.family).count(), 1,
            "Month 1: exactly 1 product should be born",
        )
        self.assertEqual(
            Account.objects.filter(family=self.family).count(), 1,
            "Month 1: exactly 1 account should be created",
        )
        product_111 = FinancialProduct.objects.get(family=self.family, account_number='111')
        self.assertEqual(product_111.product_type, FinancialProduct.ProductType.CHECKING)

        statement_a.refresh_from_db()
        self.assertEqual(statement_a.status, BankStatementImport.Status.COMPLETED)

        # ---- Month 2 ----
        df_month2 = pd.DataFrame([
            {
                'date': pd.Timestamp('2023-02-10'), 'description': 'GROCERY STORE',
                'amount': -80.0, 'account_number': '111', 'inferred_product_type': 'CHECKING',
            },
            {
                'date': pd.Timestamp('2023-02-15'), 'description': 'CELI CONTRIBUTION',
                'amount': 500.0, 'account_number': '222', 'inferred_product_type': 'INVESTMENT',
            },
        ])
        statement_b = self._make_import(document_date=date(2023, 2, 1))
        self._run_extraction(statement_b, df_month2)

        # Totals after Month 2
        self.assertEqual(
            FinancialProduct.objects.filter(family=self.family).count(), 2,
            "Month 2: exactly 2 products should exist (111 reused, 222 spawned)",
        )
        self.assertEqual(
            Account.objects.filter(family=self.family).count(), 2,
            "Month 2: exactly 2 accounts should exist",
        )

        # '111' must not be duplicated
        self.assertEqual(
            FinancialProduct.objects.filter(family=self.family, account_number='111').count(),
            1,
            "Product '111' must not be duplicated by Month 2 statement",
        )

        # '222' correctly spawned
        product_222 = FinancialProduct.objects.get(family=self.family, account_number='222')
        self.assertEqual(product_222.product_type, FinancialProduct.ProductType.INVESTMENT)

        # Transactions correctly routed in Month 2
        txs_b = StagedTransaction.objects.filter(statement_import=statement_b)
        self.assertEqual(txs_b.count(), 2)
        self.assertEqual(txs_b.filter(financial_product=product_111).count(), 1)
        self.assertEqual(txs_b.filter(financial_product=product_222).count(), 1)

        statement_b.refresh_from_db()
        self.assertEqual(statement_b.status, BankStatementImport.Status.COMPLETED)
