"""
Portfolio optimization using Markowitz model and Sharpe ratio maximization.
Fetches historical prices, computes efficient frontier, and suggests allocations.
"""

import yfinance as yf
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """Optimize portfolio weights to maximize Sharpe ratio."""

    RISK_FREE_RATE = 0.04  # 4% assumed risk-free rate (Canadian GIC equivalent)
    TRADING_DAYS_PER_YEAR = 252

    def __init__(self, lookback_years: int = 5):
        """
        Args:
            lookback_years: Historical data window for optimization (default 5 years).
        """
        self.lookback_years = lookback_years
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=lookback_years * 365)

    def fetch_prices(self, tickers: List[str]) -> pd.DataFrame:
        """
        Fetch adjusted close prices for tickers.

        Args:
            tickers: List of ticker symbols (e.g., ['XIU.TO', 'XWD.TO']).

        Returns:
            DataFrame with date index and ticker columns (daily adjusted close).

        Raises:
            ValueError: If unable to fetch data for any ticker.
        """
        try:
            data = yf.download(
                tickers,
                start=self.start_date,
                end=self.end_date,
                progress=False,
                interval="1d"
            )
            if isinstance(data, pd.DataFrame) and 'Adj Close' in data.columns:
                prices = data['Adj Close']
            elif isinstance(data, pd.Series):
                # Single ticker case
                prices = data.to_frame(name=tickers[0])
            else:
                raise ValueError("Unexpected data format from yfinance")

            # Forward-fill any gaps (e.g., weekends, holidays)
            prices = prices.fillna(method='ffill').dropna()

            if prices.empty:
                raise ValueError("No price data retrieved")

            logger.info(f"Fetched {len(prices)} trading days for {len(tickers)} tickers")
            return prices

        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            raise ValueError(f"Failed to fetch price data: {e}")

    def compute_returns(self, prices: pd.DataFrame, freq: str = 'D') -> pd.DataFrame:
        """
        Compute log returns (handles stocks and dividends via adjusted close).

        Args:
            prices: DataFrame of adjusted close prices.
            freq: Frequency for returns ('D' for daily, 'M' for monthly).

        Returns:
            DataFrame of log returns.
        """
        if freq == 'M':
            prices = prices.resample('M').last()
        
        returns = np.log(prices / prices.shift(1)).dropna()
        return returns

    def compute_statistics(self, returns: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute annualized returns, volatility, and correlation matrix.

        Returns:
            (mean_returns, volatility, correlation_matrix)
        """
        mean_returns = returns.mean() * self.TRADING_DAYS_PER_YEAR
        volatility = returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)
        correlation = returns.corr()

        return mean_returns.values, volatility.values, correlation.values

    def portfolio_stats(
        self,
        weights: np.ndarray,
        mean_returns: np.ndarray,
        volatility: np.ndarray,
        correlation: np.ndarray,
    ) -> Tuple[float, float, float]:
        """
        Compute portfolio expected return, volatility, and Sharpe ratio.

        Returns:
            (portfolio_return, portfolio_volatility, sharpe_ratio)
        """
        cov_matrix = np.outer(volatility, volatility) * correlation
        
        portfolio_return = np.dot(weights, mean_returns)
        portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
        portfolio_volatility = np.sqrt(portfolio_variance)
        
        sharpe_ratio = (portfolio_return - self.RISK_FREE_RATE) / portfolio_volatility if portfolio_volatility > 0 else 0

        return portfolio_return, portfolio_volatility, sharpe_ratio

    def negative_sharpe(
        self,
        weights: np.ndarray,
        mean_returns: np.ndarray,
        volatility: np.ndarray,
        correlation: np.ndarray,
    ) -> float:
        """Objective function: negative Sharpe ratio (for minimization)."""
        _, _, sharpe = self.portfolio_stats(weights, mean_returns, volatility, correlation)
        return -sharpe

    def optimize(
        self,
        tickers: List[str],
        min_weight: float = 0.0,
        max_weight: float = 1.0,
    ) -> Dict:
        """
        Optimize portfolio weights to maximize Sharpe ratio.

        Args:
            tickers: List of ticker symbols.
            min_weight: Minimum weight per ticker.
            max_weight: Maximum weight per ticker.

        Returns:
            Dict with 'optimal' and 'alternatives' allocations.
        """
        # Fetch and compute statistics
        prices = self.fetch_prices(tickers)
        returns = self.compute_returns(prices)
        mean_returns, volatility, correlation = self.compute_statistics(returns)

        n = len(tickers)
        constraints = (
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},  # weights sum to 1
        )
        bounds = tuple((min_weight, max_weight) for _ in range(n))

        # Optimization 1: Maximize Sharpe ratio
        result_sharpe = minimize(
            self.negative_sharpe,
            x0=np.array([1 / n] * n),
            args=(mean_returns, volatility, correlation),
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
        )

        # Optimization 2: Minimize volatility (for alternative)
        def negative_return(weights):
            ret, _, _ = self.portfolio_stats(weights, mean_returns, volatility, correlation)
            return -ret

        result_min_vol = minimize(
            lambda w: np.dot(w.T, np.dot(
                np.outer(volatility, volatility) * correlation, w
            )),
            x0=np.array([1 / n] * n),
            args=(),
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
        )

        # Equal-weight for comparison
        equal_weights = np.array([1 / n] * n)

        # Prepare output
        optimal_weights = result_sharpe.x
        optimal_return, optimal_vol, optimal_sharpe = self.portfolio_stats(
            optimal_weights, mean_returns, volatility, correlation
        )

        min_vol_weights = result_min_vol.x
        min_vol_return, min_vol_volatility, min_vol_sharpe = self.portfolio_stats(
            min_vol_weights, mean_returns, volatility, correlation
        )

        equal_return, equal_vol, equal_sharpe = self.portfolio_stats(
            equal_weights, mean_returns, volatility, correlation
        )

        return {
            'tickers': tickers,
            'period_start': prices.index[0].strftime('%Y-%m-%d'),
            'period_end': prices.index[-1].strftime('%Y-%m-%d'),
            'optimal': {
                'weights': {t: float(w) for t, w in zip(tickers, optimal_weights)},
                'expected_return': float(optimal_return),
                'volatility': float(optimal_vol),
                'sharpe_ratio': float(optimal_sharpe),
                'label': 'Max Sharpe Ratio',
            },
            'alternatives': [
                {
                    'weights': {t: float(w) for t, w in zip(tickers, min_vol_weights)},
                    'expected_return': float(min_vol_return),
                    'volatility': float(min_vol_volatility),
                    'sharpe_ratio': float(min_vol_sharpe),
                    'label': 'Min Volatility',
                },
                {
                    'weights': {t: float(w) for t, w in zip(tickers, equal_weights)},
                    'expected_return': float(equal_return),
                    'volatility': float(equal_vol),
                    'sharpe_ratio': float(equal_sharpe),
                    'label': 'Equal Weight',
                },
            ],
        }
