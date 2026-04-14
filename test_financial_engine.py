import unittest
from decimal import Decimal
from datetime import date
from finance_backend.utils.time_value import (
    PaymentFrequency,
    _period_rate,
    compute_pmt_loan,
    compute_pmt_sinking_fund,
    generate_amortization_schedule
)

class TestFinancialEngine(unittest.TestCase):
    def test_standard_period_rate(self):
        """Test rate where payment and compounding frequencies match."""
        # 12% annual, monthly = 1% per period
        rate = _period_rate(Decimal('12'), PaymentFrequency.MONTHLY, PaymentFrequency.MONTHLY)
        self.assertAlmostEqual(float(rate), 0.01, places=6)

    def test_mismatched_period_rate(self):
        """Test General Annuity conversion factor (the 'p' formula)."""
        # Case: 6% annual, monthly compounding, but WEEKLY payments
        # i = 0.06 / 12 = 0.005
        # c = 12 / 52 = 0.230769
        # p = (1 + 0.005)^0.230769 - 1 ≈ 0.00115163
        rate = _period_rate(Decimal('6'), PaymentFrequency.WEEKLY, PaymentFrequency.MONTHLY)
        self.assertAlmostEqual(float(rate), 0.00115163, places=8)

    def test_loan_payment_precision(self):
        """Verify PMT calculation against known values."""
        # $100,000, 6% annual, 10 years (120 months)
        # Expected PMT: 1110.21
        pmt = compute_pmt_loan(Decimal('100000'), Decimal('6'), 120, PaymentFrequency.MONTHLY)
        self.assertEqual(pmt, Decimal('1110.21'))

    def test_sinking_fund_precision(self):
        """Verify Sinking Fund contribution."""
        # Goal: $50,000 in 5 years (60 months) at 5% interest
        # PMT = FV * r / ((1+r)^n - 1)
        # Expected: 735.23
        pmt = compute_pmt_sinking_fund(Decimal('50000'), Decimal('5'), 60, PaymentFrequency.MONTHLY)
        self.assertEqual(pmt, Decimal('735.23'))

    def test_amortization_integrity(self):
        """Ensure the schedule clears the balance exactly."""
        principal = Decimal('10000')
        rate = Decimal('5')
        periods = 12
        schedule = generate_amortization_schedule(
            principal, rate, periods, date(2025, 1, 1), PaymentFrequency.MONTHLY
        )
        
        # Last row balance must be 0
        last_row = schedule[-1]
        self.assertEqual(last_row['balance_after'], Decimal('0.00'))
        
        # Sum of principal portions must equal original principal
        total_principal = sum(row['principal_portion'] for row in schedule)
        self.assertEqual(total_principal, principal)

    def test_prospective_retrospective_equality(self):
        """
        Verify the 'Golden Rule' of TVM: Retrospective and Prospective 
        methods must yield similar balances (within 0.1% tolerance).
        """
        P = 100000.0
        annual_rate = 0.06
        n = 120 
        k = 60  
        
        p = annual_rate / 12.0
        
        # 1. System calculated rounded PMT
        P_dec = Decimal('100000')
        rate_dec = Decimal('6')
        pmt_rounded = float(compute_pmt_loan(P_dec, rate_dec, n, PaymentFrequency.MONTHLY))
        
        # 2. Retrospective Method (Looking Back)
        s_k = ((1 + p)**k - 1) / p
        bal_retro = P * (1 + p)**k - pmt_rounded * s_k
        
        # 3. Prospective Method (Looking Forward)
        # Note: This uses the rounded PMT to value remaining payments
        a_nk = (1 - (1 + p)**-(n-k)) / p
        bal_prospect = pmt_rounded * a_nk
        
        # 4. Iterative Method (Schedule)
        schedule = generate_amortization_schedule(P_dec, rate_dec, n, date(2025,1,1), PaymentFrequency.MONTHLY)
        bal_iterative = float(schedule[k-1]['balance_after'])
        
        # Verify 0.1% tolerance for all methods
        tolerance = 0.001 * bal_retro
        
        self.assertLess(abs(bal_retro - bal_prospect), tolerance, 
                        f"Retro vs Prospect: {abs(bal_retro - bal_prospect)} > {tolerance}")
        
        self.assertLess(abs(bal_retro - bal_iterative), tolerance, 
                        f"Retro vs Iterative: {abs(bal_retro - bal_iterative)} > {tolerance}")

if __name__ == '__main__':
    unittest.main()
