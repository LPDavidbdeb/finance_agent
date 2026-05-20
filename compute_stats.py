import sys, os, json
sys.path.insert(0, '/Users/Louis-Philippe/Documents/finance_agent')
import numpy as np
import pandas as pd
import yfinance as yf
import requests
from planning.optimization import PortfolioOptimizer
from planning.returns import PortfolioReturnsCalculator

# Set up a session with a user agent to bypass some blocks
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

BASE = '/Users/Louis-Philippe/Documents/finance_agent'
OUT_JSON = os.path.join(BASE, 'notebooks', 'sim_results.json')
OUT_PICKLE = os.path.join(BASE, 'notebooks', 'price_series.pkl')

TICKERS = ['XIU.TO', 'XWD.TO', 'XEU.TO']
HORIZONS = [2,5,10,15,25]
MONTHLY_DCA_AMOUNT = 1000
REBALANCE_FREQ_MONTHS = 1
THRESHOLDS = [0.00, 0.05, 0.07]

np.set_printoptions(suppress=True)

optimizer = PortfolioOptimizer(lookback_years=5)

# Force live fetch; if it fails, try with session
try:
    print("Fetching prices...")
    # We can't easily pass 'session' to optimizer.fetch_prices if it's not supported by the method signature.
    # Let's see if we can patch yfinance globally or just download here.
    prices = yf.download(TICKERS, period="10y", interval="1d", session=session)
    if prices.empty:
        raise ValueError("Downloaded data is empty")
    # Clean up columns if it's multi-index
    if isinstance(prices.columns, pd.MultiIndex):
        prices = prices['Adj Close']
    else:
        prices = prices[['Adj Close']]
    
    prices = prices.fillna(method='ffill').dropna()
    source='yfinance'
except Exception as e:
    print('ERROR_FETCH_PRICES:', str(e))
    print('Attempting to use existing pickle as fallback...')
    if os.path.exists(OUT_PICKLE):
        prices = pd.read_pickle(OUT_PICKLE)
        source='pickle_fallback'
    else:
        raise

# Ensure output directory exists
os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)

# Save pickle
prices.to_pickle(OUT_PICKLE)

# Compute optimization and probabilities
# Since we already have prices, we might need to skip optimizer.fetch_prices inside optimize
# But wait, optimizer.optimize(tickers) might call fetch_prices again.
# Let's check PortfolioOptimizer.optimize source if possible, or just provide weights manually.
# For now, let's assume we can use the weights from the previous run or compute them if we have prices.

# Let's try to mock optimizer.fetch_prices
optimizer.fetch_prices = lambda tickers: prices

opt_result = optimizer.optimize(TICKERS)
weights = opt_result['optimal']['weights']

results = {'use_synthetic': False, 'source': source, 'thresholds': THRESHOLDS, 'weights': weights, 'data': {}}

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

# write JSON
with open(OUT_JSON, 'w') as f:
    json.dump(results, f, indent=2)

print('WROTE_JSON:', OUT_JSON)
print('WROTE_PICKLE:', OUT_PICKLE)
print('SUMMARY:')
for h in HORIZONS:
    l = results['data'][str(h)]['lump']
    d = results['data'][str(h)]['dca']
    cl = results['data'][str(h)]['counts']['lump']
    cd = results['data'][str(h)]['counts']['dca']
    def fmt(x):
        return 'N/A' if x is None else f"{x*100:.2f}%"
    print(f"{h:2d} yrs  | {fmt(l['0.0'])}, {fmt(l['0.05'])}, {fmt(l['0.07'])} | {fmt(d['0.0'])}, {fmt(d['0.05'])}, {fmt(d['0.07'])} | ({cl},{cd})")
