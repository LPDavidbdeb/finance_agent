import sys
sys.path.insert(0, '/Users/Louis-Philippe/Documents/finance_agent')
import numpy as np
import json
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock
from planning.optimization import PortfolioOptimizer
from planning.returns import PortfolioReturnsCalculator

TICKERS = ['XIU.TO', 'XWD.TO', 'XEU.TO']
HORIZONS = [2,5,10,15,25]
MONTHLY_DCA_AMOUNT = 1000
REBALANCE_FREQ_MONTHS = 1
THRESHOLDS = [0.00, 0.05, 0.07]

np.set_printoptions(suppress=True)

optimizer = PortfolioOptimizer(lookback_years=5)

# Attempt to fetch prices; on failure use synthetic extended data
use_synthetic=False
prices = None
try:
    prices = optimizer.fetch_prices(TICKERS)
    if prices is None or len(prices) < 252:
        use_synthetic = True
except Exception as e:
    use_synthetic=True

if use_synthetic:
    # Generate 32 years of business days to cover 25-year horizon
    # Use higher base returns for synthetic data to make the demonstration more interesting
    dates = pd.date_range(end=datetime.now(), periods=252*32, freq='B')
    np.random.seed(42)
    # Give some positive drift so probabilities aren't all zero/low
    price_data = {}
    drifts = [0.0003, 0.0004, 0.00025] # roughly 7-10% annual
    vols = [0.01, 0.012, 0.011]
    for i, t in enumerate(TICKERS):
        returns = np.random.normal(drifts[i], vols[i], len(dates))
        price_data[t] = 100 * np.exp(np.cumsum(returns))
    prices = pd.DataFrame(price_data, index=dates)
    
    # Mock the optimizer's fetch_prices to return our synthetic data
    optimizer.fetch_prices = MagicMock(return_value=prices)

opt_result = optimizer.optimize(TICKERS)
weights = opt_result['optimal']['weights']  # dict

out = {}

for h in HORIZONS:
    horizon_days = PortfolioReturnsCalculator.trading_days_to_index_length(h)
    
    # lump-sum
    portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, weights)
    lump = PortfolioReturnsCalculator.compute_lump_sum_returns(portfolio_series, horizon_days)
    lump_returns = np.array(lump['returns'])
    lump_ann = (1 + lump_returns) ** (1.0 / h) - 1 if len(lump_returns)>0 else np.array([])

    # dca
    dca = PortfolioReturnsCalculator.compute_dca_returns(prices, weights, h, monthly_contribution=MONTHLY_DCA_AMOUNT, rebalance_freq_months=REBALANCE_FREQ_MONTHS)
    dca_returns = np.array(dca['returns'])
    dca_ann = (1 + dca_returns) ** (1.0 / h) - 1 if len(dca_returns)>0 else np.array([])

    probs = {'lump': {}, 'dca': {}, 'counts': {'lump': len(lump_ann), 'dca': len(dca_ann)}}
    for th in THRESHOLDS:
        probs['lump'][str(th)] = float(np.mean(lump_ann >= th)) if len(lump_ann)>0 else None
        probs['dca'][str(th)] = float(np.mean(dca_ann >= th)) if len(dca_ann)>0 else None

    out[h] = probs

# Print concise table
print('Using synthetic prices:' if use_synthetic else 'Using yfinance prices:')
print('Horizon | Lump-sum P(ann >= 0%, 5%, 7%) | DCA P(ann >= 0%, 5%, 7%) | counts (lump,dca)')
for h in HORIZONS:
    l = out[h]['lump']
    d = out[h]['dca']
    cl = out[h]['counts']['lump']
    cd = out[h]['counts']['dca']
    def fmt(x):
        return 'N/A' if x is None else f"{x:.4f}"
    print(f"{h:2d} yrs  | {fmt(l['0.0'])}, {fmt(l['0.05'])}, {fmt(l['0.07'])} | {fmt(d['0.0'])}, {fmt(d['0.05'])}, {fmt(d['0.07'])} | ({cl},{cd})")

# JSON output
print('\nJSON:')
print(json.dumps({'use_synthetic': use_synthetic, 'thresholds': THRESHOLDS, 'results': out}, indent=2))
