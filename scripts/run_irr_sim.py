"""
DCA IRR Simulation: 36-Year Historical Distribution

This script calculates the true IRR (Internal Rate of Return) for DCA scenarios
across a 36-year daily historical window.
"""

import sys, os, json
import numpy as np
import pandas as pd
from scipy.optimize import newton

# Setup Django/Environment
sys.path.insert(0, '/Users/Louis-Philippe/Documents/finance_agent')
from planning.optimization import PortfolioOptimizer
from planning.returns import PortfolioReturnsCalculator
from market_data.yahoo_dao import YahooDAO

TICKERS = ['^GSPC', '^GSPTSE', 'VEURX', 'EMF']
HORIZONS = [2, 5, 10, 15, 25]
MONTHLY_DCA = 1000.0
WEIGHTS = {'^GSPC': 0.45, '^GSPTSE': 0.30, 'VEURX': 0.18, 'EMF': 0.07}

def solve_irr(final_value, contribution, n_periods, freq=26):
    """
    Solves for the annual IRR given final value and regular contributions.
    FV = PMT * [((1+r)^n - 1) / r]
    """
    if final_value <= 0: return np.nan
    
    def func(r):
        if r == 0: return contribution * n_periods - final_value
        return contribution * ((1 + r)**n_periods - 1) / r - final_value

    try:
        r_periodic = newton(func, 0.005)
        return ((1 + r_periodic)**freq) - 1
    except:
        return (final_value / (contribution * n_periods))**(freq/n_periods) - 1

def run_irr_sim():
    prices = YahooDAO.fetch_adjusted_close(TICKERS, start='1990-06-18', cache_path='notebooks/price_series.pkl')
    portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, WEIGHTS)
    
    print(f"\nPROBABILITY IRR > 0% (Capital Preservation)")
    print("-" * 45)
    print(f"{'Horizon':<10} | {'Pr(IRR > 0%)':>15} | {'Windows'}")
    print("-" * 45)

    for h in HORIZONS:
        n_months = h * 12
        monthly_prices = portfolio_series.resample('ME').last()
        
        irr_list = []
        for i in range(len(monthly_prices) - n_months):
            window = monthly_prices.iloc[i : i + n_months + 1]
            shares = 0
            for p in window.iloc[1:]:
                shares += MONTHLY_DCA / p
            
            final_value = shares * window.iloc[-1]
            ann_irr = solve_irr(float(final_value), MONTHLY_DCA, n_months, freq=12)
            if not np.isnan(ann_irr):
                irr_list.append(ann_irr)
        
        irr_array = np.array(irr_list)
        prob_success = np.mean(irr_array > 0)
        print(f"{h:2d} years   | {prob_success*100:13.2f}% | {len(irr_list)}")
    print("-" * 45)

if __name__ == "__main__":
    run_irr_sim()
