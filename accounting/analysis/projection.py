import pandas as pd
import numpy as np
from scipy import stats
from dataclasses import dataclass
from typing import Optional
from .trend import TrendResult
from .volatility import VolatilityResult
from .classification import ProcessType


@dataclass
class ProjectionResult:
    """
    Result of adaptive projection/forecasting.

    Attributes:
        projected_series: pd.Series of projected spending for next 12 months
        upper_bound: pd.Series of upper confidence interval bounds
        lower_bound: pd.Series of lower confidence interval bounds
        selected_model: str - The estimator used (EPISODIC_RESERVE, MEAN_REVERSION, etc.)
    """
    projected_series: pd.Series
    upper_bound: pd.Series
    lower_bound: pd.Series
    selected_model: str


class ProjectionEngine:
    """
    EPIC 4: Adaptive Projection Engine (Hierarchy of Estimators) for the Financial Inference Engine.

    Forecasts the next 12 months of spending by adaptively selecting the best model based on:
    - ProcessType (DETERMINISTIC, STOCHASTIC, EPISODIC)
    - Trend significance (TrendResult.is_significant)
    - Backtest accuracy (Mean Absolute Percentage Error - MAPE)
    - Uncertainty quantification (Standard Error of Regression - SER)

    Hierarchy:
    1. EPISODIC: Annual reserve (90th percentile of non-zero spikes) / 12
    2. DETERMINISTIC: Mean Reversion (recent 6-month mean projected flat)
    3. STOCHASTIC:
       - If Trend.is_significant AND MAPE < 0.20: Regression Trend
       - Else: Adaptive Mean Reversion
    """

    def __init__(
        self,
        mape_threshold: float = 0.20,
        ci_multiplier: float = 1.96,
        reserve_percentile: float = 90.0,
        recent_months_for_mean: int = 6
    ):
        """
        Args:
            mape_threshold: Max MAPE (%) to allow trend-based projection (default 20%)
            ci_multiplier: Multiplier for confidence intervals (default 1.96 for 95% CI)
            reserve_percentile: Percentile for episodic reserve calculation (default 90th)
            recent_months_for_mean: Months to use for mean reversion (default 6)
        """
        self.mape_threshold = mape_threshold
        self.ci_multiplier = ci_multiplier
        self.reserve_percentile = reserve_percentile
        self.recent_months_for_mean = recent_months_for_mean

    def project(
        self,
        historical_series: pd.Series,
        process_type: ProcessType,
        trend_result: TrendResult,
        volatility_result: VolatilityResult,
        reference_date: Optional[pd.Timestamp] = None
    ) -> ProjectionResult:
        """
        Generate adaptive 12-month projection.

        Args:
            historical_series: Monthly spend time series
            process_type: ProcessType (DETERMINISTIC, STOCHASTIC, EPISODIC)
            trend_result: TrendResult from TrendAnalyzer (Epic 2.1)
            volatility_result: VolatilityResult from VolatilityAnalyzer (Epic 2.2)
            reference_date: Optional date to anchor the projection (default: end of series)

        Returns:
            ProjectionResult with projected_series, bounds, and selected_model
        """
        # Validate inputs
        if historical_series.empty:
            raise ValueError("historical_series cannot be empty")
        if len(historical_series) < 2:
            raise ValueError("historical_series must have at least 2 data points")

        # Ensure series is clean
        series = historical_series.copy()
        series = series.fillna(0)

        # Determine reference date
        if reference_date is None:
            reference_date = series.index[-1] if isinstance(series.index, pd.DatetimeIndex) else None

        # Route to appropriate estimator based on ProcessType
        if process_type == ProcessType.EPISODIC:
            return self._project_episodic(series, reference_date)
        elif process_type == ProcessType.DETERMINISTIC:
            return self._project_deterministic(series, reference_date)
        elif process_type == ProcessType.STOCHASTIC:
            return self._project_stochastic(series, trend_result, volatility_result, reference_date)
        else:
            raise ValueError(f"Unknown ProcessType: {process_type}")

    def _project_episodic(
        self,
        series: pd.Series,
        reference_date: Optional[pd.Timestamp]
    ) -> ProjectionResult:
        """
        EPISODIC model: Calculate annual reserve from 90th percentile of non-zero spikes.
        Project flat monthly allocation of Reserve / 12.
        """
        # Calculate 90th percentile of non-zero values
        non_zero = series[series > 0]
        if len(non_zero) == 0:
            annual_reserve = 0.0
        else:
            annual_reserve = float(np.percentile(non_zero, self.reserve_percentile))

        monthly_projection = annual_reserve / 12.0

        # Create 12-month projection
        projected_series = pd.Series(
            [monthly_projection] * 12,
            index=self._generate_future_dates(reference_date)
        )

        # For episodic, bounds are tight (±20% of projection)
        bound_margin = monthly_projection * 0.2
        upper_bound = projected_series + bound_margin
        lower_bound = (projected_series - bound_margin).clip(lower=0)

        return ProjectionResult(
            projected_series=projected_series,
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            selected_model="EPISODIC_RESERVE"
        )

    def _project_deterministic(
        self,
        series: pd.Series,
        reference_date: Optional[pd.Timestamp]
    ) -> ProjectionResult:
        """
        DETERMINISTIC model: Mean Reversion using recent 6-month average.
        Project flat line equal to recent mean.
        """
        # Use recent months for mean calculation
        recent_data = series.tail(self.recent_months_for_mean)
        recent_mean = float(recent_data.mean())

        # Create 12-month projection
        projected_series = pd.Series(
            [recent_mean] * 12,
            index=self._generate_future_dates(reference_date)
        )

        # Bounds based on recent variance
        recent_std = float(recent_data.std())
        bound_margin = self.ci_multiplier * recent_std
        upper_bound = projected_series + bound_margin
        lower_bound = (projected_series - bound_margin).clip(lower=0)

        return ProjectionResult(
            projected_series=projected_series,
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            selected_model="MEAN_REVERSION"
        )

    def _project_stochastic(
        self,
        series: pd.Series,
        trend_result: TrendResult,
        volatility_result: VolatilityResult,
        reference_date: Optional[pd.Timestamp]
    ) -> ProjectionResult:
        """
        STOCHASTIC model: Adaptive selection between Regression Trend and Mean Reversion.

        Decision logic:
        - Calculate MAPE over last 6 months of historical data
        - If TrendResult.is_significant AND MAPE < threshold: Use Regression
        - Else: Fall back to Mean Reversion
        """
        # Calculate MAPE backtest on recent data (last 6 months)
        mape = self._calculate_mape_backtest(series, trend_result)

        # Decision: use regression if trend is significant AND MAPE is low
        if trend_result.is_significant and mape < self.mape_threshold:
            return self._project_regression_trend(series, trend_result, volatility_result, reference_date)
        else:
            # Fallback to Mean Reversion with ADAPTIVE label
            result = self._project_deterministic(series, reference_date)
            result.selected_model = "ADAPTIVE_MEAN_REVERSION"
            return result

    def _project_regression_trend(
        self,
        series: pd.Series,
        trend_result: TrendResult,
        volatility_result: VolatilityResult,
        reference_date: Optional[pd.Timestamp]
    ) -> ProjectionResult:
        """
        Project using log-linear regression trend.
        y_projected = exp(intercept + slope * t) - 1
        """
        # Refit regression to get intercept and slope for projection
        n = len(series)
        y = np.log1p(series.values)
        x = np.arange(n)

        # Handle edge case of zero variance
        if np.std(y) == 0:
            # Fall back to mean reversion if trend line is flat
            result = self._project_deterministic(series, reference_date)
            result.selected_model = "ADAPTIVE_MEAN_REVERSION"
            return result

        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        # Project next 12 months
        future_x = np.arange(n, n + 12)
        future_y_log = intercept + slope * future_x
        future_y = np.expm1(future_y_log)  # Inverse of log1p

        projected_series = pd.Series(
            np.maximum(future_y, 0),  # Ensure non-negative
            index=self._generate_future_dates(reference_date)
        )

        # Confidence bounds using SER
        ser = volatility_result.ser
        bound_margin = self.ci_multiplier * ser
        upper_bound = projected_series + bound_margin
        lower_bound = (projected_series - bound_margin).clip(lower=0)

        return ProjectionResult(
            projected_series=projected_series,
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            selected_model="REGRESSION_TREND"
        )

    @staticmethod
    def _calculate_mape_backtest(series: pd.Series, trend_result: TrendResult) -> float:
        """
        Calculate Mean Absolute Percentage Error (MAPE) of trend line over last 6 months.

        MAPE = (1/n) * sum(|actual - predicted| / |actual|) * 100
        """
        if len(series) < 6:
            return 0.0  # Not enough data, return 0 (accept trend)

        # Get last 6 months
        recent_data = series.tail(6)
        n = len(recent_data)

        # Reconstruct trend line for the last 6 months
        # Use the trend slope from the full series
        # Position indices relative to the recent window
        y_actual = np.log1p(recent_data.values)
        x_indices = np.arange(len(series) - 6, len(series))

        # Generate predicted line using the slope
        # For simplicity, use the trend slope and fit intercept to recent data
        if np.std(y_actual) == 0:
            return 0.0

        # Fit a new regression line on the full series to get consistent slope
        all_y = np.log1p(series.values)
        all_x = np.arange(len(series))
        if np.std(all_y) > 0:
            slope, intercept, _, _, _ = stats.linregress(all_x, all_y)
        else:
            return 0.0

        # Calculate predicted values for recent period
        y_predicted_log = intercept + slope * x_indices
        y_predicted = np.expm1(y_predicted_log)

        # Calculate MAPE on actual values (must be non-zero)
        valid_mask = recent_data.values != 0
        if not valid_mask.any():
            return 0.0  # No non-zero actuals, return 0

        valid_actual = recent_data.values[valid_mask]
        valid_predicted = y_predicted[valid_mask]

        mape = np.mean(np.abs((valid_actual - valid_predicted) / valid_actual)) * 100
        return float(np.clip(mape, 0, 100))  # Clip to reasonable range

    @staticmethod
    def _generate_future_dates(reference_date: Optional[pd.Timestamp]) -> pd.DatetimeIndex:
        """
        Generate 12 future month-end dates starting from reference_date.
        If reference_date is None, use the current date.
        """
        if reference_date is None:
            reference_date = pd.Timestamp.now()

        # Ensure we have a Timestamp
        reference_date = pd.Timestamp(reference_date)

        # Generate monthly dates (end-of-month)
        future_dates = pd.date_range(
            start=reference_date + pd.DateOffset(months=1),
            periods=12,
            freq='ME'  # Month-end
        )
        return future_dates

