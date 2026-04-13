from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from users.models import Family
from .models import AnnuitySchedule, AnnuityPeriod, AnnuityRateHistory
from .services import AnnuityService
from .schemas import ScenarioSpec, ScenarioType, PaymentFrequencyIn
from categorization.models import TransactionMappingRule

class DynamicReamortizationTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Reamortization Family")
        
        # 1. Create a 12-month loan at 5%
        self.spec = ScenarioSpec(
            name="Small Loan",
            type=ScenarioType.LOAN_AMORTIZATION,
            principal=Decimal("1200.00"),
            annual_rate=Decimal("5.0000"),
            amortization_years=1, # 12 months
            payment_frequency=PaymentFrequencyIn.MONTHLY,
            start_date=date(2026, 1, 1)
        )
        self.schedule = AnnuityService.commit_schedule(self.family, self.spec)
        self.initial_payment = self.schedule.computed_payment
        
        # Verify initial rule exists
        self.rule = TransactionMappingRule.objects.get(linked_schedule=self.schedule)
        self.assertAlmostEqual(self.rule.max_amount, self.initial_payment + Decimal("5.00"))

    def test_dynamic_reamortization_on_new_rate(self):
        """
        Edge Case Test:
        1. Mark first 3 periods as paid.
        2. Insert new rate history (effective month 4).
        3. Assert paid periods untouched, tail regenerated, rule updated.
        """
        # 1. Mark periods 1, 2, 3 as paid
        paid_periods = self.schedule.periods.filter(period_number__lte=3)
        paid_periods.update(is_paid=True)
        
        # Capture state of period 3 balance_after
        p3 = self.schedule.periods.get(period_number=3)
        p3_balance = p3.balance_after
        p3_id = p3.id
        
        # 2. Add new rate history starting at month 4 (2026-04-01)
        # Old rate was 5%, new rate is 10%
        new_rate = Decimal("10.0000")
        effective_date = date(2026, 4, 1)
        
        # This should trigger the signal -> AnnuityService.recalculate_schedule
        AnnuityRateHistory.objects.create(
            annuity_schedule=self.schedule,
            effective_date=effective_date,
            annual_rate=new_rate
        )
        
        # Refresh state
        self.schedule.refresh_from_db()
        self.rule.refresh_from_db()
        
        # ASSERTIONS
        
        # A. Paid periods 1-3 remain strictly untouched (same IDs and count)
        remaining_paid = self.schedule.periods.filter(is_paid=True).order_by('period_number')
        self.assertEqual(remaining_paid.count(), 3)
        self.assertEqual(list(remaining_paid.values_list('id', flat=True)), [p.id for p in paid_periods])
        
        # B. Period 4 and beyond are regenerated with NEW payment amount
        new_payment = self.schedule.computed_payment
        self.assertNotEqual(new_payment, self.initial_payment)
        
        # Verify period 4 uses the new payment
        p4 = self.schedule.periods.get(period_number=4)
        self.assertEqual(p4.payment_amount, new_payment)
        self.assertEqual(p4.payment_date, date(2026, 5, 1))
        
        # C. Mapping rule bounds are successfully updated
        variance = Decimal("5.00")
        self.assertEqual(self.rule.min_amount, new_payment - variance)
        self.assertEqual(self.rule.max_amount, new_payment + variance)
        
        # D. The math still makes sense (final balance is 0)
        last_period = self.schedule.periods.order_by('period_number').last()
        self.assertEqual(last_period.period_number, 12)
        self.assertEqual(last_period.balance_after, Decimal("0.00"))
