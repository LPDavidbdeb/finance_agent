from ninja import Router
from typing import List
from decimal import Decimal

from .schemas import ScenarioSpec, ScenarioResult, PeriodRow, ScenarioType, PaymentFrequencyIn
from finance_backend.utils.time_value import (
    PaymentFrequency,
    compute_pmt_loan,
    compute_pmt_sinking_fund,
    generate_amortization_schedule,
    generate_sinking_fund_schedule,
)

router = Router(tags=["Planning"])

_FREQ_MAP = {
    PaymentFrequencyIn.MONTHLY: PaymentFrequency.MONTHLY,
    PaymentFrequencyIn.BIWEEKLY: PaymentFrequency.BIWEEKLY,
    PaymentFrequencyIn.WEEKLY: PaymentFrequency.WEEKLY,
    PaymentFrequencyIn.ANNUALLY: PaymentFrequency.ANNUALLY,
}

_PERIODS_PER_YEAR = {
    PaymentFrequency.MONTHLY: 12,
    PaymentFrequency.BIWEEKLY: 26,
    PaymentFrequency.WEEKLY: 52,
    PaymentFrequency.ANNUALLY: 1,
}


@router.post("/simulate", response=List[ScenarioResult])
def simulate(request, scenarios: List[ScenarioSpec]):
    """
    Stateless simulation: given N scenario specs, compute and return N amortization results.
    No DB writes. The client can call this repeatedly as the user tweaks inputs.
    """
    results: List[ScenarioResult] = []
    baseline_pmt: Decimal | None = None

    for spec in scenarios:
        freq = _FREQ_MAP[spec.payment_frequency]
        periods_per_year = _PERIODS_PER_YEAR[freq]
        n = spec.amortization_years * periods_per_year

        if spec.type == ScenarioType.LOAN_AMORTIZATION:
            pmt = compute_pmt_loan(spec.principal, spec.annual_rate, n, freq)
            schedule_dicts = generate_amortization_schedule(
                spec.principal, spec.annual_rate, n, spec.start_date, freq
            )
        else:  # SINKING_FUND
            current_balance = spec.current_balance or Decimal('0')
            pmt = compute_pmt_sinking_fund(
                spec.principal - current_balance, spec.annual_rate, n, freq
            )
            schedule_dicts = generate_sinking_fund_schedule(
                spec.principal, spec.annual_rate, n, spec.start_date, current_balance, freq
            )

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
            fcf_impact_monthly=-pmt if spec.type == ScenarioType.LOAN_AMORTIZATION else -pmt,
            delta_vs_baseline=(pmt - baseline_pmt) if pmt != baseline_pmt else None,
            schedule=schedule,
        ))

    return results
