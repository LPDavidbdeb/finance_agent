"""
Calculate probabilities of hitting specific returns (>0, >5, >7, >10) across horizons.
"""
import sys, os
import numpy as np
import pandas as pd
from scipy.optimize import newton

# Setup Django/Environment
sys.path.insert(0, '/Users/Louis-Philippe/Documents/finance_agent')
from planning.returns import PortfolioReturnsCalculator
from market_data.yahoo_dao import YahooDAO

TICKERS = ['^GSPC', '^GSPTSE', 'VEURX', 'EMF']
HORIZONS = [2, 5, 10, 15, 25]
MONTHLY_DCA = 1000.0
# Let's use Max Sharpe weights for this demonstration since it's the recommended one
WEIGHTS = {'^GSPC': 0.600, '^GSPTSE': 0.067, 'VEURX': 0.050, 'EMF': 0.283}

def solve_irr(final_value, contribution, n_periods, freq=12):
    if final_value <= 0: return np.nan
    def func(r):
        if r == 0: return contribution * n_periods - final_value
        return contribution * ((1 + r)**n_periods - 1) / r - final_value
    try:
        r_periodic = newton(func, 0.005)
        return ((1 + r_periodic)**freq) - 1
    except:
        return (final_value / (contribution * n_periods))**(freq/n_periods) - 1

def run_threshold_sim():
    prices = YahooDAO.fetch_adjusted_close(TICKERS, start='1990-06-18', cache_path='notebooks/price_series.pkl')
    portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, WEIGHTS)
    
    dca_results = []
    ls_results = []
    
    for h in HORIZONS:
        n_months = h * 12
        monthly_prices = portfolio_series.resample('ME').last()
        
        dca_irr_list = []
        ls_cagr_list = []
        
        for i in range(len(monthly_prices) - n_months):
            window = monthly_prices.iloc[i : i + n_months + 1]
            
            # DCA Calc
            shares = 0
            for p in window.iloc[1:]:
                shares += MONTHLY_DCA / p
            final_value = shares * window.iloc[-1]
            ann_irr = solve_irr(float(final_value), MONTHLY_DCA, n_months, freq=12)
            if not np.isnan(ann_irr):
                dca_irr_list.append(ann_irr)
                
            # Lump Sum Calc
            start_price = window.iloc[0]
            end_price = window.iloc[-1]
            cagr = (end_price / start_price) ** (12 / n_months) - 1
            ls_cagr_list.append(cagr)
        
        dca_array = np.array(dca_irr_list) * 100
        ls_array = np.array(ls_cagr_list) * 100
        
        dca_results.append({
            'horizon': f'{h} Years',
            '> 0%': np.mean(dca_array > 0) * 100,
            '> 5%': np.mean(dca_array > 5) * 100,
            '> 7%': np.mean(dca_array > 7) * 100,
            '> 10%': np.mean(dca_array > 10) * 100,
        })
        
        ls_results.append({
            'horizon': f'{h} Years',
            '> 0%': np.mean(ls_array > 0) * 100,
            '> 5%': np.mean(ls_array > 5) * 100,
            '> 7%': np.mean(ls_array > 7) * 100,
            '> 10%': np.mean(ls_array > 10) * 100,
        })

    print("DCA Results:")
    print(pd.DataFrame(dca_results).to_dict(orient='records'))
    print("\nLump Sum Results:")
    print(pd.DataFrame(ls_results).to_dict(orient='records'))

if __name__ == "__main__":
    run_threshold_sim()