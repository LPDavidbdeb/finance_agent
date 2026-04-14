from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from banking.consistency import TransactionConsistencyReport
from banking.models import BankStatementImport, StagedTransaction
from users.models import Family

from .models import ConsistencyReportFinding, ConsistencyReportRun


def _json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def serialize_report(report: TransactionConsistencyReport) -> dict[str, Any]:
    return _json_safe(asdict(report))


def build_default_findings(report: TransactionConsistencyReport) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    if report.unbalanced_journal_entry_count:
        findings.append(
            {
                'severity': ConsistencyReportFinding.Severity.ERROR,
                'category': 'UNBALANCED_JOURNAL_ENTRY',
                'title': 'Unbalanced journal entries detected',
                'message': 'One or more journal entries do not sum to zero.',
                'details': {'count': report.unbalanced_journal_entry_count},
            }
        )

    if report.reconciled_without_journal_entry_count:
        findings.append(
            {
                'severity': ConsistencyReportFinding.Severity.ERROR,
                'category': 'RECONCILED_WITHOUT_JOURNAL_ENTRY',
                'title': 'Reconciled staged transactions missing a journal entry',
                'message': 'At least one reconciled staged transaction has no linked journal entry.',
                'details': {'count': report.reconciled_without_journal_entry_count},
            }
        )

    if report.old_unresolved_nonzero_count:
        findings.append(
            {
                'severity': ConsistencyReportFinding.Severity.WARNING,
                'category': 'OLD_UNRESOLVED_NONZERO',
                'title': 'Old unresolved non-zero staged transactions',
                'message': 'Some staged transactions older than the fallback cutoff remain unresolved.',
                'details': {'count': report.old_unresolved_nonzero_count, 'cutoff_date': report.cutoff_date.isoformat()},
            }
        )

    if report.predicted_but_unprocessed_nonzero_count:
        findings.append(
            {
                'severity': ConsistencyReportFinding.Severity.WARNING,
                'category': 'PREDICTED_BUT_UNPROCESSED',
                'title': 'Predicted transactions left unprocessed',
                'message': 'Some transactions were routed by prediction but still remain unprocessed.',
                'details': {'count': report.predicted_but_unprocessed_nonzero_count},
            }
        )

    if report.zero_amount_unprocessed_count:
        findings.append(
            {
                'severity': ConsistencyReportFinding.Severity.INFO,
                'category': 'ZERO_AMOUNT_UNPROCESSED',
                'title': 'Zero-amount staged transactions present',
                'message': 'Zero-amount rows remain available for investigation or explicit dismissal.',
                'details': {'count': report.zero_amount_unprocessed_count},
            }
        )

    return findings


def _run_cutoff_date(run: ConsistencyReportRun) -> date:
    cutoff_value = (run.summary or {}).get('cutoff_date')
    if isinstance(cutoff_value, str):
        try:
            return date.fromisoformat(cutoff_value)
        except ValueError:
            pass
    return date.today()


def build_old_unresolved_transactions(run: ConsistencyReportRun) -> list[dict[str, Any]]:
    statement_ids = list((run.scope or {}).get('statement_ids') or [])
    if statement_ids:
        statement_qs = BankStatementImport.objects.filter(
            id__in=statement_ids,
        ).filter(
            Q(financial_product__family=run.family)
            | Q(financial_product__isnull=True, institution__products__family=run.family)
        ).distinct()
    else:
        statement_qs = BankStatementImport.objects.filter(
            Q(financial_product__family=run.family)
            | Q(financial_product__isnull=True, institution__products__family=run.family)
        ).distinct()

    cutoff_date = _run_cutoff_date(run)
    transactions = (
        StagedTransaction.objects.filter(
            statement_import__in=statement_qs,
            status=StagedTransaction.Status.UNPROCESSED,
            bank_date__lt=cutoff_date,
        )
        .exclude(amount=Decimal('0.00'))
        .select_related('statement_import', 'financial_product', 'predicted_account', 'journal_entry')
        .order_by('bank_date', 'id')
    )

    return [
        {
            'id': tx.id,
            'statement_import_id': tx.statement_import_id,
            'statement_import_label': str(tx.statement_import),
            'financial_product_id': tx.financial_product_id,
            'bank_date': tx.bank_date,
            'raw_description': tx.raw_description,
            'amount': str(tx.amount),
            'status': tx.status,
            'predicted_account_id': tx.predicted_account_id,
            'journal_entry_id': tx.journal_entry_id,
            'cutoff_date': cutoff_date,
            'days_past_cutoff': (date.today() - tx.bank_date).days,
        }
        for tx in transactions
    ]


@transaction.atomic
def create_consistency_report_run(
    *,
    family: Family,
    trigger_source: str,
    report: TransactionConsistencyReport,
    scope: dict[str, Any] | None = None,
    findings: Iterable[dict[str, Any]] | None = None,
    status: str = ConsistencyReportRun.Status.COMPLETED,
    error_message: str = '',
) -> ConsistencyReportRun:
    run = ConsistencyReportRun.objects.create(
        family=family,
        trigger_source=trigger_source,
        status=ConsistencyReportRun.Status.PENDING,
        scope=_json_safe(scope or {}),
        summary=serialize_report(report),
        error_message=error_message,
        finished_at=timezone.now(),
    )

    rendered_findings = list(findings) if findings is not None else build_default_findings(report)
    if rendered_findings:
        ConsistencyReportFinding.objects.bulk_create(
            [
                ConsistencyReportFinding(run=run, **finding)
                for finding in rendered_findings
            ]
        )

    run.status = status
    run.save(update_fields=['status'])
    return run

