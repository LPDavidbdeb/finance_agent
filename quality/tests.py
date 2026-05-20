from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja_jwt.tokens import AccessToken

from accounting.models import Account, JournalEntry, TransactionLine
from banking.consistency import TransactionConsistencyReport
from banking.models import BankStatementImport, FinancialInstitution, FinancialProduct, StagedTransaction
from quality.models import ConsistencyReportFinding, ConsistencyReportRun
from quality.services import create_consistency_report_run
from users.models import Family
from finance_backend.test_client_factory import get_test_client

User = get_user_model()



class ConsistencyReportPersistenceTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='Quality Family')
        self.account = Account.objects.create(
            name='Checking',
            account_type=Account.AccountType.ASSET,
            family=self.family,
        )
        self.journal_entry = JournalEntry.objects.create(
            family=self.family,
            date=date(2026, 4, 1),
            description='Test entry',
            is_reconciled=True,
        )
        TransactionLine.objects.create(journal_entry=self.journal_entry, account=self.account, amount=Decimal('10.00'))
        TransactionLine.objects.create(journal_entry=self.journal_entry, account=self.account, amount=Decimal('-10.00'))

    def test_create_consistency_report_run_persists_summary_and_findings(self):
        report = TransactionConsistencyReport(
            statement_count=1,
            staged_transaction_count=2,
            journal_entry_count=1,
            transaction_line_count=2,
            balanced_journal_entry_count=1,
            unbalanced_journal_entry_count=0,
            auto_routed_count=1,
            fallback_routed_count=0,
            manual_review_queue_count=1,
            zero_amount_unprocessed_count=2,
            old_unresolved_nonzero_count=0,
            predicted_but_unprocessed_nonzero_count=0,
            reconciled_without_journal_entry_count=0,
            recent_reconciled_without_prediction_count=0,
            cutoff_date=date(2026, 1, 1),
        )

        run = create_consistency_report_run(
            family=self.family,
            trigger_source=ConsistencyReportRun.TriggerSource.MANUAL,
            report=report,
            scope={'statement_ids': [1]},
        )

        run.refresh_from_db()
        self.assertEqual(run.family, self.family)
        self.assertEqual(run.status, ConsistencyReportRun.Status.COMPLETED)
        self.assertEqual(run.summary['statement_count'], 1)
        self.assertEqual(run.summary['cutoff_date'], '2026-01-01')
        self.assertEqual(run.scope['statement_ids'], [1])
        self.assertEqual(run.findings.count(), 1)

        finding = run.findings.get()
        self.assertEqual(finding.severity, ConsistencyReportFinding.Severity.INFO)
        self.assertEqual(finding.category, 'ZERO_AMOUNT_UNPROCESSED')
        self.assertEqual(finding.details['count'], 2)


class ReprocessCommandReportPersistenceTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='Reprocess Family')
        self.user = User.objects.create_user('reprocess@example.com', 'x', family=self.family)
        self.institution = FinancialInstitution.objects.create(name='Test Bank')
        self.account = Account.objects.create(
            name='Reprocess Checking',
            account_type=Account.AccountType.ASSET,
            family=self.family,
        )
        self.product = FinancialProduct.objects.create(
            institution=self.institution,
            family=self.family,
            account=self.account,
            product_type=FinancialProduct.ProductType.CHECKING,
        )
        self.statement = BankStatementImport.objects.create(
            financial_product=self.product,
            institution=self.institution,
        )

    @patch('banking.management.commands.reprocess_all_statements.extract_transactions_from_statement')
    def test_reprocess_command_persists_consistency_run(self, mocked_extract):
        def _mark_completed(import_id, user):
            BankStatementImport.objects.filter(id=import_id).update(
                status=BankStatementImport.Status.COMPLETED,
                processed_by_python=True,
            )

        mocked_extract.side_effect = _mark_completed

        call_command('reprocess_all_statements')

        run = ConsistencyReportRun.objects.get()
        self.assertEqual(run.family, self.family)
        self.assertEqual(run.trigger_source, ConsistencyReportRun.TriggerSource.REPROCESS)
        self.assertEqual(run.status, ConsistencyReportRun.Status.COMPLETED)
        self.assertEqual(run.scope['statement_ids'], [self.statement.id])
        self.assertEqual(run.scope['processed_count'], 1)
        self.assertEqual(run.scope['failed_count'], 0)


class LedgerResetCommandReportPersistenceTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name='Reset Family')
        self.institution = FinancialInstitution.objects.create(name='Reset Bank')
        self.account = Account.objects.create(
            name='Reset Checking',
            account_type=Account.AccountType.ASSET,
            family=self.family,
        )
        self.product = FinancialProduct.objects.create(
            institution=self.institution,
            family=self.family,
            account=self.account,
            product_type=FinancialProduct.ProductType.CHECKING,
        )
        self.statement = BankStatementImport.objects.create(
            financial_product=self.product,
            institution=self.institution,
            status=BankStatementImport.Status.COMPLETED,
            processed_by_python=True,
        )
        StagedTransaction.objects.create(
            statement_import=self.statement,
            financial_product=self.product,
            bank_date=date(2026, 4, 1),
            raw_description='Reset tx',
            amount=Decimal('-12.34'),
            status=StagedTransaction.Status.UNPROCESSED,
        )

        je = JournalEntry.objects.create(
            family=self.family,
            date=date(2026, 4, 1),
            description='Reset JE',
            is_reconciled=True,
        )
        TransactionLine.objects.create(journal_entry=je, account=self.account, amount=Decimal('12.34'))
        TransactionLine.objects.create(journal_entry=je, account=self.account, amount=Decimal('-12.34'))

    def test_ledger_reset_persists_consistency_run(self):
        call_command('ledger_reset', '--confirm', '--family-id', str(self.family.id))

        run = ConsistencyReportRun.objects.get(trigger_source=ConsistencyReportRun.TriggerSource.LEDGER_RESET)
        self.assertEqual(run.family, self.family)
        self.assertEqual(run.status, ConsistencyReportRun.Status.COMPLETED)
        self.assertEqual(run.scope['family_id'], str(self.family.id))
        self.assertEqual(run.scope['deleted_before_reset']['staged'], 1)
        self.assertEqual(run.scope['deleted_before_reset']['jes'], 1)
        self.assertEqual(run.scope['deleted_before_reset']['lines'], 2)
        self.statement.refresh_from_db()
        self.assertEqual(self.statement.status, BankStatementImport.Status.STAGED)


