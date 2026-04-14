from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from banking.consistency import build_transaction_consistency_report
from banking.models import BankStatementImport
from quality.models import ConsistencyReportFinding, ConsistencyReportRun
from quality.schemas import (
    ConsistencyReportFindingOut,
    ConsistencyReportRunOut,
    ConsistencyRunTransactionOut,
    ConsistencyRunTriggerIn,
)
from quality.services import build_old_unresolved_transactions, create_consistency_report_run

router = Router(auth=JWTAuth())


def _statements_for_family(family, statement_ids: list[int] | None = None):
    qs = BankStatementImport.objects.filter(
        Q(financial_product__family=family) |
        Q(financial_product__isnull=True, institution__products__family=family)
    ).distinct()
    if statement_ids:
        qs = qs.filter(id__in=statement_ids)
    return qs


@router.get('/consistency-runs', response=list[ConsistencyReportRunOut])
def list_consistency_runs(request, limit: int = 25):
    user = request.auth
    safe_limit = max(1, min(limit, 200))
    runs = (
        ConsistencyReportRun.objects.filter(family=user.family)
        .annotate(finding_count=Count('findings'))
        .order_by('-started_at', '-id')[:safe_limit]
    )
    return runs


@router.get('/consistency-runs/{run_id}', response=ConsistencyReportRunOut)
def get_consistency_run(request, run_id: int):
    user = request.auth
    return get_object_or_404(
        ConsistencyReportRun.objects.filter(family=user.family).annotate(finding_count=Count('findings')),
        id=run_id,
    )


@router.get('/consistency-runs/{run_id}/findings', response=list[ConsistencyReportFindingOut])
def list_consistency_findings(request, run_id: int, severity: str | None = None):
    user = request.auth
    run = get_object_or_404(ConsistencyReportRun, id=run_id, family=user.family)

    findings = ConsistencyReportFinding.objects.filter(run=run).order_by('id')
    if severity:
        severity_upper = severity.upper()
        allowed = {choice for choice, _ in ConsistencyReportFinding.Severity.choices}
        if severity_upper not in allowed:
            raise HttpError(400, 'Invalid severity. Allowed values: INFO, WARNING, ERROR.')
        findings = findings.filter(severity=severity_upper)

    return findings


@router.post('/consistency-runs', response=ConsistencyReportRunOut)
def trigger_consistency_run(request, payload: ConsistencyRunTriggerIn):
    user = request.auth
    statements = _statements_for_family(user.family, payload.statement_ids)

    if payload.statement_ids:
        scoped_count = statements.count()
        if scoped_count != len(set(payload.statement_ids)):
            raise HttpError(404, 'One or more statements were not found in your family scope.')

    report = build_transaction_consistency_report(statements)
    run = create_consistency_report_run(
        family=user.family,
        trigger_source=ConsistencyReportRun.TriggerSource.MANUAL,
        report=report,
        scope={'statement_ids': list(statements.values_list('id', flat=True))},
    )

    return (
        ConsistencyReportRun.objects.filter(id=run.id)
        .annotate(finding_count=Count('findings'))
        .get()
    )


@router.get('/consistency-runs/{run_id}/unresolved-transactions', response=list[ConsistencyRunTransactionOut])
def list_old_unresolved_transactions(request, run_id: int):
    user = request.auth
    run = get_object_or_404(ConsistencyReportRun, id=run_id, family=user.family)
    return build_old_unresolved_transactions(run)


