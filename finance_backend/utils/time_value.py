from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import List, Dict, Any


class PaymentFrequency(str, Enum):
    DAILY = 'DAILY'
    WEEKLY = 'WEEKLY'
    BIWEEKLY = 'BIWEEKLY'
    MONTHLY = 'MONTHLY'
    ANNUALLY = 'ANNUALLY'


def compute_n_periods(target_date: date, frequency: PaymentFrequency, start_date: date = None) -> int:
    """
    Calculates "n" (number of periods) for actuarial formulas to figure out
    required funding PMTs to hit specific milestone dates.
    """
    if start_date is None:
        start_date = date.today()

    if target_date <= start_date:
        return 0

    if frequency in [PaymentFrequency.DAILY, PaymentFrequency.WEEKLY, PaymentFrequency.BIWEEKLY]:
        delta_days = (target_date - start_date).days

        if frequency == PaymentFrequency.DAILY:
            return delta_days
        elif frequency == PaymentFrequency.WEEKLY:
            return delta_days // 7
        elif frequency == PaymentFrequency.BIWEEKLY:
            return delta_days // 14

    elif frequency in [PaymentFrequency.MONTHLY, PaymentFrequency.ANNUALLY]:
        delta = relativedelta(target_date, start_date)
        total_months = (delta.years * 12) + delta.months

        if frequency == PaymentFrequency.MONTHLY:
            return total_months
        elif frequency == PaymentFrequency.ANNUALLY:
            return delta.years

    return 0


def _period_rate(annual_rate: Decimal, frequency: PaymentFrequency) -> Decimal:
    """Convert annual percentage rate to per-period rate."""
    rate = annual_rate / Decimal('100')
    if frequency == PaymentFrequency.MONTHLY:
        return rate / Decimal('12')
    elif frequency == PaymentFrequency.BIWEEKLY:
        return rate / Decimal('26')
    elif frequency == PaymentFrequency.WEEKLY:
        return rate / Decimal('52')
    elif frequency == PaymentFrequency.ANNUALLY:
        return rate
    elif frequency == PaymentFrequency.DAILY:
        return rate / Decimal('365')
    return rate / Decimal('12')


def compute_pmt_loan(
    pv: Decimal,
    annual_rate: Decimal,
    n_periods: int,
    frequency: PaymentFrequency = PaymentFrequency.MONTHLY,
) -> Decimal:
    """
    Payment required to fully amortize a loan (present value annuity).
    PMT = PV * r / (1 - (1+r)^-n)
    """
    if n_periods <= 0:
        return Decimal('0')
    r = _period_rate(annual_rate, frequency)
    if r == 0:
        return (pv / n_periods).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    pmt = pv * r / (1 - (1 + r) ** -n_periods)
    return pmt.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def compute_pmt_sinking_fund(
    fv: Decimal,
    annual_rate: Decimal,
    n_periods: int,
    frequency: PaymentFrequency = PaymentFrequency.MONTHLY,
) -> Decimal:
    """
    Periodic contribution required to accumulate a future value (future value annuity).
    PMT = FV * r / ((1+r)^n - 1)
    """
    if n_periods <= 0:
        return Decimal('0')
    r = _period_rate(annual_rate, frequency)
    if r == 0:
        return (fv / n_periods).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    pmt = fv * r / ((1 + r) ** n_periods - 1)
    return pmt.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _advance_date(d: date, frequency: PaymentFrequency) -> date:
    if frequency == PaymentFrequency.MONTHLY:
        return d + relativedelta(months=1)
    elif frequency == PaymentFrequency.BIWEEKLY:
        return d + relativedelta(weeks=2)
    elif frequency == PaymentFrequency.WEEKLY:
        return d + relativedelta(weeks=1)
    elif frequency == PaymentFrequency.ANNUALLY:
        return d + relativedelta(years=1)
    elif frequency == PaymentFrequency.DAILY:
        return d + relativedelta(days=1)
    return d + relativedelta(months=1)


def generate_amortization_schedule(
    principal: Decimal,
    annual_rate: Decimal,
    n_periods: int,
    start_date: date,
    frequency: PaymentFrequency = PaymentFrequency.MONTHLY,
) -> List[Dict[str, Any]]:
    """
    Full amortization schedule for a loan.
    Each row: period_number, payment_date, payment_amount,
              interest_portion, principal_portion, balance_after.
    """
    pmt = compute_pmt_loan(principal, annual_rate, n_periods, frequency)
    r = _period_rate(annual_rate, frequency)
    balance = principal
    schedule = []
    payment_date = _advance_date(start_date, frequency)

    for i in range(1, n_periods + 1):
        interest = (balance * r).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        principal_portion = (pmt - interest).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Last period: clear residual rounding
        if i == n_periods:
            principal_portion = balance
            pmt = interest + principal_portion

        balance = max(balance - principal_portion, Decimal('0'))

        schedule.append({
            'period_number': i,
            'payment_date': payment_date,
            'payment_amount': (interest + principal_portion).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'interest_portion': interest,
            'principal_portion': principal_portion,
            'balance_after': balance,
        })

        payment_date = _advance_date(payment_date, frequency)

    return schedule


def generate_sinking_fund_schedule(
    target: Decimal,
    annual_rate: Decimal,
    n_periods: int,
    start_date: date,
    current_balance: Decimal = Decimal('0'),
    frequency: PaymentFrequency = PaymentFrequency.MONTHLY,
) -> List[Dict[str, Any]]:
    """
    Sinking fund accumulation schedule.
    Each row: period_number, payment_date, contribution,
              interest_earned, balance_after.
    """
    remaining = target - current_balance
    if remaining <= 0:
        return []

    pmt = compute_pmt_sinking_fund(remaining, annual_rate, n_periods, frequency)
    r = _period_rate(annual_rate, frequency)
    balance = current_balance
    schedule = []
    payment_date = _advance_date(start_date, frequency)

    for i in range(1, n_periods + 1):
        interest_earned = (balance * r).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        balance = balance + pmt + interest_earned

        schedule.append({
            'period_number': i,
            'payment_date': payment_date,
            'payment_amount': pmt,
            'interest_portion': interest_earned,
            'principal_portion': pmt,
            'balance_after': balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        })

        payment_date = _advance_date(payment_date, frequency)

    return schedule
