from ninja import Schema
from decimal import Decimal
from datetime import date
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
    start_date: date
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
    delta_vs_baseline: Optional[Decimal] = None   # difference in monthly PMT vs first scenario
    schedule: List[PeriodRow]
