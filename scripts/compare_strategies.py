"""
Portfolio Strategy Comparison: GDP-Weighted vs Markowitz (MVO)

This script compares two allocation philosophies using 36 years of history:
1. GDP-Biased: Fundamental macro-weighting (OECD/World Bank data).
2. Max Sharpe Ratio: Efficient Frontier optimization (Markowitz theory).
3. Min Volatility: The safest possible mathematical combination.
"""

import sys, os
import pandas as pd
import numpy as np
from datetime import datetime

# Setup paths
BASE = '/Users/Louis-Philippe/Documents/finance_agent'
sys.path.insert(0, BASE)

from market_data.oecd_dao import MacroDAO
from planning.optimization import PortfolioOptimizer

def run_comparison():
    print("Fetching 36-year price history for optimization...")
    # Use 20 years lookback for the Markowitz optimization to capture modern regime
    optimizer = PortfolioOptimizer(lookback_years=20)
    tickers = ['^GSPC', '^GSPTSE', 'VEURX', 'EMF']
    
    # 1. Calculate Efficient Frontier (Markowitz)
    mvo_results = optimizer.optimize(tickers, min_weight=0.05, max_weight=0.60)
    
    # 2. Calculate GDP-Biased Weights (Macro)
    # Using 2024 latest weights as representative
    dao = MacroDAO()
    gdp_data = dao.fetch_world_bank_gdp(["CAN", "USA", "EMU", "CHN", "IND"], start_year=2023)
    gdp_weights_raw = dao.calculate_biased_gdp_weights(gdp_data, home_bias=0.25).iloc[-1]
    
    # Map GDP countries to Tickers
    # CAN -> ^GSPTSE, USA -> ^GSPC, EMU -> VEURX, (CHN+IND) -> EMF
    gdp_weights = {
        '^GSPC': float(gdp_weights_raw['USA']),
        '^GSPTSE': float(gdp_weights_raw['CAN']),
        'VEURX': float(gdp_weights_raw['EMU']),
        'EMF': float(gdp_weights_raw['CHN'] + gdp_weights_raw['IND'])
    }

    # 3. Compile Comparison
    df_comp = pd.DataFrame({
        'GDP-Biased (Macro)': pd.Series(gdp_weights),
        'Max Sharpe (Math)': pd.Series(mvo_results['optimal']['weights']),
        'Min Vol (Safe)': pd.Series(mvo_results['alternatives'][0]['weights'])
    })

    print("\nALLOCATION STRATEGY COMPARISON")
    print("=" * 60)
    print(df_comp.applymap(lambda x: f"{x*100:.1f}%"))
    print("-" * 60)
    
    print(f"\nExpected Annual Return (Max Sharpe): {mvo_results['optimal']['expected_return']*100:.2f}%")
    print(f"Historical Volatility (Max Sharpe):  {mvo_results['optimal']['volatility']*100:.2f}%")
    print(f"Sharpe Ratio:                        {mvo_results['optimal']['sharpe_ratio']:.2f}")
    print("=" * 60)
    
    return df_comp

if __name__ == "__main__":
    run_comparison()
