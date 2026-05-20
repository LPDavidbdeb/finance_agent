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
HORIZONS = [2, 5, 10] # Reduced horizons to fit 10 years of synthetic data (2520 days)
MONTHLY_DCA_AMOUNT = 1000
REBALANCE_FREQ_MONTHS = 1
THRESHOLDS = [0.00, 0.05, 0.07]

np.set_printoptions(suppress=True)

# Generate 10 years of synthetic data
dates = pd.date_range(end=datetime.now(), periods=252*10, freq='B')
np.random.seed(42)
# Create a realistic-ish synthetic dataset: 8% ann return, 15% vol
daily_ret = 0.08/252
daily_vol = 0.15/np.sqrt(252)
prices = pd.DataFrame({
    t: 100 * np.exp(np.cumsum(daily_ret + daily_vol * np.random.randn(len(dates)))) 
    for t in TICKERS
}, index=dates)

optimizer = PortfolioOptimizer(lookback_years=5)
# Monkeypatch fetch_prices to avoid yfinance errors
optimizer.fetch_prices = MagicMock(return_value=prices)

print("Optimizing portfolio (using synthetic data)...")
opt_result = optimizer.optimize(TICKERS)
weights = opt_result['optimal']['weights']
print(f"Optimal weights: {weights}")

out = {}
# We need a price series for lump sum
portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, weights)

for h in HORIZONS:
    horizon_days = PortfolioReturnsCalculator.trading_days_to_index_length(h)
    
    # Check if we have enough data for this horizon
    if len(prices) < horizon_days:
        print(f"Skipping horizon {h} years: insufficient data ({len(prices)} < {horizon_days} days)")
        continue

    # lump-sum
    lump = PortfolioReturnsCalculator.compute_lump_sum_returns(portfolio_series, horizon_days)
    lump_returns = np.array(lump['returns'])
    if len(lump_returns) > 0:
        lump_ann = (1 + lump_returns) ** (1.0 / h) - 1
    else:
        lump_ann = np.array([])

    # dca
    dca = PortfolioReturnsCalculator.compute_dca_returns(prices, weights, h, monthly_contribution=MONTHLY_DCA_AMOUNT, rebalance_freq_months=REBALANCE_FREQ_MONTHS)
    dca_returns = np.array(dca['returns'])
    if len(dca_returns) > 0:
        dca_ann = (1 + dca_returns) ** (1.0 / h) - 1
    else:
        dca_ann = np.array([])

    probs = {'lump': {}, 'dca': {}}
    for th in THRESHOLDS:
        probs['lump'][str(th)] = float(np.mean(lump_ann >= th)) if len(lump_ann) > 0 else 0.0
        probs['dca'][str(th)] = float(np.mean(dca_ann >= th)) if len(dca_ann) > 0 else 0.0

    out[h] = probs

# Print concise table
print('\nHorizon | Lump-sum P(ann >= 0%, 5%, 7%) | DCA P(ann >= 0%, 5%, 7%)')
for h in sorted(out.keys()):
    l = out[h]['lump']
    d = out[h]['dca']
    print(f"{h:2d} yrs  | {l['0.0']:.3f}, {l['0.05']:.3f}, {l['0.07']:.3f}       | {d['0.0']:.3f}, {d['0.05']:.3f}, {d['0.07']:.3f}")

# Return structured output for programmatic use
print('\nJSON_START')
print(json.dumps({'thresholds': THRESHOLDS, 'results': out}, indent=2))
print('JSON_END')
