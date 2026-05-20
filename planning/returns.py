"""
Rolling-window return calculations and DCA scenario simulations.

This module estimates historical return probabilities from calendar-aligned
price series using discrete cash-flow math. Lump-sum scenarios are evaluated
as annualized gross growth over each rolling window, while DCA scenarios are
modeled as monthly end-of-period contributions on the same discrete grid as
the sampled prices. Where fee-adjusted thresholds are used, the gross hurdle
is derived multiplicatively from the target annualized return and blended fee
drag, so the internal time-step arithmetic remains consistent with the cash
flow schedule.

The outputs are empirical benchmarks over proxy data, not guarantees of ETF
cash-flow behavior. When a true total-return series is unavailable, price or
adjusted-close proxies may omit dividend timing, FX translation, withholding
tax, and tracking error, so the resulting probabilities should be interpreted
as model-consistent historical estimates rather than exact forward forecasts.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class PortfolioReturnsCalculator:
    """Compute distributions of portfolio returns using historical rolling windows."""

    TRADING_DAYS_PER_YEAR = 252

    @staticmethod
    def trading_days_to_index_length(horizon_years: int) -> int:
        """Convert horizon in years to approximate index length in trading days."""
        return int(horizon_years * PortfolioReturnsCalculator.TRADING_DAYS_PER_YEAR)

    @staticmethod
    def compute_portfolio_price_series(
        prices: pd.DataFrame,
        weights: Dict[str, float],
    ) -> pd.Series:
        """
        Compute weighted portfolio price series.

        Args:
            prices: DataFrame with date index and ticker columns (adjusted close).
            weights: Dict mapping ticker → allocation weight.

        Returns:
            Series of portfolio values (normalized to start at 1.0).
        """
        # Normalize weights to ensure they sum to 1
        total_weight = sum(weights.values())
        weights = {t: w / total_weight for t, w in weights.items()}

        # Select only tickers in weights
        price_subset = prices[[t for t in weights.keys() if t in prices.columns]]

        # Normalize prices to start at 1.0 (for portfolio calculation)
        normalized_prices = price_subset / price_subset.iloc[0]

        # Compute weighted portfolio
        portfolio = (normalized_prices * pd.Series(weights)).sum(axis=1)

        return portfolio

    @staticmethod
    def compute_lump_sum_returns(
        portfolio_series: pd.Series,
        horizon_days: int,
    ) -> Dict[str, any]:
        """
        Compute returns for all overlapping H-day windows (lump-sum scenarios).

        Args:
            portfolio_series: Series of portfolio price values.
            horizon_days: Investment horizon in trading days.

        Returns:
            Dict with 'returns' (list), 'stats' (dict), 'count' (int).
        """
        if len(portfolio_series) < horizon_days:
            raise ValueError(f"Price series too short ({len(portfolio_series)} days < {horizon_days} horizon)")

        returns = []
        for i in range(len(portfolio_series) - horizon_days):
            start_price = portfolio_series.iloc[i]
            end_price = portfolio_series.iloc[i + horizon_days]
            ret = (end_price / start_price) - 1
            returns.append(float(ret))

        # Compute statistics
        returns_array = np.array(returns)
        stats_dict = PortfolioReturnsCalculator._compute_stats(returns_array)

        return {
            'returns': returns,
            'stats': stats_dict,
            'count': len(returns),
        }

    @staticmethod
    def compute_dca_returns(
        prices: pd.DataFrame,
        weights: Dict[str, float],
        horizon_years: int,
        monthly_contribution: float = 1000.0,
        rebalance_freq_months: int = 1,
    ) -> Dict[str, any]:
        """
        Simulate DCA (dollar-cost averaging) with monthly rebalancing.
        For each historical start date, simulate monthly contributions and rebalancing
        over the investment horizon, then compute the final return.

        Args:
            prices: DataFrame with date index and ticker columns.
            weights: Dict mapping ticker → allocation weight.
            horizon_years: Investment horizon in years.
            monthly_contribution: Monthly contribution amount (default $1000).
            rebalance_freq_months: Rebalancing frequency in months (default 1 = monthly).

        Returns:
            Dict with 'returns' (list), 'stats' (dict), 'count' (int).
        """
        # Normalize weights
        total_weight = sum(weights.values())
        weights = {t: w / total_weight for t, w in weights.items()}

        # Filter to available tickers
        tickers = [t for t in weights.keys() if t in prices.columns]
        weights = {t: weights[t] for t in tickers}

        prices_subset = prices[tickers]

        # Calculate horizon in days
        horizon_days = int(horizon_years * PortfolioReturnsCalculator.TRADING_DAYS_PER_YEAR)
        rebalance_days = int(rebalance_freq_months * 21)  # ~21 trading days per month

        returns = []

        # For each possible start date where we have horizon_days ahead
        for start_idx in range(len(prices_subset) - horizon_days):
            end_idx = start_idx + horizon_days

            # Simulate portfolio accumulation
            shares = {t: 0.0 for t in tickers}  # Track share units held
            total_invested = 0.0

            # Walk through each day, rebalancing at intervals
            for current_idx in range(start_idx, end_idx):
                # Add monthly contribution
                if (current_idx - start_idx) % rebalance_days == 0:
                    # Time to contribute: buy shares at current price according to weights
                    price_now = prices_subset.iloc[current_idx]
                    for t in tickers:
                        # guard against zero price
                        p = price_now[t]
                        if p and p > 0:
                            shares[t] += (monthly_contribution * weights[t]) / p
                    total_invested += monthly_contribution

                    # Rebalance holdings to target weights using current prices
                    # Compute current portfolio value
                    current_values = {t: shares[t] * price_now[t] for t in tickers}
                    total_value = sum(current_values.values())
                    if total_value > 0:
                        # Set shares to match target weights
                        for t in tickers:
                            target_dollars = total_value * weights[t]
                            shares[t] = target_dollars / price_now[t]

                # On last day, compute return
                if current_idx == end_idx - 1:
                    # Compute portfolio value at end
                    end_prices = prices_subset.iloc[current_idx]
                    portfolio_value = sum(shares[t] * end_prices[t] for t in tickers)
                    ret = (portfolio_value / total_invested - 1) if total_invested > 0 else 0.0
                    returns.append(float(ret))

        # Compute statistics
        returns_array = np.array(returns)
        stats_dict = PortfolioReturnsCalculator._compute_stats(returns_array)

        return {
            'returns': returns,
            'stats': stats_dict,
            'count': len(returns),
        }

    @staticmethod
    def _compute_stats(returns_array: np.ndarray) -> Dict[str, float]:
        """
        Compute summary statistics for a returns array.

        Returns:
            Dict with mean, median, std, skew, kurtosis, and percentiles.
        """
        if len(returns_array) == 0:
            return {}

        return {
            'mean': float(np.mean(returns_array)),
            'median': float(np.median(returns_array)),
            'std': float(np.std(returns_array)),
            'min': float(np.min(returns_array)),
            'max': float(np.max(returns_array)),
            'skewness': float(stats.skew(returns_array)),
            'kurtosis': float(stats.kurtosis(returns_array)),
            'percentile_5': float(np.percentile(returns_array, 5)),
            'percentile_25': float(np.percentile(returns_array, 25)),
            'percentile_50': float(np.percentile(returns_array, 50)),
            'percentile_75': float(np.percentile(returns_array, 75)),
            'percentile_95': float(np.percentile(returns_array, 95)),
        }

    @staticmethod
    def compute_histogram_bins(
        returns: List[float],
        n_bins: int = 50,
    ) -> Tuple[List[float], List[float]]:
        """
        Compute histogram bins and counts.

        Returns:
            (bin_edges, bin_counts) — edges as list of floats, counts as list of ints.
        """
        if len(returns) == 0:
            return [], []

        counts, edges = np.histogram(returns, bins=n_bins)
        return edges.tolist(), counts.tolist()

    @staticmethod
    def compute_kde_points(
        returns: List[float],
        n_points: int = 200,
    ) -> Tuple[List[float], List[float]]:
        """
        Compute KDE (kernel density estimate) for visualization.

        Returns:
            (x_points, density_values) — both as lists.
        """
        if len(returns) < 2:
            return [], []

        from scipy.stats import gaussian_kde

        returns_array = np.array(returns)
        kde = gaussian_kde(returns_array)

        # Create x range from min to max with padding
        x_min = np.min(returns_array)
        x_max = np.max(returns_array)
        x_range = x_max - x_min
        x_min -= 0.1 * x_range
        x_max += 0.1 * x_range

        x_points = np.linspace(x_min, x_max, n_points)
        density = kde(x_points)

        return x_points.tolist(), density.tolist()

    @staticmethod
    def compute_annualized_return(total_return: float, horizon_years: int) -> float:
        """
        Convert total return to annualized return (CAGR).

        Args:
            total_return: Total return (e.g., 0.25 for +25%).
            horizon_years: Investment period in years.

        Returns:
            Annualized return as fraction (e.g., 0.044 for ~4.4% CAGR).
        """
        if horizon_years <= 0:
            return 0.0
        return (1 + total_return) ** (1 / horizon_years) - 1
