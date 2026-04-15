import numpy as np
import pandas as pd
from typing import Dict, Union, Optional
from dataclasses import dataclass

@dataclass
class SeasonalityResult:
    is_seasonal: bool
    max_correlation: float
    best_lag: int

class SeasonalityAnalyzer:
    """
    EPIC 2.3: Seasonality Robustness (Axis 4) for the Financial Inference Engine.
    Detects stable annual patterns with lag tolerance for billing drifts.
    """

    def __init__(
        self, 
        correlation_threshold: float = 0.7,
        lags: list[int] = [-1, 0, 1]
    ):
        self.correlation_threshold = correlation_threshold
        self.lags = lags

    def analyze(self, series: pd.Series) -> SeasonalityResult:
        """
        Calculates lag-tolerant cross-correlation for 12-month cycles.
        
        Args:
            series (pd.Series): Time series of monthly spend.
            
        Returns:
            SeasonalityResult: Contains is_seasonal, max_correlation, and best_lag.
        """
        if not isinstance(series, pd.Series):
            series = pd.Series(series)

        n = len(series)
        
        # Requirement: At least 24 months of data
        if n < 24:
            return SeasonalityResult(is_seasonal=False, max_correlation=0.0, best_lag=0)

        # Take the last 24 months
        data = series.tail(24).values
        y1 = data[:12] # Year 1 (older)
        y2 = data[12:] # Year 2 (recent)

        max_corr = -1.0
        best_lag = 0

        # Check Pearson correlation for each lag state (-1, 0, +1)
        for lag in self.lags:
            # We shift y2 relative to y1
            # Lag 0: compare y1[0:12] to y2[0:12]
            # Lag +1: compare y1[0:11] to y2[1:12]
            # Lag -1: compare y1[1:12] to y2[0:11]
            
            if lag == 0:
                s1 = y1
                s2 = y2
            elif lag == 1:
                s1 = y1[:-1]
                s2 = y2[1:]
            elif lag == -1:
                s1 = y1[1:]
                s2 = y2[:-1]
            else:
                continue

            # Standardize to avoid issues with zero variance
            if np.std(s1) == 0 or np.std(s2) == 0:
                # If one year is perfectly flat but the other isn't, they are not seasonal
                # unless BOTH are flat, but flat isn't "seasonal" in a useful way.
                corr = 1.0 if (np.std(s1) == 0 and np.std(s2) == 0 and s1[0] == s2[0]) else 0.0
            else:
                corr = np.corrcoef(s1, s2)[0, 1]
            
            if corr > max_corr:
                max_corr = corr
                best_lag = lag

        is_seasonal = max_corr > self.correlation_threshold

        return SeasonalityResult(
            is_seasonal=bool(is_seasonal),
            max_correlation=float(max_corr),
            best_lag=best_lag
        )
