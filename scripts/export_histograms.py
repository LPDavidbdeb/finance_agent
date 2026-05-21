"""
Generate Histogram Data for Return Distributions
"""
import sys, os, json
import numpy as np
import pandas as pd

# Setup Django/Environment
sys.path.insert(0, '/Users/Louis-Philippe/Documents/finance_agent')
from planning.returns import PortfolioReturnsCalculator
from market_data.yahoo_dao import YahooDAO

TICKERS = ['^GSPC', '^GSPTSE', 'VEURX', 'EMF']
HORIZONS = [2, 5, 10, 25]
WEIGHTS = {'^GSPC': 0.600, '^GSPTSE': 0.067, 'VEURX': 0.050, 'EMF': 0.283}

def run_distribution_export():
    prices = YahooDAO.fetch_adjusted_close(TICKERS, start='1990-06-18', cache_path='notebooks/price_series.pkl')
    portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, WEIGHTS)
    
    monthly_prices = portfolio_series.resample('ME').last()
    
    hist_data = {}
    
    for h in HORIZONS:
        n_months = h * 12
        ls_cagr_list = []
        
        for i in range(len(monthly_prices) - n_months):
            window = monthly_prices.iloc[i : i + n_months + 1]
            start_price = window.iloc[0]
            end_price = window.iloc[-1]
            cagr = (end_price / start_price) ** (12 / n_months) - 1
            ls_cagr_list.append(cagr * 100) # Percentage
            
        # Create Histogram Bins (from -30% to +30%, bin size 2%)
        bins = np.arange(-30, 32, 2)
        counts, edges = np.histogram(ls_cagr_list, bins=bins)
        
        # Normalize counts to percentages (Density)
        total = sum(counts)
        freq = (counts / total) * 100
        
        # Format for Recharts
        chart_data = []
        for j in range(len(freq)):
            chart_data.append({
                'bin': f"{edges[j]:.0f}% to {edges[j+1]:.0f}%",
                'value': float(freq[j])
            })
            
        hist_data[f"{h} Years"] = chart_data

    # Save to a temp JSON file to be read and pasted into the frontend
    with open('notebooks/hist_data.json', 'w') as f:
        json.dump(hist_data, f, indent=2)
    print("Histogram data saved to notebooks/hist_data.json")

if __name__ == "__main__":
    run_distribution_export()