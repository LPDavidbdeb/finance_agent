"""
Conditional Outcome Analysis: Upside vs. Downside Severity

This script calculates two critical metrics for each strategy and horizon:
1. Expected Return | IRR > 0% (The 'Bonus' you get when things go well)
2. Expected Return | IRR < 0% (The 'Shortfall' you must fund if things go poorly)
"""

import sys, os
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.optimize import newton

# Setup paths
BASE = '/Users/Louis-Philippe/Documents/finance_agent'
sys.path.insert(0, BASE)

from market_data.yahoo_dao import YahooDAO
from planning.returns import PortfolioReturnsCalculator

TICKERS = ['^GSPC', '^GSPTSE', 'VEURX', 'EMF']
HORIZONS = [2, 5, 10, 15]

STRATEGIES = {
    'GDP-Biased': {'^GSPC': 0.307, '^GSPTSE': 0.274, 'VEURX': 0.176, 'EMF': 0.242},
    'Max Sharpe': {'^GSPC': 0.600, '^GSPTSE': 0.067, 'VEURX': 0.050, 'EMF': 0.283},
    'Min Vol':    {'^GSPC': 0.300, '^GSPTSE': 0.600, 'VEURX': 0.050, 'EMF': 0.050}
}

def solve_irr(final_value, contribution, n_periods, freq=26):
    """
    Solves for the annual IRR given final value and regular contributions.
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

def run_conditional_analysis():
    print("Loading 36-year history...")
    prices = YahooDAO.fetch_adjusted_close(TICKERS, start='1990-06-18', cache_path='notebooks/price_series.pkl')
    
    upside_results = {}
    downside_results = {}

    for name, weights in STRATEGIES.items():
        print(f"Analyzing {name}...")
        portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, weights)
        monthly_prices = portfolio_series.resample('ME').last()
        
        upside_h = {}
        downside_h = {}
        
        for h in HORIZONS:
            n_months = h * 12
            irr_list = []
            
            for i in range(len(monthly_prices) - n_months):
                window = monthly_prices.iloc[i : i + n_months + 1]
                shares = 0
                for p in window.iloc[1:]:
                    shares += 1.0 / p
                final_val = shares * window.iloc[-1]
                
                # Approximate IRR using accurate Newton solver
                irr = solve_irr(float(final_val), 1.0, n_months, freq=12)
                if not np.isnan(irr):
                    irr_list.append(irr)
            
            irr_array = np.array(irr_list)
            
            # Upside: Mean of positive returns
            pos_returns = irr_array[irr_array > 0]
            upside_h[h] = np.mean(pos_returns) if len(pos_returns) > 0 else 0
            
            # Downside: Mean of negative returns (Expected Shortfall)
            neg_returns = irr_array[irr_array < 0]
            downside_h[h] = np.mean(neg_returns) if len(neg_returns) > 0 else 0
            
        upside_results[name] = upside_h
        downside_results[name] = downside_h

    # Formatting Output
    df_upside = pd.DataFrame(upside_results)
    df_downside = pd.DataFrame(downside_results)

    print("\nEXPECTED UPSIDE (Mean IRR when > 0%)")
    print("-" * 65)
    print(df_upside.map(lambda x: f"+{x*100:.2f}%"))
    
    print("\nEXPECTED DOWNSIDE (Mean IRR when < 0%)")
    print("-" * 65)
    print(df_downside.map(lambda x: f"{x*100:.2f}%"))
    print("-" * 65)
    print("Interpretation: When you fail, how deep is the hole?")
    print("=" * 65)

if __name__ == "__main__":
    run_conditional_analysis()
