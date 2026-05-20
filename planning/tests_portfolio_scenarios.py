"""
Tests for portfolio optimization and return calculations.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import numpy as np
import pandas as pd

from market_data.yahoo_dao import YahooDAO
from planning.optimization import PortfolioOptimizer
from planning.returns import PortfolioReturnsCalculator


def _make_adj_close_frame(index, column_values):
    frame = pd.DataFrame(column_values, index=index)
    frame.columns = pd.MultiIndex.from_product([["Adj Close"], frame.columns])
    return frame


class TestPortfolioOptimizer:
    """Tests for PortfolioOptimizer."""

    def test_optimizer_weights_sum_to_one(self):
        """Optimized weights should sum to 1."""
        optimizer = PortfolioOptimizer()
        
        # Create synthetic price data (for testing without network)
        dates = pd.date_range(start='2021-01-01', end='2026-01-01', freq='D')
        tickers = ['XIU.TO', 'XWD.TO']
        
        # Generate synthetic prices (simple random walk)
        np.random.seed(42)
        data = {}
        for ticker in tickers:
            prices = 100 + np.cumsum(np.random.randn(len(dates)) * 2)
            data[ticker] = prices
        
        prices_df = pd.DataFrame(data, index=dates)
        
        # Mock the fetch_prices to return our synthetic data
        optimizer.fetch_prices = lambda tickers: prices_df[tickers]
        
        result = optimizer.optimize(tickers)
        
        optimal_weights = result['optimal']['weights']
        total_weight = sum(optimal_weights.values())
        
        assert abs(total_weight - 1.0) < 1e-5, f"Weights sum to {total_weight}, expected 1.0"

    def test_optimizer_bounds_respected(self):
        """Weights should respect min/max bounds."""
        optimizer = PortfolioOptimizer()
        
        dates = pd.date_range(start='2021-01-01', end='2026-01-01', freq='D')
        tickers = ['XIU.TO', 'XWD.TO']
        
        np.random.seed(42)
        data = {}
        for ticker in tickers:
            prices = 100 + np.cumsum(np.random.randn(len(dates)) * 2)
            data[ticker] = prices
        
        prices_df = pd.DataFrame(data, index=dates)
        optimizer.fetch_prices = lambda tickers: prices_df[tickers]
        
        result = optimizer.optimize(tickers, min_weight=0.1, max_weight=0.9)
        
        weights = result['optimal']['weights']
        for w in weights.values():
            assert 0.1 <= w <= 0.9, f"Weight {w} outside bounds [0.1, 0.9]"

    def test_sharpe_ratio_positive(self):
        """Optimal Sharpe ratio should be positive for reasonable data."""
        optimizer = PortfolioOptimizer()
        
        dates = pd.date_range(start='2021-01-01', end='2026-01-01', freq='D')
        tickers = ['XIU.TO', 'XWD.TO']
        
        np.random.seed(42)
        data = {}
        for ticker in tickers:
            # Upward trend + noise
            prices = 100 * (1.05 ** (np.arange(len(dates)) / 252)) + np.random.randn(len(dates)) * 2
            data[ticker] = prices
        
        prices_df = pd.DataFrame(data, index=dates)
        optimizer.fetch_prices = lambda tickers: prices_df[tickers]
        
        result = optimizer.optimize(tickers)
        
        sharpe = result['optimal']['sharpe_ratio']
        assert sharpe > -1, f"Sharpe ratio {sharpe} unexpectedly low"


class TestPortfolioReturnsCalculator:
    """Tests for PortfolioReturnsCalculator."""

    def test_lump_sum_returns_count(self):
        """Rolling windows should produce N - H samples."""
        # Create simple 100-day price series
        prices = np.linspace(100, 110, 100)
        portfolio_series = pd.Series(prices)
        
        horizon_days = 10
        result = PortfolioReturnsCalculator.compute_lump_sum_returns(
            portfolio_series, horizon_days
        )
        
        expected_count = len(prices) - horizon_days
        assert len(result['returns']) == expected_count, \
            f"Expected {expected_count} returns, got {len(result['returns'])}"

    def test_portfolio_stats_keys(self):
        """Portfolio stats should have all required keys."""
        returns = [0.01, 0.02, -0.01, 0.03, 0.00]
        stats = PortfolioReturnsCalculator._compute_stats(np.array(returns))
        
        required_keys = [
            'mean', 'median', 'std', 'min', 'max', 'skewness', 'kurtosis',
            'percentile_5', 'percentile_25', 'percentile_50', 'percentile_75', 'percentile_95'
        ]
        
        for key in required_keys:
            assert key in stats, f"Missing key: {key}"

    def test_annualized_return(self):
        """Annualized return calculation should be correct."""
        # 10% total return over 2 years should be ~4.88% annualized
        total_return = 0.10
        horizon_years = 2
        
        annualized = PortfolioReturnsCalculator.compute_annualized_return(total_return, horizon_years)
        
        # (1.10)^(1/2) - 1 ≈ 0.04881
        expected = (1 + total_return) ** (1 / horizon_years) - 1
        assert abs(annualized - expected) < 1e-6, \
            f"Annualized return {annualized} != expected {expected}"

    def test_histogram_bins_non_empty(self):
        """Histogram should produce bins for non-empty returns."""
        returns = [0.01, 0.02, -0.01, 0.03, 0.00, 0.015]
        edges, counts = PortfolioReturnsCalculator.compute_histogram_bins(returns, n_bins=10)
        
        assert len(edges) > 0, "Expected non-empty histogram edges"
        assert len(counts) > 0, "Expected non-empty histogram counts"
        assert len(counts) == len(edges) - 1, "Counts should be one less than edges"

    def test_kde_points_non_empty(self):
        """KDE should produce points for non-empty returns."""
        returns = [0.01, 0.02, -0.01, 0.03, 0.00, 0.015, 0.025, -0.005]
        x, y = PortfolioReturnsCalculator.compute_kde_points(returns, n_points=100)
        
        assert len(x) == 100, f"Expected 100 KDE x-points, got {len(x)}"
        assert len(y) == 100, f"Expected 100 KDE y-points, got {len(y)}"
        assert all(yd > 0 for yd in y), "All KDE density values should be positive"

    def test_lump_sum_and_dca_are_exact_on_simple_series(self, monkeypatch):
        """A one-asset synthetic series should produce exact, manually verifiable outputs."""
        monkeypatch.setattr(PortfolioReturnsCalculator, "TRADING_DAYS_PER_YEAR", 2)

        prices = pd.DataFrame(
            {"SINGLE": [100.0, 110.0, 121.0]},
            index=pd.date_range("2026-01-01", periods=3, freq="D"),
        )
        weights = {"SINGLE": 1.0}

        portfolio = PortfolioReturnsCalculator.compute_portfolio_price_series(prices, weights)

        lump = PortfolioReturnsCalculator.compute_lump_sum_returns(portfolio, horizon_days=2)
        assert pytest.approx(lump["returns"][0], abs=1e-4) == 0.21

        dca = PortfolioReturnsCalculator.compute_dca_returns(
            prices,
            weights,
            horizon_years=1,
            monthly_contribution=1000.0,
            rebalance_freq_months=1 / 21,
        )
        assert pytest.approx(dca["returns"][0], abs=1e-4) == 0.05


class TestYahooDAO:
    """Tests for YahooDAO cache and fetch behavior."""

    def test_incremental_fetch_returns_cached_data_on_empty_yfinance_response(self, tmp_path):
        """An empty incremental fetch should fall back to the cached DataFrame."""
        today = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
        yesterday = today - pd.Timedelta(days=1)

        cache_df = pd.DataFrame(
            {"XIU.TO": [100.0, 101.0], "XWD.TO": [200.0, 202.0]},
            index=pd.to_datetime([yesterday - pd.Timedelta(days=1), yesterday]),
        )
        cache_path = tmp_path / "prices.pkl"
        cache_df.to_pickle(cache_path)

        with patch("market_data.yahoo_dao.yf.download", return_value=pd.DataFrame()) as mock_download:
            result = YahooDAO.fetch_adjusted_close(["XIU.TO", "XWD.TO"], cache_path=str(cache_path))

        assert mock_download.call_count == 1
        assert result.equals(cache_df)

    def test_incremental_fetch_merges_new_rows_into_cache(self, tmp_path):
        """An incremental fetch should merge fresh rows and update the cache on disk."""
        today = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
        yesterday = today - pd.Timedelta(days=1)
        tomorrow = today + pd.Timedelta(days=1)

        cache_df = pd.DataFrame(
            {"XIU.TO": [100.0, 101.0], "XWD.TO": [200.0, 202.0]},
            index=pd.to_datetime([yesterday - pd.Timedelta(days=1), yesterday]),
        )
        cache_path = tmp_path / "prices.pkl"
        cache_df.to_pickle(cache_path)

        raw = _make_adj_close_frame(
            pd.to_datetime([today, tomorrow]),
            {
                "XIU.TO": [102.0, 103.0],
                "XWD.TO": [204.0, 206.0],
            },
        )

        with patch("market_data.yahoo_dao.yf.download", return_value=raw) as mock_download:
            result = YahooDAO.fetch_adjusted_close(["XIU.TO", "XWD.TO"], cache_path=str(cache_path))

        assert mock_download.call_count == 1
        assert len(result) == 4
        assert result.iloc[-1]["XIU.TO"] == 103.0
        assert result.iloc[-1]["XWD.TO"] == 206.0
        assert pd.read_pickle(cache_path).equals(result)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
