from ninja import Router
from ninja.errors import HttpError
from django.db import transaction
from django.shortcuts import get_object_or_404
from typing import List
from decimal import Decimal

from .schemas import (
    ScenarioSpec, ScenarioResult, PeriodRow, ScenarioType, PaymentFrequencyIn,
    CommitIn, AnnuityScheduleOut, AnnuityScheduleListOut, AnnuityPeriodOut,
)
from .models import AnnuitySchedule, AnnuityPeriod
from .services import AnnuityService

router = Router(tags=["Planning"])


# ── Simulation (stateless) ────────────────────────────────────────────────────

@router.post("/simulate", response=List[ScenarioResult])
def simulate(request, scenarios: List[ScenarioSpec]):
    """
    Stateless: given N scenario specs compute and return N results.
    No DB writes — call repeatedly as the user tweaks inputs.
    """
    results: List[ScenarioResult] = []
    baseline_pmt: Decimal | None = None

    for spec in scenarios:
        pmt, schedule_dicts, _ = AnnuityService.compute_scenario(spec)
        schedule = [PeriodRow(**row) for row in schedule_dicts]
        total_interest = sum(row.interest_portion for row in schedule)
        total_cost = sum(row.payment_amount for row in schedule)

        if baseline_pmt is None:
            baseline_pmt = pmt

        results.append(ScenarioResult(
            name=spec.name,
            type=spec.type,
            payment_amount=pmt,
            total_interest_paid=total_interest,
            total_cost=total_cost,
            fcf_impact_monthly=-pmt,
            delta_vs_baseline=(pmt - baseline_pmt) if pmt != baseline_pmt else None,
            schedule=schedule,
        ))

    return results


# ── Commit (persist) ──────────────────────────────────────────────────────────

@router.post("/schedules", response=AnnuityScheduleOut)
def commit_schedule(request, payload: CommitIn):
    """
    Commit a chosen scenario: persist AnnuitySchedule + all AnnuityPeriod rows.
    The start_date on the spec is the loan origination date; payment dates flow from it.
    """
    spec = payload.spec
    family = request.auth.family

    # Optionally validate the linked JE belongs to this family
    linked_je = None
    if payload.linked_journal_entry_id:
        from accounting.models import JournalEntry
        try:
            linked_je = JournalEntry.objects.get(
                id=payload.linked_journal_entry_id, family=family
            )
        except JournalEntry.DoesNotExist:
            raise HttpError(404, "Journal entry not found in your family.")

    schedule = AnnuityService.commit_schedule(family, spec, linked_je)

    return _schedule_to_out(schedule, include_periods=True)



@router.get("/schedules", response=List[AnnuityScheduleListOut])
def list_schedules(request):
    """List all committed schedules for this family."""
    return list(
        AnnuitySchedule.objects.filter(family=request.auth.family)
    )


@router.get("/schedules/{schedule_id}", response=AnnuityScheduleOut)
def get_schedule(request, schedule_id: int):
    """Get a specific schedule with its full period table."""
    schedule = get_object_or_404(AnnuitySchedule, id=schedule_id, family=request.auth.family)
    return _schedule_to_out(schedule, include_periods=True)


@router.delete("/schedules/{schedule_id}")
def delete_schedule(request, schedule_id: int):
    """Delete a committed schedule and all its periods."""
    schedule = get_object_or_404(AnnuitySchedule, id=schedule_id, family=request.auth.family)
    schedule.delete()
    return {"message": "Schedule deleted."}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _schedule_to_out(schedule: AnnuitySchedule, include_periods: bool = False) -> AnnuityScheduleOut:
    periods = []
    if include_periods:
        periods = [
            AnnuityPeriodOut(
                id=p.id,
                period_number=p.period_number,
                payment_date=p.payment_date,
                payment_amount=p.payment_amount,
                interest_portion=p.interest_portion,
                principal_portion=p.principal_portion,
                balance_after=p.balance_after,
                is_paid=p.is_paid,
                journal_entry_id=p.journal_entry_id,
            )
            for p in schedule.periods.all()
        ]

    return AnnuityScheduleOut(
        id=schedule.id,
        name=schedule.name,
        schedule_type=schedule.schedule_type,
        principal_amount=schedule.principal_amount,
        annual_rate=schedule.annual_rate,
        n_periods=schedule.n_periods,
        payment_frequency=schedule.payment_frequency,
        start_date=schedule.start_date,
        computed_payment=schedule.computed_payment,
        linked_journal_entry_id=schedule.linked_journal_entry_id,
        created_at=schedule.created_at,
        periods=periods,
    )
