from decimal import Decimal
from datetime import date
from django.test import TestCase
from users.models import Family
from planning.models import AnnuitySchedule
from categorization.models import Merchant, TransactionMappingRule

class AnnuityScheduleSignalTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Signal Family")

    def test_schedule_creation_generates_rule(self):
        """
        Success Criteria: When an AnnuitySchedule is saved, 
        a Merchant and TransactionMappingRule are created with +/- $5 variance.
        """
        payment = Decimal("1234.56")
        schedule_name = "Tesla Loan"
        
        schedule = AnnuitySchedule.objects.create(
            family=self.family,
            name=schedule_name,
            schedule_type=AnnuitySchedule.ScheduleType.LOAN_AMORTIZATION,
            principal_amount=Decimal("50000.00"),
            annual_rate=Decimal("5.0"),
            n_periods=60,
            payment_frequency=AnnuitySchedule.Frequency.MONTHLY,
            start_date=date(2026, 1, 1),
            computed_payment=payment
        )

        # 1. Assert Merchant creation (using case-insensitive match because Merchant.save() uppers the name)
        expected_merchant_name = f"[LOAN] {schedule_name}".upper()
        self.assertTrue(Merchant.objects.filter(family=self.family, name__iexact=expected_merchant_name).exists())
        merchant = Merchant.objects.get(family=self.family, name__iexact=expected_merchant_name)

        # 2. Assert Rule creation
        self.assertTrue(TransactionMappingRule.objects.filter(linked_schedule=schedule).exists())
        rule = TransactionMappingRule.objects.get(linked_schedule=schedule)
        
        self.assertEqual(rule.merchant, merchant)
        self.assertEqual(rule.search_text, "tesla loan") # normalized search text

        # 3. Assert exact mathematical bounds (+/- $5.00)
        expected_min = payment - Decimal("5.00")
        expected_max = payment + Decimal("5.00")
        
        self.assertEqual(rule.min_amount, expected_min)
        self.assertEqual(rule.max_amount, expected_max)

    def test_schedule_update_does_not_duplicate_rule(self):
        """
        Verify the signal only fires on creation.
        """
        schedule = AnnuitySchedule.objects.create(
            family=self.family,
            name="Unique Loan",
            schedule_type=AnnuitySchedule.ScheduleType.LOAN_AMORTIZATION,
            principal_amount=Decimal("1000.00"),
            annual_rate=Decimal("5.0"),
            n_periods=12,
            payment_frequency=AnnuitySchedule.Frequency.MONTHLY,
            start_date=date(2026, 1, 1),
            computed_payment=Decimal("100.00")
        )
        
        initial_count = TransactionMappingRule.objects.filter(linked_schedule=schedule).count()
        self.assertEqual(initial_count, 1)
        
        # Update schedule
        schedule.name = "Updated Loan Name"
        schedule.save()
        
        final_count = TransactionMappingRule.objects.filter(linked_schedule=schedule).count()
        self.assertEqual(final_count, 1)
