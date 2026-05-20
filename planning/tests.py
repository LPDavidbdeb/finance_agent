import unittest
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja_jwt.tokens import AccessToken

from planning.models import AnnuitySchedule, AnnuityPeriod
from users.models import Family
from finance_backend.utils.time_value import (
    PaymentFrequency,
    _period_rate,
    compute_pmt_loan,
    compute_pmt_sinking_fund,
    generate_amortization_schedule,
)

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


class TimeValueOfMoneyTest(unittest.TestCase):
    def test_standard_period_rate(self):
        rate = _period_rate(Decimal('12'), PaymentFrequency.MONTHLY, PaymentFrequency.MONTHLY)
        self.assertAlmostEqual(float(rate), 0.01, places=6)

    def test_mismatched_period_rate(self):
        rate = _period_rate(Decimal('6'), PaymentFrequency.WEEKLY, PaymentFrequency.MONTHLY)
        self.assertAlmostEqual(float(rate), 0.00115163, places=8)

    def test_loan_payment_precision(self):
        pmt = compute_pmt_loan(Decimal('100000'), Decimal('6'), 120, PaymentFrequency.MONTHLY)
        self.assertEqual(pmt, Decimal('1110.21'))

    def test_sinking_fund_precision(self):
        pmt = compute_pmt_sinking_fund(Decimal('50000'), Decimal('5'), 60, PaymentFrequency.MONTHLY)
        self.assertEqual(pmt, Decimal('735.23'))

    def test_amortization_clears_balance(self):
        schedule = generate_amortization_schedule(
            Decimal('10000'), Decimal('5'), 12, date(2025, 1, 1), PaymentFrequency.MONTHLY
        )
        self.assertEqual(schedule[-1]['balance_after'], Decimal('0.00'))
        self.assertEqual(sum(r['principal_portion'] for r in schedule), Decimal('10000'))

    def test_prospective_retrospective_equality(self):
        P, r_dec, n, k = 100000.0, Decimal('6'), 120, 60
        p = 0.06 / 12
        pmt = float(compute_pmt_loan(Decimal('100000'), r_dec, n, PaymentFrequency.MONTHLY))
        bal_retro = P * (1 + p)**k - pmt * ((1 + p)**k - 1) / p
        bal_prospect = pmt * (1 - (1 + p)**(-(n - k))) / p
        schedule = generate_amortization_schedule(Decimal('100000'), r_dec, n, date(2025, 1, 1), PaymentFrequency.MONTHLY)
        bal_iterative = float(schedule[k - 1]['balance_after'])
        tol = 0.001 * bal_retro
        self.assertLess(abs(bal_retro - bal_prospect), tol)
        self.assertLess(abs(bal_retro - bal_iterative), tol)

