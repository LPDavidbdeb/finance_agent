"""
Paycheck Router: Principal-Floor Liability Engine
================================================

STRATEGY: Principal-Floor Solvency
----------------------------------
This script implements a "Solvency-First" routing logic. It assumes 0% growth for 
all investments to calculate the base installment. This ensures that the 
principal alone will fund the liability, making the goal immune to market crashes 
or sequence-of-returns risk.

The "Expected Returns" (e.g., 7% Market, 4.5% GIC) are used ONLY to determine 
 the RATIO (split) of where the principal is routed, maximizing the potential 
"Investment Discount" (surplus cash) at the end of the horizon.

LOGIC:
1. Base Installment (PMT) = Total Liability / Total Remaining Periods.
2. Risky/Safe Split = Derived from the relative 'work' each portfolio is expected to do.
3. Allocation = Duration-matched GIC terms (6mo, 1yr, 5yr).

Result: You are guaranteed to hit your goal (X), and the market returns 
simply determine how much "bonus cash" you have left over.
"""

import sys, os
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict

# Setup Django Environment
sys.path.insert(0, '/Users/Louis-Philippe/Documents/finance_agent')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings')
import django
django.setup()

from planning.models import AnnuitySchedule
from users.models import Family

def calculate_principal_floor_split(
    goal_amount: Decimal, 
    horizon_years: float, 
    total_periods: int,
    risky_rate: float = 0.07, 
    safe_rate: float = 0.045
) -> Dict:
    """
    Calculates routing based on the Principal-Floor (0% growth) assumption.
    """
    # 1. Calculate the 'Solvency Installment' (X/N)
    # This ensures principal alone covers the goal.
    total_pmt = goal_amount / Decimal(total_periods)

    # 2. Calculate the 'Growth Weights'
    # We use the relative future value factors to decide the split ratio.
    # Higher expected return = Higher weight in the risky bucket.
    periods = horizon_years * 26 
    
    # FV Factors (how much $1 grows to)
    fv_factor_risky = (1 + (risky_rate/26))**periods
    fv_factor_safe = (1 + (safe_rate/26))**periods
    
    # Weighting logic: We want to capture as much of the 7% 'discount' as possible
    # while maintaining the barbell balance.
    total_weight = fv_factor_risky + fv_factor_safe
    w_risky = Decimal(fv_factor_risky / total_weight)
    w_safe = Decimal(fv_factor_safe / total_weight)

    return {
        'total_pmt': total_pmt.quantize(Decimal('0.01')),
        'risky': (total_pmt * w_risky).quantize(Decimal('0.01')),
        'safe': (total_pmt * w_safe).quantize(Decimal('0.01'))
    }

def route_paycheck(family_name: str):
    try:
        family = Family.objects.get(name=family_name)
    except Family.DoesNotExist:
        print(f"Family {family_name} not found.")
        return

    # Fetch all active sinking funds (Liabilities)
    schedules = AnnuitySchedule.objects.filter(
        family=family, 
        schedule_type=AnnuitySchedule.ScheduleType.SINKING_FUND
    )

    today = date.today()
    results = {
        'risky_total': Decimal('0.00'),
        'safe_buckets': {
            '6_months': Decimal('0.00'),
            '1_year': Decimal('0.00'),
            '5_years': Decimal('0.00'),
            'long_term_safe': Decimal('0.00')
        }
    }

    print(f"\nPRINCIPAL-FLOOR ROUTING REPORT: {family.name.upper()}")
    print("=" * 85)
    print(f"{'Liability':<25} | {'Total PMT':>10} | {'Risky':>10} | {'Safe':>10} | {'Maturity'}")
    print("-" * 85)

    for s in schedules:
        # Calculate Remaining Horizon
        end_date = s.start_date + timedelta(weeks=(s.n_periods * 2))
        horizon_days = (end_date - today).days
        horizon_years = horizon_days / 365.25

        if horizon_years <= 0:
            continue

        # 1. Use the Principal-Floor logic
        # For long term (> 5 years), split the principal.
        # For short term, 100% goes to the safe bucket.
        if horizon_years > 5:
            split = calculate_principal_floor_split(s.principal_amount, horizon_years, s.n_periods)
        else:
            pmt = s.principal_amount / s.n_periods
            split = {'total_pmt': pmt, 'risky': Decimal('0.00'), 'safe': pmt}

        # 2. Determine GIC/Term Bucket
        if horizon_years <= 0.5:
            term = '6_months'
        elif horizon_years <= 1.0:
            term = '1_year'
        elif horizon_years <= 5.0:
            term = '5_years'
        else:
            term = 'long_term_safe'

        results['risky_total'] += split['risky']
        results['safe_buckets'][term] += split['safe']

        print(f"{s.name[:25]:<25} | {split['total_pmt']:>10} | {split['risky']:>10} | {split['safe']:>10} | {term}")

    print("-" * 85)
    total_safe = sum(results['safe_buckets'].values())
    print(f"{'AGGREGATE TOTALS':<25} | {results['risky_total'] + total_safe:>10} | {results['risky_total']:>10} | {total_safe:>10}")
    print("=" * 85)
    
    print("\nACTIONABLE INSTRUCTIONS FOR THIS PAYCHECK:")
    print(f" 1. [RISKY] Transfer to Brokerage:         ${results['risky_total']}")
    print(f" 2. [SAFE]  Buy 6-Month GIC:               ${results['safe_buckets']['6_months']}")
    print(f" 3. [SAFE]  Buy 1-Year GIC:                ${results['safe_buckets']['1_year']}")
    print(f" 4. [SAFE]  Buy 5-Year GIC:                ${results['safe_buckets']['5_years']}")
    print(f" 5. [SAFE]  Hold in Cash/Liquid Safe:      ${results['safe_buckets']['long_term_safe']}")
    print("\n* Note: Total Principal Saved == Total Liability Cost (Growth is your surplus).")
    print("-" * 85)

if __name__ == "__main__":
    route_paycheck('709rueBeaudoin')