class QualityApiTest(TestCase):
    def setUp(self):
        self.client = get_test_client()
        self.family_a = Family.objects.create(name='Quality A')
        self.family_b = Family.objects.create(name='Quality B')

        self.user_a = User.objects.create_user('qa@example.com', 'x', family=self.family_a)
        self.user_b = User.objects.create_user('qb@example.com', 'x', family=self.family_b)
        self.headers_a = {'Authorization': f"Bearer {str(AccessToken.for_user(self.user_a))}"}
        self.headers_b = {'Authorization': f"Bearer {str(AccessToken.for_user(self.user_b))}"}

        self.institution = FinancialInstitution.objects.create(name='QA Bank')
        self.account_a = Account.objects.create(name='QA A Checking', account_type=Account.AccountType.ASSET, family=self.family_a)
        self.product_a = FinancialProduct.objects.create(
            institution=self.institution,
            family=self.family_a,
            account=self.account_a,
            product_type=FinancialProduct.ProductType.CHECKING,
        )
        self.statement_a = BankStatementImport.objects.create(financial_product=self.product_a, institution=self.institution)

        self.old_unresolved_tx = StagedTransaction.objects.create(
            statement_import=self.statement_a,
            financial_product=self.product_a,
            bank_date=date(2025, 12, 31),
            raw_description='Old unresolved row',
            amount=Decimal('45.67'),
            status=StagedTransaction.Status.UNPROCESSED,
        )
        self.recent_unresolved_tx = StagedTransaction.objects.create(
            statement_import=self.statement_a,
            financial_product=self.product_a,
            bank_date=date(2026, 3, 1),
            raw_description='Recent unresolved row',
            amount=Decimal('12.34'),
            status=StagedTransaction.Status.UNPROCESSED,
        )

        report = TransactionConsistencyReport(
            statement_count=1,
            staged_transaction_count=0,
            journal_entry_count=0,
            transaction_line_count=0,
            balanced_journal_entry_count=0,
            unbalanced_journal_entry_count=0,
            auto_routed_count=0,
            fallback_routed_count=0,
            manual_review_queue_count=0,
            zero_amount_unprocessed_count=1,
            old_unresolved_nonzero_count=0,
            predicted_but_unprocessed_nonzero_count=0,
            reconciled_without_journal_entry_count=0,
            recent_reconciled_without_prediction_count=0,
            cutoff_date=date(2026, 1, 1),
        )
        self.run_a = create_consistency_report_run(
            family=self.family_a,
            trigger_source=ConsistencyReportRun.TriggerSource.MANUAL,
            report=report,
            scope={'statement_ids': [self.statement_a.id]},
        )

    def test_list_runs_is_family_scoped(self):
        response_a = self.client.get('/quality/consistency-runs', headers=self.headers_a)
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(len(response_a.json()), 1)
        self.assertEqual(response_a.json()[0]['id'], self.run_a.id)

        response_b = self.client.get('/quality/consistency-runs', headers=self.headers_b)
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(response_b.json(), [])

    def test_get_findings_is_family_scoped(self):
        response_a = self.client.get(f'/quality/consistency-runs/{self.run_a.id}/findings', headers=self.headers_a)
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(len(response_a.json()), 1)
        self.assertEqual(response_a.json()[0]['category'], 'ZERO_AMOUNT_UNPROCESSED')

        response_b = self.client.get(f'/quality/consistency-runs/{self.run_a.id}/findings', headers=self.headers_b)
        self.assertEqual(response_b.status_code, 404)

    def test_get_unresolved_transactions_returns_old_nonzero_rows(self):
        response = self.client.get(f'/quality/consistency-runs/{self.run_a.id}/unresolved-transactions', headers=self.headers_a)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['id'], self.old_unresolved_tx.id)
        self.assertEqual(payload[0]['statement_import_id'], self.statement_a.id)
        self.assertEqual(payload[0]['raw_description'], 'Old unresolved row')
        self.assertEqual(payload[0]['amount'], '45.67')

        response_b = self.client.get(f'/quality/consistency-runs/{self.run_a.id}/unresolved-transactions', headers=self.headers_b)
        self.assertEqual(response_b.status_code, 404)

    def test_trigger_manual_run_respects_statement_scope(self):
        response = self.client.post(
            '/quality/consistency-runs',
            json={'statement_ids': [self.statement_a.id]},
            headers=self.headers_a,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['family_id'], str(self.family_a.id))
        self.assertEqual(payload['scope']['statement_ids'], [self.statement_a.id])

    def test_trigger_manual_run_rejects_cross_family_statement(self):
        account_b = Account.objects.create(name='QA B Checking', account_type=Account.AccountType.ASSET, family=self.family_b)
        product_b = FinancialProduct.objects.create(
            institution=self.institution,
            family=self.family_b,
            account=account_b,
            product_type=FinancialProduct.ProductType.CHECKING,
        )
        statement_b = BankStatementImport.objects.create(financial_product=product_b, institution=self.institution)

        response = self.client.post(
            '/quality/consistency-runs',
            json={'statement_ids': [statement_b.id]},
            headers=self.headers_a,
        )
        self.assertEqual(response.status_code, 404)


