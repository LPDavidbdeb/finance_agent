import sys
import os
import numpy as np
import pandas as pd
import json
from datetime import datetime
from unittest.mock import MagicMock

# Set up path
sys.path.insert(0, '/Users/Louis-Philippe/Documents/finance_agent')

try:
    from planning.optimization import PortfolioOptimizer
    from planning.returns import PortfolioReturnsCalculator
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

TICKERS = ['XIU.TO', 'XWD.TO', 'XEU.TO']
HORIZONS = [2, 5, 10, 15, 25]
MONTHLY_DCA_AMOUNT = 1000
REBALANCE_FREQ_MONTHS = 1
THRESHOLDS = [0.00, 0.05, 0.07]

np.set_printoptions(suppress=True)

optimizer = PortfolioOptimizer(lookback_years=30) 

# Attempt to fetch prices; on failure use synthetic but print a warning
use_synthetic = False
try:
    print("Attempting to fetch historical prices...")
    prices = optimizer.fetch_prices(TICKERS)
    if len(prices) < 252 * 5:
        print("Insufficient historical data found, using synthetic data for demonstration.")
        use_synthetic = True
except Exception as e:
    print(f"Fetch failed ({e}), using synthetic data.")
    use_synthetic = True

if use_synthetic:
    # Generate 30 years of synthetic data
    dates = pd.date_range(end=datetime.now(), periods=252*32, freq='B')
    np.random.seed(42)
    # Different returns/vol for some variety among assets
    returns_ann = [0.07, 0.09, 0.06]
    vols_ann = [0.15, 0.18, 0.16]
    
    price_data = {}
    for i, t in enumerate(TICKERS):
        daily_ret = returns_ann[i] / 252
        daily_vol = vols_ann[i] / np.sqrt(252)
        price_data[t] = 100 * np.exp(np.cumsum(daily_ret + daily_vol * np.random.randn(len(dates))))
    
    prices = pd.DataFrame(price_data, index=dates)

# Optimizer setup - provide data if synthetic
if use_synthetic:
    optimizer.fetch_prices = MagicMock(return_value=prices)

print("Optimizing portfolio...")
opt_result = optimizer.optimize(TICKERS)
weights = opt_result['optimal']['weights'] # This is a dict

out = {}

for h in HORIZONS:
    horizon_days = PortfolioReturnsCalculator.trading_days_to_index_length(h)
    
    # Check if we have enough data
    if len(prices) < horizon_days:
        out[h] = {'lump': {th: None for th in THRESHOLDS}, 'dca': {th: None for th in THRESHOLDS}, 'counts': {'lump': 0, 'dca': 0}}
        continue

    # lump-sum - passing the dict 'weights'
    portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, weights)
    lump = PortfolioReturnsCalculator.compute_lump_sum_returns(portfolio_series, horizon_days)
    lump_returns = np.array(lump['returns'])
    if len(lump_returns) > 0:
        lump_ann = (1 + lump_returns) ** (1.0 / h) - 1
    else:
        lump_ann = np.array([])

    # dca - passing the dict 'weights'
    dca = PortfolioReturnsCalculator.compute_dca_returns(prices, weights, h, monthly_contribution=MONTHLY_DCA_AMOUNT, rebalance_freq_months=REBALANCE_FREQ_MONTHS)
    dca_returns = np.array(dca['returns'])
    if len(dca_returns) > 0:
        dca_ann = (1 + dca_returns) ** (1.0 / h) - 1
    else:
        dca_ann = np.array([])

    probs = {'lump': {}, 'dca': {}, 'counts': {'lump': len(lump_ann), 'dca': len(dca_ann)}}
    for th in THRESHOLDS:
        probs['lump'][th] = float(np.mean(lump_ann >= th)) if len(lump_ann) > 0 else None
        probs['dca'][th] = float(np.mean(dca_ann >= th)) if len(dca_ann) > 0 else None

    out[h] = probs

# Print concise table
print('\nUsing synthetic prices:' if use_synthetic else '\nUsing historical prices:')
print('Horizon | Lump-sum P(ann >= 0%, 5%, 7%) | DCA P(ann >= 0%, 5%, 7%) | counts (lump,dca)')
for h in HORIZONS:
    l = out[h]['lump']
    d = out[h]['dca']
    cl = out[h]['counts']['lump']
    cd = out[h]['counts']['dca']
    def fmt(x):
        return 'N/A' if x is None else f"{x:.3f}"
    print(f"{h:2d} yrs  | {fmt(l[0.0])}, {fmt(l[0.05])}, {fmt(l[0.07])}       | {fmt(d[0.0])}, {fmt(d[0.05])}, {fmt(d[0.07])}       | ({cl},{cd})")

# JSON output
print('\nJSON_START')
json_out = {str(k): v for k, v in out.items()}
print(json.dumps({'use_synthetic': use_synthetic, 'thresholds': THRESHOLDS, 'results': json_out}, indent=2))
print('JSON_END')
