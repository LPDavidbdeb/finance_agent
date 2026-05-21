"""
Strategy Stress-Test: Comparing Pr(IRR > 0%) for GDP vs. Markowitz

This script backtests three specific portfolios since 1990:
1. GDP-Biased (Fundamental)
2. Max Sharpe (Markowitz - Math)
3. Min Volatility (Safe)
"""

import sys, os
import numpy as np
import pandas as pd
from datetime import datetime

# Setup paths
BASE = '/Users/Louis-Philippe/Documents/finance_agent'
sys.path.insert(0, BASE)

from market_data.yahoo_dao import YahooDAO
from planning.returns import PortfolioReturnsCalculator

TICKERS = ['^GSPC', '^GSPTSE', 'VEURX', 'EMF']
HORIZONS = [2, 5, 10, 15]

# Strategy Weights
STRATEGIES = {
    'GDP-Biased': {'^GSPC': 0.307, '^GSPTSE': 0.274, 'VEURX': 0.176, 'EMF': 0.242},
    'Max Sharpe': {'^GSPC': 0.600, '^GSPTSE': 0.067, 'VEURX': 0.050, 'EMF': 0.283},
    'Min Vol':    {'^GSPC': 0.300, '^GSPTSE': 0.600, 'VEURX': 0.050, 'EMF': 0.050}
}

def run_stress_test():
    print("Loading 36-year history for all strategies...")
    prices = YahooDAO.fetch_adjusted_close(TICKERS, start='1990-06-18', cache_path='notebooks/price_series.pkl')
    
    final_results = {}

    for name, weights in STRATEGIES.items():
        print(f"Backtesting {name}...")
        portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, weights)
        monthly_prices = portfolio_series.resample('ME').last()
        
        strat_results = {}
        for h in HORIZONS:
            n_months = h * 12
            success_count = 0
            total_windows = 0
            
            for i in range(len(monthly_prices) - n_months):
                window = monthly_prices.iloc[i : i + n_months + 1]
                # Simulate DCA: simple check if ending value > total principal
                shares = 0
                for p in window.iloc[1:]:
                    shares += 1.0 / p
                
                final_val = shares * window.iloc[-1]
                total_in = n_months
                
                if final_val > total_in:
                    success_count += 1
                total_windows += 1
            
            strat_results[h] = (success_count / total_windows) if total_windows > 0 else 0
        
        final_results[name] = strat_results

    # Display Results
    df_prob = pd.DataFrame(final_results)
    print("\nPROBABILITY OF IRR > 0% (Capital Preservation)")
    print("=" * 65)
    print(df_prob.applymap(lambda x: f"{x*100:.2f}%"))
    print("-" * 65)
    print("Interpretation: Which strategy is most likely to fund the principal?")
    print("=" * 65)

if __name__ == "__main__":
    run_stress_test()
