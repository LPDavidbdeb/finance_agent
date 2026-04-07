from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.models import Sum

from users.models import Family
from accounting.models import Account, JournalEntry, TransactionLine
from planning.models import AnnuitySchedule, AnnuityPeriod
from assets.models import TangibleAsset
from assets.services import OriginationService
from planning.schemas import PaymentFrequencyIn

class OriginationServiceTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Acquisition Family")
        
        # Create funding account
        self.cash_account = Account.objects.create(
            name="Checking Account",
            account_type=Account.AccountType.ASSET,
            family=self.family
        )
        
        # Create liability account (e.g. Loan Provider)
        self.loan_account = Account.objects.create(
            name="Bank Loan",
            account_type=Account.AccountType.LIABILITY,
            family=self.family
        )

    def test_acquire_financed_asset_success(self):
        """
        Verify that acquiring an asset creates a balanced 3-line entry
        and a valid annuity schedule.
        """
        total_cost = Decimal("50000.00")
        down_payment = Decimal("10000.00")
        financed_amount = Decimal("40000.00")
        origination_date = date(2026, 1, 1)
        
        asset = OriginationService.acquire_financed_asset(
            name="Tesla Model 3",
            family=self.family,
            total_cost=total_cost,
            down_payment=down_payment,
            financed_amount=financed_amount,
            origination_date=origination_date,
            loan_term_years=5,
            annual_rate=Decimal("4.99"),
            cash_account=self.cash_account,
            liability_account=self.loan_account,
            payment_frequency=PaymentFrequencyIn.MONTHLY
        )
        
        # 1. Check Asset Model
        self.assertEqual(asset.name, "Tesla Model 3")
        self.assertEqual(asset.purchase_value, total_cost)
        self.assertIsNotNone(asset.annuity_schedule)
        
        # 2. Check Ledger Integrity (The Core Requirement)
        je = JournalEntry.objects.get(description="Acquisition of Tesla Model 3")
        lines = je.lines.all()
        self.assertEqual(lines.count(), 3)
        
        # Sum of amounts MUST be zero
        balance = lines.aggregate(Sum('amount'))['amount__sum']
        self.assertEqual(balance, Decimal("0.00"))
        
        # Verify specific lines
        asset_line = lines.get(account__account_type=Account.AccountType.ASSET, amount__gt=0)
        self.assertEqual(asset_line.amount, total_cost)
        
        cash_line = lines.get(account=self.cash_account)
        self.assertEqual(cash_line.amount, -down_payment)
        
        loan_line = lines.get(account=self.loan_account)
        self.assertEqual(loan_line.amount, -financed_amount)
        
        # 3. Check Schedule Projections
        schedule = asset.annuity_schedule
        self.assertEqual(schedule.principal_amount, financed_amount)
        self.assertEqual(schedule.periods.count(), 60) # 5 years * 12 months
        
        # Verify the first period math
        first_period = schedule.periods.get(period_number=1)
        self.assertGreater(first_period.interest_portion, 0)
        self.assertGreater(first_period.principal_portion, 0)
        self.assertEqual(
            first_period.payment_amount, 
            first_period.interest_portion + first_period.principal_portion
        )

    def test_validation_prevents_imbalanced_math(self):
        """
        Service must raise ValidationError if Cost != Down + Financed
        """
        with self.assertRaises(ValidationError) as cm:
            OriginationService.acquire_financed_asset(
                name="Imbalanced Car",
                family=self.family,
                total_cost=Decimal("100.00"),
                down_payment=Decimal("20.00"),
                financed_amount=Decimal("20.00"), # Sum is 40, not 100
                origination_date=date.today(),
                loan_term_years=1,
                annual_rate=Decimal("5.0"),
                cash_account=self.cash_account,
                liability_account=self.loan_account
            )
        self.assertIn("Accounting mismatch", str(cm.exception))

    def test_zero_down_payment_is_balanced(self):
        """
        Verify 100% financing works (2-line entry).
        """
        total_cost = Decimal("1000.00")
        
        asset = OriginationService.acquire_financed_asset(
            name="Fully Financed Asset",
            family=self.family,
            total_cost=total_cost,
            down_payment=Decimal("0.00"),
            financed_amount=total_cost,
            origination_date=date.today(),
            loan_term_years=1,
            annual_rate=Decimal("0.0"),
            cash_account=self.cash_account,
            liability_account=self.loan_account
        )
        
        je = JournalEntry.objects.get(description="Acquisition of Fully Financed Asset")
        self.assertEqual(je.lines.count(), 2)
        balance = je.lines.aggregate(Sum('amount'))['amount__sum']
        self.assertEqual(balance, Decimal("0.00"))
