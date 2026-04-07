from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from users.models import Family
from .models import AnnuitySchedule, AnnuityRateHistory
from .services import AnnuityService
from .schemas import ScenarioSpec, ScenarioType, PaymentFrequencyIn

class AnnuityRateHistoryTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Asset Family")
        self.spec = ScenarioSpec(
            name="Test Schedule",
            type=ScenarioType.LOAN_AMORTIZATION,
            principal=Decimal("100000.00"),
            annual_rate=Decimal("5.0000"),
            amortization_years=25,
            payment_frequency=PaymentFrequencyIn.MONTHLY,
            start_date=date(2026, 1, 1)
        )

    def test_commit_schedule_creates_rate_history(self):
        schedule = AnnuityService.commit_schedule(self.family, self.spec)
        
        self.assertEqual(AnnuityRateHistory.objects.filter(annuity_schedule=schedule).count(), 1)
        history = AnnuityRateHistory.objects.get(annuity_schedule=schedule)
        self.assertEqual(history.annual_rate, Decimal("5.0000"))
        self.assertEqual(history.effective_date, self.spec.start_date)

    def test_current_rate_queries_most_recent_history(self):
        schedule = AnnuityService.commit_schedule(self.family, self.spec)
        
        # Add a newer rate
        new_date = date(2026, 2, 1)
        new_rate = Decimal("6.5000")
        AnnuityRateHistory.objects.create(
            annuity_schedule=schedule,
            effective_date=new_date,
            annual_rate=new_rate
        )
        
        self.assertEqual(schedule.current_rate, new_rate)

    def test_current_rate_falls_back_to_static_field(self):
        # Create schedule manually without history
        schedule = AnnuitySchedule.objects.create(
            family=self.family,
            name="Manual Schedule",
            schedule_type=AnnuitySchedule.ScheduleType.LOAN_AMORTIZATION,
            principal_amount=Decimal("100000.00"),
            annual_rate=Decimal("4.0000"),
            n_periods=300,
            payment_frequency=AnnuitySchedule.Frequency.MONTHLY,
            start_date=date(2026, 1, 1),
            computed_payment=Decimal("500.00")
        )
        
        self.assertEqual(schedule.current_rate, Decimal("4.0000"))
