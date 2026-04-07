from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja_jwt.tokens import AccessToken

from planning.models import AnnuitySchedule, AnnuityPeriod
from users.models import Family

User = get_user_model()


class PlanningScheduleApiContractTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Planning Family")
        self.user = User.objects.create_user(
            email="planning@example.com",
            password="password",
            family=self.family,
        )
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(self.user)}"}

        self.schedule = AnnuitySchedule.objects.create(
            family=self.family,
            name="Mortgage 25y",
            schedule_type=AnnuitySchedule.ScheduleType.LOAN_AMORTIZATION,
            principal_amount=Decimal("350000.00"),
            annual_rate=Decimal("4.5000"),
            n_periods=300,
            payment_frequency=AnnuitySchedule.Frequency.MONTHLY,
            start_date=date(2026, 1, 1),
            computed_payment=Decimal("1940.00"),
        )
        AnnuityPeriod.objects.create(
            schedule=self.schedule,
            period_number=1,
            payment_date=date(2026, 2, 1),
            payment_amount=Decimal("1940.00"),
            interest_portion=Decimal("1200.00"),
            principal_portion=Decimal("740.00"),
            balance_after=Decimal("349260.00"),
        )

    def test_schedule_list_is_lightweight_and_omits_periods(self):
        response = self.client.get("/api/planning/schedules", **self.auth)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertNotIn("periods", payload[0])

    def test_schedule_detail_includes_periods(self):
        response = self.client.get(f"/api/planning/schedules/{self.schedule.id}", **self.auth)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("periods", payload)
        self.assertEqual(len(payload["periods"]), 1)

