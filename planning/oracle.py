from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel
from numpy.lib.stride_tricks import sliding_window_view

from market_data.yahoo_dao import YahooDAO
from market_data.proxy_mapping import ETF_TO_PROXY_MAP, translate_portfolio_to_proxies


class OracleEvaluationRequest(BaseModel):
    """Standardized input for the historical probability Oracle."""

    horizon_years: int
    target_net_return: float
    blended_mer: float
    asset_allocation: Dict[str, float]
    monthly_dca_amount: float = 1000.0
    rebalance_freq_months: int = 1
    cache_path: Optional[str] = None
    proxy_mapping: Optional[Dict[str, Dict[str, float]]] = None


class OracleEvaluationResponse(BaseModel):
    """Standardized output for lifecycle goal scoring."""

    horizon_years: int
    target_net_return: float
    blended_mer: float
    gross_hurdle: float
    monthly_hurdle: float
    prob_lump_sum: float
    prob_dca: float
    goal_status: str
    recommendation: str
    proxy_allocation: Dict[str, float]
    source: str
    count: int


def translate_asset_allocation_to_proxy_basket(
    asset_allocation: Dict[str, float],
    proxy_mapping: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, float]:
    """Translate a user-facing ETF allocation into a proxy basket allocation."""

    return translate_portfolio_to_proxies(asset_allocation, proxy_map=proxy_mapping or ETF_TO_PROXY_MAP)


def classify_goal_probability(probability: float) -> tuple[str, str]:
    """Map probability to the lifecycle engine's user-facing status and action."""

    if probability >= 0.90:
        return "On Track", "No routing change required. Maintain the current allocation and contribution plan."
    if probability >= 0.50:
        return (
            "Cash Flow Re-routing",
            "Consider increasing monthly contributions or re-routing excess cash flow toward the goal."
        )
    return (
        "Asset Allocation / Timeline Warning",
        "Review the asset mix or extend the timeline; the current plan is below the target success threshold."
    )


def _build_proxy_portfolio_index(
    proxy_allocation: Dict[str, float],
    cache_path: Optional[str] = None,
) -> tuple[pd.Series, str]:
    """Fetch proxy data and convert it into a synthetic monthly index."""

    tickers = list(proxy_allocation.keys())
    df_daily = YahooDAO.fetch_adjusted_close(
        tickers=tickers,
        period="max",
        cache_path=cache_path,
    )

    daily_returns = df_daily.pct_change().dropna()
    weights = np.array([proxy_allocation[t] for t in tickers], dtype=float)
    port_daily_returns = daily_returns.dot(weights)
    synthetic_index_daily = (1 + port_daily_returns).cumprod() * 100
    monthly_series = synthetic_index_daily.resample("ME").last().dropna()
    return monthly_series, "yahoo_proxy"


class PortfolioOracle:
    """Oracle service that evaluates probability thresholds from proxy data."""

    @staticmethod
    def evaluate(request: OracleEvaluationRequest) -> OracleEvaluationResponse:
        proxy_allocation = translate_asset_allocation_to_proxy_basket(
            request.asset_allocation,
            proxy_mapping=request.proxy_mapping,
        )
        monthly_series, source = _build_proxy_portfolio_index(
            proxy_allocation,
            cache_path=request.cache_path,
        )

        prices = monthly_series.values
        horizon_years = int(request.horizon_years)
        months_in_window = horizon_years * 12
        if len(prices) <= months_in_window:
            raise ValueError(
                f"Insufficient monthly data ({len(prices)} points) for {horizon_years}-year horizon"
            )

        gross_hurdle = ((1 + float(request.target_net_return)) / (1 - float(request.blended_mer))) - 1
        monthly_hurdle = (1 + gross_hurdle) ** (1 / 12) - 1

        windows = sliding_window_view(prices, window_shape=months_in_window + 1)
        start_prices = windows[:, 0]
        end_prices = windows[:, -1]
        lump_sum_cagr = (end_prices / start_prices) ** (1 / horizon_years) - 1

        contrib_prices = windows[:, 1:]
        monthly_contribution = float(request.monthly_dca_amount)
        shares_acquired = monthly_contribution * np.sum(1.0 / contrib_prices, axis=1)
        fv_actual = end_prices * shares_acquired

        months_invested = np.arange(months_in_window - 1, -1, -1)
        fv_target = monthly_contribution * np.sum((1 + monthly_hurdle) ** months_invested)

        prob_lump_sum = float(np.mean(lump_sum_cagr >= gross_hurdle))
        prob_dca = float(np.mean(fv_actual >= fv_target))

        goal_status, recommendation = classify_goal_probability(prob_dca)

        return OracleEvaluationResponse(
            horizon_years=horizon_years,
            target_net_return=float(request.target_net_return),
            blended_mer=float(request.blended_mer),
            gross_hurdle=float(gross_hurdle),
            monthly_hurdle=float(monthly_hurdle),
            prob_lump_sum=prob_lump_sum,
            prob_dca=prob_dca,
            goal_status=goal_status,
            recommendation=recommendation,
            proxy_allocation=proxy_allocation,
            source=source,
            count=int(len(lump_sum_cagr)),
        )


class LifecycleOracle:
    """Lifecycle-facing Oracle wrapper that hides market-data internals."""

    @staticmethod
    def evaluate_goal_probability(
        user_portfolio: Dict[str, float],
        target_net_return: float,
        horizon_years: int,
        blended_mer: float = 0.0012,
        monthly_dca_amount: float = 1000.0,
        rebalance_freq_months: int = 1,
        cache_path: Optional[str] = None,
        proxy_mapping: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, float | str | Dict[str, float]]:
        """
        Evaluate a goal from the perspective of the lifecycle engine.

        The lifecycle engine provides real ETF holdings; the Oracle translates
        them to proxies, computes the historical probabilities, and returns a
        compact routing payload for the deterministic ledger layer.
        """

        proxy_basket = translate_portfolio_to_proxies(
            user_portfolio,
            proxy_map=proxy_mapping,
        )

        result = PortfolioOracle.evaluate(
            OracleEvaluationRequest(
                horizon_years=horizon_years,
                target_net_return=target_net_return,
                blended_mer=blended_mer,
                asset_allocation=proxy_basket,
                monthly_dca_amount=monthly_dca_amount,
                rebalance_freq_months=rebalance_freq_months,
                cache_path=cache_path,
            )
        )

        return {
            "lump_sum_prob": result.prob_lump_sum,
            "dca_prob": result.prob_dca,
            "goal_status": result.goal_status,
            "recommendation": result.recommendation,
            "proxy_basket": result.proxy_allocation,
        }
