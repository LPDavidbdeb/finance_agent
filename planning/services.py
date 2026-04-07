from decimal import Decimal
from typing import List, Dict, Any
from django.db import transaction
from .models import AnnuitySchedule, AnnuityRateHistory, AnnuityPeriod
from .schemas import ScenarioSpec, ScenarioType, PaymentFrequencyIn
from finance_backend.utils.time_value import (
    PaymentFrequency,
    compute_pmt_loan,
    compute_pmt_sinking_fund,
    generate_amortization_schedule,
    generate_sinking_fund_schedule,
)

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

class AnnuityService:
    @staticmethod
    def compute_scenario(spec: ScenarioSpec) -> tuple[Decimal, List[Dict[str, Any]], int]:
        """Return (pmt, schedule_dicts, n_periods) for a scenario spec."""
        freq = _FREQ_MAP[spec.payment_frequency]
        n = spec.amortization_years * _PERIODS_PER_YEAR[freq]

        if spec.type == ScenarioType.LOAN_AMORTIZATION:
            pmt = compute_pmt_loan(spec.principal, spec.annual_rate, n, freq)
            schedule_dicts = generate_amortization_schedule(
                spec.principal, spec.annual_rate, n, spec.start_date, freq
            )
        else:
            current_balance = spec.current_balance or Decimal('0')
            pmt = compute_pmt_sinking_fund(
                spec.principal - current_balance, spec.annual_rate, n, freq
            )
            schedule_dicts = generate_sinking_fund_schedule(
                spec.principal, spec.annual_rate, n, spec.start_date, current_balance, freq
            )

        return pmt, schedule_dicts, n

    @staticmethod
    @transaction.atomic
    def commit_schedule(family, spec: ScenarioSpec, linked_je=None) -> AnnuitySchedule:
        """
        Persist AnnuitySchedule, its initial rate history, and all AnnuityPeriod rows.
        """
        pmt, schedule_dicts, n_periods = AnnuityService.compute_scenario(spec)

        schedule = AnnuitySchedule.objects.create(
            family=family,
            name=spec.name,
            schedule_type=spec.type.value,
            principal_amount=spec.principal,
            annual_rate=spec.annual_rate,  # Initial rate
            n_periods=n_periods,
            payment_frequency=spec.payment_frequency.value,
            start_date=spec.start_date,
            computed_payment=pmt,
            linked_journal_entry=linked_je,
        )

        # Create initial rate history
        AnnuityRateHistory.objects.create(
            annuity_schedule=schedule,
            effective_date=spec.start_date,
            annual_rate=spec.annual_rate
        )

        AnnuityPeriod.objects.bulk_create([
            AnnuityPeriod(
                schedule=schedule,
                period_number=row['period_number'],
                payment_date=row['payment_date'],
                payment_amount=row['payment_amount'],
                interest_portion=row['interest_portion'],
                principal_portion=row['principal_portion'],
                balance_after=row['balance_after'],
            )
            for row in schedule_dicts
        ])

        return schedule
