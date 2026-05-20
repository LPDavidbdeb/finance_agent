from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from django.db import transaction, models
from .models import AnnuitySchedule, AnnuityRateHistory, AnnuityPeriod
from .schemas import ScenarioSpec, ScenarioType, PaymentFrequencyIn
from accounting.models import Account, JournalEntry, TransactionLine
import logging
from finance_backend.utils.time_value import (
    PaymentFrequency,
    compute_pmt_loan,
    compute_pmt_sinking_fund,
    generate_amortization_schedule,
    generate_sinking_fund_schedule,
)


class ReconciliationError(Exception):
    """Domain error for amortization reconciliation failures."""
    pass

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
        # This will trigger the trigger_reamortization signal, which calls recalculate_schedule
        # to generate the initial set of AnnuityPeriod rows.
        AnnuityRateHistory.objects.create(
            annuity_schedule=schedule,
            effective_date=spec.start_date,
            annual_rate=spec.annual_rate
        )

        return schedule

    @staticmethod
    @transaction.atomic
    def recalculate_schedule(schedule: AnnuitySchedule, effective_date: date, new_rate: Decimal):
        """
        Phase 5: Dynamic Re-Amortization.
        Determines remaining balance and regenerates the tail of the schedule.
        """
        # 1. Identify the last period that MUST stay.
        # This is the last period that is either PAID or is UNPAID but occurs BEFORE the new rate takes effect.
        last_staying_period = schedule.periods.filter(
            models.Q(is_paid=True) | models.Q(payment_date__lt=effective_date)
        ).order_by('-period_number').first()

        if last_staying_period:
            remaining_principal = last_staying_period.balance_after
            last_period_num = last_staying_period.period_number
            last_payment_date = last_staying_period.payment_date
        else:
            remaining_principal = schedule.principal_amount
            last_period_num = 0
            last_payment_date = schedule.start_date

        # 2. Delete all future, unpaid periods that are being replaced
        schedule.periods.filter(
            is_paid=False,
            payment_date__gte=effective_date
        ).delete()

        # 3. Regenerate remaining periods
        remaining_n = schedule.n_periods - last_period_num
        if remaining_n <= 0:
            return

        freq = PaymentFrequency(schedule.payment_frequency)
        
        # Generate the remaining tail using the new rate
        new_rows = generate_amortization_schedule(
            remaining_principal,
            new_rate,
            remaining_n,
            last_payment_date,
            freq
        )

        AnnuityPeriod.objects.bulk_create([
            AnnuityPeriod(
                schedule=schedule,
                period_number=last_period_num + row['period_number'],
                payment_date=row['payment_date'],
                payment_amount=row['payment_amount'],
                interest_portion=row['interest_portion'],
                principal_portion=row['principal_portion'],
                balance_after=row['balance_after'],
            )
            for row in new_rows
        ])

        # 4. Update Schedule metadata and linked mapping rules
        if new_rows:
            new_pmt = new_rows[0]['payment_amount']
            schedule.computed_payment = new_pmt
            schedule.save(update_fields=['computed_payment'])

            # Success Criteria: Update TransactionMappingRule bounds +/- $5.00
            variance = Decimal("5.00")
            schedule.mapping_rules.all().update(
                min_amount=new_pmt - variance,
                max_amount=new_pmt + variance
            )

class AmortizationReconciliationService:
    @staticmethod
    @transaction.atomic
    def reconcile_amortization_payment(staged_tx, rule, user, schedule_override=None) -> Optional[JournalEntry]:
        """
        Phase 4: Payment Stripping.
        Matches a StagedTransaction to an AnnuityPeriod and creates a 3-line compound entry.
        schedule_override: explicit schedule (used when the link is on Merchant rather than Rule).
        """
        schedule = schedule_override or rule.linked_schedule
        if not schedule:
            return None

        # 1. Find the oldest unpaid AnnuityPeriod within ± 5-day window
        window_start = staged_tx.bank_date - timedelta(days=5)
        window_end = staged_tx.bank_date + timedelta(days=5)
        
        period = schedule.periods.filter(
            is_paid=False,
            payment_date__range=(window_start, window_end)
        ).order_by('period_number').first()
        
        if not period:
            return None

        # 2. Identify accounts
        resolved_product = staged_tx.financial_product or staged_tx.statement_import.financial_product
        source_account = resolved_product.account
        family = resolved_product.family

        # Liability Account (from schedule's originating JE)
        orig_je = schedule.linked_journal_entry
        if not orig_je:
            # Fallback: find any liability account linked to tangible assets of this schedule
            from assets.models import TangibleAsset
            asset = TangibleAsset.objects.filter(annuity_schedule=schedule).first()
            if asset:
                # This is actually an ASSET account. We need the liability one.
                # If no linked_je, we might have to search for a liability account with similar name?
                # For now, we enforce linked_je exists as per Phase 2.
                raise ValueError(f"Schedule {schedule.id} has no linked originating journal entry.")
            else:
                raise ValueError(f"Schedule {schedule.id} has no linked originating journal entry.")
        
        liability_line = orig_je.lines.filter(account__account_type=Account.AccountType.LIABILITY).first()
        if not liability_line:
            raise ValueError(f"Originating JE for schedule {schedule.id} has no liability account line.")
        liability_account = liability_line.account
        
        # Interest Expense Account
        # Prioritize accounts linked to this family over global ones.
        interest_account = Account.objects.filter(
            models.Q(family=family) | models.Q(family__isnull=True),
            account_type=Account.AccountType.EXPENSE,
            name__icontains='interest'
        ).annotate(
            is_family_specific=models.Case(
                models.When(family=family, then=models.Value(1)),
                default=models.Value(0),
                output_field=models.IntegerField(),
            )
        ).order_by('-is_family_specific', 'id').first()
        if not interest_account:
            # Try a common name fallback
            interest_account = Account.objects.filter(name__icontains='Mortgage interest cost', family=family).first()
        if not interest_account:
            # As a safe fallback, auto-create a family-scoped interest expense account.
            logger = logging.getLogger(__name__)
            interest_account = Account.objects.create(
                name='Interest expense',
                account_type=Account.AccountType.EXPENSE,
                family=family
            )
            logger.info("Auto-created interest expense account %s for family %s", interest_account.id, family.id)

        # 3. Construct the 3-line compound JournalEntry
        journal_entry = JournalEntry.objects.create(
            family=family,
            date=staged_tx.bank_date,
            description=f"Loan Payment: {schedule.name} (Period {period.period_number})",
            is_reconciled=True
        )

        # Line 1: Credit (-) the Bank Account (Total payment amount)
        # Note: staged_tx.amount is negative for outflows in Assets
        total_payment = abs(staged_tx.amount)
        TransactionLine.objects.create(
            journal_entry=journal_entry,
            account=source_account,
            amount=-total_payment
        )

        # Line 2: Debit (+) the Liability Account (Principal portion)
        TransactionLine.objects.create(
            journal_entry=journal_entry,
            account=liability_account,
            amount=period.principal_portion
        )

        # Line 3: Debit (+) the Interest Expense Account (Interest portion)
        TransactionLine.objects.create(
            journal_entry=journal_entry,
            account=interest_account,
            amount=period.interest_portion
        )

        # 4. State Update
        period.is_paid = True
        period.journal_entry = journal_entry
        period.save(update_fields=['is_paid', 'journal_entry'])

        staged_tx.status = staged_tx.Status.RECONCILED
        staged_tx.journal_entry = journal_entry
        staged_tx.merchant = rule.merchant
        staged_tx.save(update_fields=['status', 'journal_entry', 'merchant'])

        return journal_entry
