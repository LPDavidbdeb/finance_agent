"""
Tests for the Oracle boundary used by the lifecycle engine.
"""

from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from market_data.proxy_mapping import ETF_TO_PROXY_MAP, translate_portfolio_to_proxies
from planning.oracle import (
    OracleEvaluationRequest,
    PortfolioOracle,
    LifecycleOracle,
    classify_goal_probability,
    translate_asset_allocation_to_proxy_basket,
)


class TestOracleMapping:
    def test_proxy_mapping_module_translates_all_in_one_etf(self):
        result = translate_portfolio_to_proxies({"XAW.TO": 1.0})

        assert abs(sum(result.values()) - 1.0) < 1e-9
        assert result["^GSPC"] > result["EEM"]
        assert set(result).issuperset({"^GSPC", "^N100", "EEM"})

    def test_translate_asset_allocation_to_proxy_basket_normalizes_and_merges(self):
        proxy_mapping = {
            "XAW.TO": {"^GSPC": 0.45, "^GSPTSE": 0.25, "^N100": 0.25, "EEM": 0.05},
            "XUU.TO": {"^GSPC": 1.0},
        }

        result = translate_asset_allocation_to_proxy_basket(
            {"XAW.TO": 0.5, "XUU.TO": 0.5},
            proxy_mapping=proxy_mapping,
        )

        assert abs(sum(result.values()) - 1.0) < 1e-9
        assert result["^GSPC"] > result["EEM"]
        assert result["^GSPTSE"] > 0

    def test_classify_goal_probability_thresholds(self):
        assert classify_goal_probability(0.95)[0] == "On Track"
        assert classify_goal_probability(0.75)[0] == "Cash Flow Re-routing"
        assert classify_goal_probability(0.25)[0] == "Asset Allocation / Timeline Warning"


class TestLifecycleOracle:
    def test_evaluate_goal_probability_returns_routing_payload(self):
        with patch("planning.oracle.PortfolioOracle.evaluate") as mock_eval:
            mock_eval.return_value = type(
                "R",
                (),
                {
                    "prob_lump_sum": 0.94,
                    "prob_dca": 0.91,
                    "goal_status": "On Track",
                    "recommendation": "No routing change required. Maintain the current allocation and contribution plan.",
                    "proxy_allocation": {"^GSPC": 0.6, "^N100": 0.4},
                },
            )

            result = LifecycleOracle.evaluate_goal_probability(
                user_portfolio={"XAW.TO": 1.0},
                target_net_return=0.05,
                horizon_years=15,
                blended_mer=0.0012,
                cache_path="notebooks/price_series.pkl",
            )

        assert result["goal_status"] == "On Track"
        assert result["dca_prob"] == 0.91
        assert result["proxy_basket"] == {"^GSPC": 0.6, "^N100": 0.4}
        mock_eval.assert_called_once()


class TestPortfolioOracle:
    def test_evaluate_returns_goal_status_and_probabilities(self):
        dates = pd.date_range("2020-01-01", periods=400, freq="B")
        prices = pd.DataFrame(
            {"PROXY": 100.0 * (1.0015 ** np.arange(len(dates)))},
            index=dates,
        )

        request = OracleEvaluationRequest(
            horizon_years=1,
            target_net_return=0.0,
            blended_mer=0.0012,
            asset_allocation={"XUU.TO": 1.0},
            monthly_dca_amount=1000.0,
            rebalance_freq_months=1,
            cache_path=None,
            proxy_mapping={"XUU.TO": {"PROXY": 1.0}},
        )

        with patch("planning.oracle.YahooDAO.fetch_adjusted_close", return_value=prices) as mock_fetch:
            response = PortfolioOracle.evaluate(request)

        mock_fetch.assert_called_once()
        assert response.source == "yahoo_proxy"
        assert response.goal_status == "On Track"
        assert response.prob_lump_sum == 1.0
        assert response.prob_dca == 1.0
        assert response.proxy_allocation == {"PROXY": 1.0}
        assert response.gross_hurdle > 0
        assert response.monthly_hurdle > 0


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
