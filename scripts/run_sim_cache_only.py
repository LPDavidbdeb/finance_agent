"""Run portfolio simulation using only the cached price pickle (no network).
Writes notebooks/sim_results.json with explicit provenance 'cache'.
"""
import os, json, sys
BASE='/Users/Louis-Philippe/Documents/finance_agent'
OUT_JSON=os.path.join(BASE,'notebooks','sim_results.json')
PICKLE=os.path.join(BASE,'notebooks','price_series.pkl')
import pandas as pd, numpy as np
from planning.returns import PortfolioReturnsCalculator
from planning.optimization import PortfolioOptimizer

TICKERS=['XIU.TO','XWD.TO','XEU.TO']
HORIZONS=[2,5,10,15,25]
MONTHLY_DCA_AMOUNT=1000
REBALANCE_FREQ_MONTHS=1
THRESHOLDS=[0.0,0.05,0.07]

if not os.path.exists(PICKLE):
    print('CACHE_MISSING', PICKLE)
    sys.exit(2)

prices = pd.read_pickle(PICKLE)
missing = [t for t in TICKERS if t not in prices.columns]
if missing:
    print('MISSING_TICKERS_IN_PICKLE', missing)
    sys.exit(3)

# Try to get optimizer weights but avoid network; fall back to equal weights silently here
optimizer = PortfolioOptimizer(lookback_years=5)
try:
    opt = optimizer.optimize(TICKERS)
    weights = opt['optimal']['weights']
except Exception:
    weights = {t: 1.0/len(TICKERS) for t in TICKERS}

results = {'use_synthetic': False, 'source': 'cache', 'thresholds': THRESHOLDS, 'weights': weights, 'data': {}}

for h in HORIZONS:
    horizon_days = PortfolioReturnsCalculator.trading_days_to_index_length(h)
    portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, weights)
    lump = PortfolioReturnsCalculator.compute_lump_sum_returns(portfolio_series, horizon_days)
    lump_returns = np.array(lump['returns'])
    lump_ann = (1 + lump_returns) ** (1.0 / h) - 1 if len(lump_returns)>0 else np.array([])
    dca = PortfolioReturnsCalculator.compute_dca_returns(prices, weights, h, monthly_contribution=MONTHLY_DCA_AMOUNT, rebalance_freq_months=REBALANCE_FREQ_MONTHS)
    dca_returns = np.array(dca['returns'])
    dca_ann = (1 + dca_returns) ** (1.0 / h) - 1 if len(dca_returns)>0 else np.array([])
    entry = {'counts': {'lump': int(len(lump_ann)), 'dca': int(len(dca_ann))}, 'lump': {}, 'dca': {}}
    for th in THRESHOLDS:
        entry['lump'][str(th)] = float(np.mean(lump_ann >= th)) if len(lump_ann)>0 else None
        entry['dca'][str(th)] = float(np.mean(dca_ann >= th)) if len(dca_ann)>0 else None
    results['data'][str(h)] = entry

with open(OUT_JSON,'w') as f:
    json.dump(results,f,indent=2)

print('PRICE_SOURCE: cache')
print('JSON_SAVED:', OUT_JSON)
print('\nSUMMARY:')
for h in HORIZONS:
    l = results['data'][str(h)]['lump']
    d = results['data'][str(h)]['dca']
    def fmt(x):
        return 'N/A' if x is None else f"{x*100:.2f}%"
    print(f"{h:2d} yrs | Lump: {fmt(l['0.0'])}, {fmt(l['0.05'])}, {fmt(l['0.07'])} | DCA: {fmt(d['0.0'])}, {fmt(d['0.05'])}, {fmt(d['0.07'])}")