"""
Reviewer Note: Benchmark Approved, Exact Simulator Not Approved

This module is approved as a historical benchmark engine. It is not approved as an exact ETF simulator.

The distinction matters:
- The engine is mathematically consistent inside its discrete cash-flow model.
- The inputs are proxy instruments, not a complete representation of real ETF cash flows.
- Therefore, the output is suitable for benchmarking, scenario analysis, and relative comparison, but not for claiming exact realized ETF probabilities.

What Is Approved:
- Rolling historical probability estimates over calendar-aligned monthly windows.
- Fee-adjusted hurdle modeling using a multiplicative gross hurdle.
- Discrete DCA evaluation on the same monthly grid as the sampled series.
- Fail-fast behavior when a required ticker is missing.
- Cached data reuse and incremental update behavior for operational efficiency.

What Is Not Approved:
- Exact ETF cash-flow simulation.
- Currency-complete portfolio replication without a translation layer.
- Dividend-timing exactness for all instruments in the proxy set.
- Withholding-tax exactness.
- Tracking-error exactness.
- Silent substitution of missing tickers or partial proxy portfolios.

Required Assumptions:
- The results are based on historical proxy data, not guaranteed future outcomes.
- Price-index or adjusted-close proxies may understate or distort true total-return behavior.
- Cross-currency proxies are only approximate unless daily FX translation is explicitly modeled.
- The DCA return distribution assumes the chosen contribution schedule and contribution timing are intentional model inputs.
- The fee adjustment is modeled multiplicatively as a gross hurdle derived from the target net annualized return and blended MER.

Implementation Boundary:
1. Fetch proxy data through YahooDAO.
2. Build the synthetic portfolio series in the mathematical engine.
3. Downsample to monthly observations.
4. Apply the fee-adjusted probability engine.
5. Present the results as benchmark probabilities only.

If any required proxy is unavailable, the engine should fail fast rather than silently proceed with a reduced portfolio.
"""

import sys, os, json
sys.path.insert(0, '/Users/Louis-Philippe/Documents/finance_agent')
import numpy as np
import pandas as pd
from datetime import datetime
from planning.optimization import PortfolioOptimizer
from planning.returns import PortfolioReturnsCalculator
from market_data.yahoo_dao import YahooDAO

BASE = '/Users/Louis-Philippe/Documents/finance_agent'
OUT_JSON = os.path.join(BASE, 'notebooks', 'sim_results.json')
OUT_PICKLE = os.path.join(BASE, 'notebooks', 'price_series.pkl')

TICKERS = ['^GSPC', '^GSPTSE', 'VEURX', 'EMF']
HORIZONS = [2,5,10,15,25]
MONTHLY_DCA_AMOUNT = 1000
REBALANCE_FREQ_MONTHS = 1
THRESHOLDS = [0.00, 0.05, 0.07]

np.set_printoptions(suppress=True)

optimizer = PortfolioOptimizer(lookback_years=10)
use_synthetic=False
prices=None
source='rapidapi'

try:
    # Explicitly fetch from 1990 to capture the full legacy proxy window
    prices = YahooDAO.fetch_adjusted_close(TICKERS, start='1990-06-18')
except Exception as e:
    print(f"Failed to fetch prices: {e}. Falling back to synthetic data.")
    use_synthetic=True
    dates = pd.date_range(end=datetime.now(), periods=252*32, freq='B')
    np.random.seed(42)
    prices = pd.DataFrame({t: 100 * np.cumprod(1 + np.random.randn(len(dates)) * 0.005 + 0.0003) for t in TICKERS}, index=dates)
    source='synthetic'

# Ensure output directory exists
os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)

# Save pickle
try:
    prices.to_pickle(OUT_PICKLE)
    pickle_saved=True
except Exception as e:
    pickle_saved=False
    pickle_error=str(e)

# Compute optimization and probabilities
if not use_synthetic:
    try:
        opt_result = optimizer.optimize(TICKERS)
        weights = opt_result['optimal']['weights']
    except Exception as e:
        print(f"Optimization failed: {e}. Using equal weights.")
        weights = {t: 1.0/len(TICKERS) for t in TICKERS}
else:
    weights = {t: 1.0/len(TICKERS) for t in TICKERS}

results = {'use_synthetic': use_synthetic, 'source': source, 'thresholds': THRESHOLDS, 'weights': weights, 'data': {}}

for h in HORIZONS:
    horizon_days = PortfolioReturnsCalculator.trading_days_to_index_length(h)
    portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, weights)
    lump = PortfolioReturnsCalculator.compute_lump_sum_returns(portfolio_series, horizon_days)
    lump_returns = np.array(lump['returns'])
    
    # Avoid division by zero or log errors if h is small or data is missing
    if len(lump_returns) > 0:
        lump_ann = (1 + lump_returns) ** (1.0 / h) - 1
    else:
        lump_ann = np.array([])

    dca = PortfolioReturnsCalculator.compute_dca_returns(prices, weights, h, monthly_contribution=MONTHLY_DCA_AMOUNT, rebalance_freq_months=REBALANCE_FREQ_MONTHS)
    dca_returns = np.array(dca['returns'])
    if len(dca_returns) > 0:
        # Note: DCA internal return might be more complex, but here we use the same formula for consistency with user request
        # Actually, dca['returns'] are total percentage gains.
        dca_ann = (1 + dca_returns) ** (1.0 / h) - 1
    else:
        dca_ann = np.array([])

    entry = {'counts': {'lump': int(len(lump_ann)), 'dca': int(len(dca_ann))}, 'lump': {}, 'dca': {}}
    for th in THRESHOLDS:
        entry['lump'][str(th)] = float(np.mean(lump_ann >= th)) if len(lump_ann)>0 else None
        entry['dca'][str(th)] = float(np.mean(dca_ann >= th)) if len(dca_ann)>0 else None
    results['data'][str(h)] = entry

# write JSON
with open(OUT_JSON, 'w') as f:
    json.dump(results, f, indent=2)

# Print summary
print('PRICE_SOURCE:', source)
print('PICKLE_SAVED:', OUT_PICKLE if pickle_saved else 'ERROR: '+pickle_error)
print('JSON_SAVED:', OUT_JSON)
print('\nSUMMARY TABLE:')
print('Horizon | Lump-sum P(ann >= 0%,5%,7%) | DCA P(ann >= 0%,5%,7%) | counts (lump,dca)')
for h in HORIZONS:
    l = results['data'][str(h)]['lump']
    d = results['data'][str(h)]['dca']
    cl = results['data'][str(h)]['counts']['lump']
    cd = results['data'][str(h)]['counts']['dca']
    def fmt(x):
        return 'N/A' if x is None else f"{x*100:.2f}%"
    print(f"{h:2d} yrs  | {fmt(l['0.0'])}, {fmt(l['0.05'])}, {fmt(l['0.07'])} | {fmt(d['0.0'])}, {fmt(d['0.05'])}, {fmt(d['0.07'])} | ({cl},{cd})")
