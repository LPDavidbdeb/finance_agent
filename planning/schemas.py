from ninja import Schema
from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional
from enum import Enum


class ScenarioType(str, Enum):
    LOAN_AMORTIZATION = 'LOAN_AMORTIZATION'
    SINKING_FUND = 'SINKING_FUND'


class PaymentFrequencyIn(str, Enum):
    MONTHLY = 'MONTHLY'
    BIWEEKLY = 'BIWEEKLY'
    WEEKLY = 'WEEKLY'
    ANNUALLY = 'ANNUALLY'


class ScenarioSpec(Schema):
    name: str
    type: ScenarioType = ScenarioType.LOAN_AMORTIZATION
    principal: Decimal                     # PV for loan; FV target for sinking fund
    annual_rate: Decimal                   # percentage, e.g. 4.5 means 4.5%
    amortization_years: int
    payment_frequency: PaymentFrequencyIn = PaymentFrequencyIn.MONTHLY
    start_date: date                       # loan origination date; payments flow from here
    current_balance: Optional[Decimal] = Decimal('0')   # sinking fund only


class PeriodRow(Schema):
    period_number: int
    payment_date: date
    payment_amount: Decimal
    interest_portion: Decimal
    principal_portion: Decimal
    balance_after: Decimal


class ScenarioResult(Schema):
    name: str
    type: ScenarioType
    payment_amount: Decimal
    total_interest_paid: Decimal
    total_cost: Decimal
    fcf_impact_monthly: Decimal
    delta_vs_baseline: Optional[Decimal] = None
    schedule: List[PeriodRow]


# ── Persisted schedule schemas ────────────────────────────────────────────────

class CommitIn(Schema):
    """Commit a scenario to a persisted AnnuitySchedule."""
    spec: ScenarioSpec
    linked_journal_entry_id: Optional[int] = None   # originating lump-sum JE, if known


class AnnuityPeriodOut(Schema):
    id: int
    period_number: int
    payment_date: date
    payment_amount: Decimal
    interest_portion: Decimal
    principal_portion: Decimal
    balance_after: Decimal
    is_paid: bool
    journal_entry_id: Optional[int] = None


class AnnuityScheduleOut(Schema):
    id: int
    name: str
    schedule_type: str
    principal_amount: Decimal
    annual_rate: Decimal
    n_periods: int
    payment_frequency: str
    start_date: date
    computed_payment: Decimal
    linked_journal_entry_id: Optional[int] = None
    created_at: datetime
    periods: List[AnnuityPeriodOut] = []


class AnnuityScheduleListOut(Schema):
    id: int
    name: str
    schedule_type: str
    principal_amount: Decimal
    annual_rate: Decimal
    n_periods: int
    payment_frequency: str
    start_date: date
    computed_payment: Decimal
    created_at: datetime
