import sys, json, os
import numpy as np
import pandas as pd
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.getcwd())

from planning.optimization import PortfolioOptimizer
from planning.returns import PortfolioReturnsCalculator

TICKERS = ['XIU.TO', 'XWD.TO', 'XEU.TO']
HORIZONS = [2,5,10,15,25]
MONTHLY_DCA_AMOUNT = 1000
REBALANCE_FREQ_MONTHS = 1
THRESHOLDS = [0.00, 0.05, 0.07]

optimizer = PortfolioOptimizer(lookback_years=5)
use_synthetic=False
try:
    print("Attempting to fetch real prices...")
    prices = optimizer.fetch_prices(TICKERS)
    if prices is None or prices.empty or len(prices) < 252:
         raise ValueError("Insufficient data")
    print("Successfully fetched real prices.")
except Exception as e:
    print(f"Failed to fetch real prices ({e}). Using synthetic data.")
    use_synthetic=True
    dates = pd.date_range(end=datetime.now(), periods=252*32, freq='B')
    np.random.seed(42)
    # Generate random walk with small positive drift (approx 8% annual)
    # 0.08 / 252 approx 0.0003
    prices = pd.DataFrame({t: 100 * np.cumprod(1 + np.random.normal(0.0003, 0.01, len(dates))) for t in TICKERS}, index=dates)

# Monkey-patch fetch_prices to avoid redundant (and failing) network calls
optimizer.fetch_prices = lambda tickers: prices

print("Optimizing portfolio...")
opt_result = optimizer.optimize(TICKERS)
weights = opt_result['optimal']['weights']
print(f"Optimal weights: {dict(zip(TICKERS, weights))}")

results = {'use_synthetic': use_synthetic, 'thresholds': THRESHOLDS, 'data': {}}

for h in HORIZONS:
    print(f"Processing horizon {h} years...")
    horizon_days = PortfolioReturnsCalculator.trading_days_to_index_length(h)
    
    # Lump sum
    portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, weights)
    lump = PortfolioReturnsCalculator.compute_lump_sum_returns(portfolio_series, horizon_days)
    lump_returns = np.array(lump['returns'])
    lump_ann = (1 + lump_returns) ** (1.0 / h) - 1 if len(lump_returns)>0 else np.array([])

    # DCA
    dca = PortfolioReturnsCalculator.compute_dca_returns(prices, weights, h, monthly_contribution=MONTHLY_DCA_AMOUNT, rebalance_freq_months=REBALANCE_FREQ_MONTHS)
    dca_returns = np.array(dca['returns'])
    dca_ann = (1 + dca_returns) ** (1.0 / h) - 1 if len(dca_returns)>0 else np.array([])

    entry = {
        'counts': {'lump': int(len(lump_ann)), 'dca': int(len(dca_ann))},
        'lump': {}, 'dca': {}
    }
    for th in THRESHOLDS:
        entry['lump'][str(th)] = float(np.mean(lump_ann >= th)) if len(lump_ann)>0 else None
        entry['dca'][str(th)] = float(np.mean(dca_ann >= th)) if len(dca_ann)>0 else None
    results['data'][str(h)] = entry

# Ensure notebooks directory exists
os.makedirs('notebooks', exist_ok=True)

# write file
with open('notebooks/sim_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print('WROTE notebooks/sim_results.json')
