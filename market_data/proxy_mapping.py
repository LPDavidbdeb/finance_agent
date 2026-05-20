"""
Translation layer between user-facing ETFs and the historical benchmark proxies
used by the probability Oracle.

This module intentionally keeps the lifecycle engine detached from raw Yahoo
tickers and market-history implementation details.
"""

from __future__ import annotations

from typing import Dict, Optional


ETF_TO_PROXY_MAP: dict[str, dict[str, float]] = {
    # Canadian Equity
    "VCN.TO": {"^GSPTSE": 1.0},
    "XIC.TO": {"^GSPTSE": 1.0},

    # US Equity
    "XUU.TO": {"^GSPC": 1.0},
    "VUN.TO": {"^GSPC": 1.0},

    # International / Emerging
    "XEF.TO": {"^N100": 1.0},
    "XEC.TO": {"EEM": 1.0},

    # Global ex-Canada (decomposed into foundational proxies)
    "XAW.TO": {
        "^GSPC": 0.60,
        "^N100": 0.30,
        "EEM": 0.10,
    },

    # All-in-one portfolios (decomposed)
    "VEQT.TO": {
        "^GSPC": 0.45,
        "^GSPTSE": 0.30,
        "^N100": 0.18,
        "EEM": 0.07,
    },
}


def translate_portfolio_to_proxies(
    user_portfolio: Dict[str, float],
    proxy_map: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, float]:
    """
    Translate a dictionary of ETF holdings and weights into a blended proxy basket.

    Raises:
        ValueError: If the portfolio is empty, weights do not sum to a positive
        value, or a holding lacks a defined proxy mapping.
    """

    if not user_portfolio:
        raise ValueError("user_portfolio must not be empty")

    proxy_weights: Dict[str, float] = {}
    mapping = proxy_map or ETF_TO_PROXY_MAP
    total = sum(float(weight) for weight in user_portfolio.values())
    if total <= 0:
        raise ValueError("user_portfolio must sum to a positive value")

    for etf, weight in user_portfolio.items():
        if etf not in mapping:
            raise ValueError(f"ETF {etf} lacks a defined benchmark proxy mapping.")

        etf_mapping = mapping[etf]
        mapping_total = sum(etf_mapping.values())
        if mapping_total <= 0:
            raise ValueError(f"Proxy mapping for {etf} must sum to a positive value")

        normalized_weight = float(weight) / float(total)
        for proxy_ticker, proxy_allocation in etf_mapping.items():
            actual_weight = normalized_weight * (float(proxy_allocation) / float(mapping_total))
            proxy_weights[proxy_ticker] = proxy_weights.get(proxy_ticker, 0.0) + actual_weight

    normalized_total = sum(proxy_weights.values())
    return {ticker: value / normalized_total for ticker, value in proxy_weights.items()}
