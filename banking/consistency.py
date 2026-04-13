from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from dateutil.relativedelta import relativedelta
from django.db.models import Count, Sum

from accounting.models import JournalEntry, TransactionLine
from banking.models import BankStatementImport, StagedTransaction


@dataclass(frozen=True)
class TransactionConsistencyReport:
    statement_count: int
    staged_transaction_count: int
    journal_entry_count: int
    transaction_line_count: int
    balanced_journal_entry_count: int
    unbalanced_journal_entry_count: int
    auto_routed_count: int
    fallback_routed_count: int
    manual_review_queue_count: int
    zero_amount_unprocessed_count: int
    old_unresolved_nonzero_count: int
    predicted_but_unprocessed_nonzero_count: int
    reconciled_without_journal_entry_count: int
    recent_reconciled_without_prediction_count: int
    cutoff_date: date

    @property
    def unexpected_issue_count(self) -> int:
        return (
            self.unbalanced_journal_entry_count
            + self.old_unresolved_nonzero_count
            + self.predicted_but_unprocessed_nonzero_count
            + self.reconciled_without_journal_entry_count
        )

    @property
    def is_clean(self) -> bool:
        return self.unexpected_issue_count == 0


def _statement_ids(statement_imports: Iterable[BankStatementImport]) -> list[int]:
    if hasattr(statement_imports, "values_list"):
        return list(statement_imports.values_list("id", flat=True))
    return [stmt.id for stmt in statement_imports]


def build_transaction_consistency_report(
    statement_imports: Iterable[BankStatementImport],
) -> TransactionConsistencyReport:
    statement_ids = _statement_ids(statement_imports)
    cutoff_date = date.today() - relativedelta(months=3)

    staged_qs = StagedTransaction.objects.filter(statement_import_id__in=statement_ids)
    journal_qs = JournalEntry.objects.filter(staged_transactions__statement_import_id__in=statement_ids).distinct()
    line_qs = TransactionLine.objects.filter(journal_entry__staged_transactions__statement_import_id__in=statement_ids).distinct()

    journal_stats = journal_qs.annotate(
        line_count=Count("lines"),
        line_total=Sum("lines__amount"),
    )

    balanced_journal_entry_count = journal_stats.filter(
        line_count=2,
        line_total=Decimal("0.00"),
    ).count()

    return TransactionConsistencyReport(
        statement_count=len(statement_ids),
        staged_transaction_count=staged_qs.count(),
        journal_entry_count=journal_qs.count(),
        transaction_line_count=line_qs.count(),
        balanced_journal_entry_count=balanced_journal_entry_count,
        unbalanced_journal_entry_count=journal_qs.count() - balanced_journal_entry_count,
        auto_routed_count=staged_qs.filter(
            status=StagedTransaction.Status.RECONCILED,
            predicted_account__isnull=False,
        ).count(),
        fallback_routed_count=staged_qs.filter(
            status=StagedTransaction.Status.RECONCILED,
            predicted_account__isnull=True,
            bank_date__lt=cutoff_date,
            journal_entry__isnull=False,
        ).count(),
        manual_review_queue_count=staged_qs.filter(
            status=StagedTransaction.Status.UNPROCESSED,
            bank_date__gte=cutoff_date,
        ).count(),
        zero_amount_unprocessed_count=staged_qs.filter(
            status=StagedTransaction.Status.UNPROCESSED,
            amount=Decimal("0.00"),
        ).count(),
        old_unresolved_nonzero_count=staged_qs.filter(
            status=StagedTransaction.Status.UNPROCESSED,
            bank_date__lt=cutoff_date,
        ).exclude(amount=Decimal("0.00")).count(),
        predicted_but_unprocessed_nonzero_count=staged_qs.filter(
            status=StagedTransaction.Status.UNPROCESSED,
            predicted_account__isnull=False,
        ).exclude(amount=Decimal("0.00")).count(),
        reconciled_without_journal_entry_count=staged_qs.filter(
            status=StagedTransaction.Status.RECONCILED,
            journal_entry__isnull=True,
        ).count(),
        recent_reconciled_without_prediction_count=staged_qs.filter(
            status=StagedTransaction.Status.RECONCILED,
            predicted_account__isnull=True,
            bank_date__gte=cutoff_date,
        ).count(),
        cutoff_date=cutoff_date,
    )


def render_transaction_consistency_report(report: TransactionConsistencyReport) -> list[str]:
    return [
        "Consistency analysis (transaction processing):",
        f"  Scope statements: {report.statement_count}",
        f"  Cutoff date (3 months): {report.cutoff_date}",
        f"  Staged transactions: {report.staged_transaction_count}",
        f"  Journal entries: {report.journal_entry_count}",
        f"  Transaction lines: {report.transaction_line_count}",
        f"  Balanced journal entries: {report.balanced_journal_entry_count}",
        f"  Unbalanced journal entries: {report.unbalanced_journal_entry_count}",
        f"  Auto-routed by rule: {report.auto_routed_count}",
        f"  Fallback-routed older than 3 months: {report.fallback_routed_count}",
        f"  Manual review queue (recent unprocessed): {report.manual_review_queue_count}",
        f"  Zero-amount unprocessed exceptions: {report.zero_amount_unprocessed_count}",
        f"  Old unresolved non-zero rows: {report.old_unresolved_nonzero_count}",
        f"  Predicted but still unprocessed (non-zero): {report.predicted_but_unprocessed_nonzero_count}",
        f"  Reconciled staged tx without journal entry: {report.reconciled_without_journal_entry_count}",
        f"  Recent manual approvals without prediction: {report.recent_reconciled_without_prediction_count}",
    ]

