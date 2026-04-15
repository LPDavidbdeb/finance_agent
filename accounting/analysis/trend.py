import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, Union, Optional
from dataclasses import dataclass

@dataclass
class TrendResult:
    slope: float
    p_value: float
    is_significant: bool
    is_nonlinear: bool

class TrendAnalyzer:
    """
    EPIC 2.1: Trend & Predictability (Axis 1) for the Financial Inference Engine.
    Computes trajectory (slope), significance, and linearity for active categories.
    """

    def __init__(
        self, 
        p_val_threshold: float = 0.05, 
        effect_size_threshold: float = 0.02,
        non_linear_threshold: float = 0.15
    ):
        self.p_val_threshold = p_val_threshold
        self.effect_size_threshold = effect_size_threshold
        self.non_linear_threshold = non_linear_threshold

    def _get_log_slope(self, series: pd.Series) -> tuple[float, float, float]:
        """
        Fits a log-linear regression: ln(y + 1) ~ t
        Returns: (slope, intercept, p_value)
        """
        n = len(series)
        if n < 2:
            return 0.0, 0.0, 1.0
            
        # Log transformation (ln(y+1))
        y = np.log1p(series.values)
        x = np.arange(n)
        
        # Check for zero variance to avoid warnings/NaNs in linregress
        if np.std(y) == 0:
            return 0.0, y[0], 1.0
            
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        
        return slope, intercept, p_value

    def analyze(self, series: pd.Series) -> TrendResult:
        """
        Performs full trend analysis on a series.
        """
        if not isinstance(series, pd.Series):
            series = pd.Series(series)

        n = len(series)
        
        # 1. Core Log-Linear Regression
        slope, intercept, p_value = self._get_log_slope(series)
        
        # 2. Significance Guardrails
        is_significant = False
        if n >= 6:
            is_significant = p_value < self.p_val_threshold
        else:
            # Use Effect Size (absolute slope > 2%) for small n
            is_significant = abs(slope) > self.effect_size_threshold

        # 3. Non-Linearity Detection (requires n >= 24)
        is_nonlinear = False
        if n >= 24:
            # Overall slope is already calculated as 'slope'
            # Last 24 months slope
            recent_series = series.tail(24)
            recent_slope, _, _ = self._get_log_slope(recent_series)
            
            diff = abs(slope - recent_slope)
            if diff > self.non_linear_threshold:
                is_nonlinear = True

        return TrendResult(
            slope=float(slope),
            p_value=float(p_value),
            is_significant=is_significant,
            is_nonlinear=is_nonlinear
        )
