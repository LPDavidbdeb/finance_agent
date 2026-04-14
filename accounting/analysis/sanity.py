import pandas as pd
import numpy as np
from typing import Union, Optional

class SanityLayer:
    """
    Step 0 (Part 3): Outlier & Sanity Layer for the Financial Inference Engine.
    Handles extreme outliers (Conditional Winsorization) and isolated missing data.
    """

    def __init__(
        self, 
        percentile_threshold: float = 0.95,
        persistence_threshold: int = 3,
        std_threshold: float = 3.0
    ):
        self.percentile_threshold = percentile_threshold
        self.persistence_threshold = persistence_threshold
        self.std_threshold = std_threshold

    def apply_conditional_winsorization(
        self, 
        series: pd.Series
    ) -> pd.Series:
        """
        Caps extreme outliers (> percentile or > 3 std devs) UNLESS they persist for >= 3 months.
        Persistence indicates a structural break, NOT an outlier.
        
        Args:
            series (pd.Series): Time series of monthly spend.
            
        Returns:
            pd.Series: Cleaned series.
        """
        if len(series) < self.persistence_threshold:
            return series.copy()

        # 1. Identify potential outliers
        # We use non-zero months for statistical thresholds to avoid bias
        non_zero_series = series[series > 0]
        if len(non_zero_series) == 0:
            return series.copy()
            
        upper_limit = non_zero_series.quantile(self.percentile_threshold)
        # Fallback to std dev if percentile is too tight
        std_limit = non_zero_series.mean() + (self.std_threshold * non_zero_series.std())
        
        # Use the more conservative (higher) threshold
        threshold = max(upper_limit, std_limit)
        
        # 2. Identify spikes
        is_spike = series > threshold
        
        # 3. Persistence Check
        # Identify contiguous blocks of spikes
        spike_blocks = (is_spike != is_spike.shift()).cumsum()
        spike_groups = series.groupby(spike_blocks)
        
        # Determine which points belong to a persistent block
        persistence_mask = is_spike & (spike_groups.transform('size') >= self.persistence_threshold)
        
        # 4. Apply Winsorization: Cap only non-persistent spikes
        capped_series = series.copy().astype(float)
        outlier_mask = is_spike & ~persistence_mask
        capped_series[outlier_mask] = threshold
        
        return capped_series

    def impute_missing_periods(
        self, 
        series: pd.Series
    ) -> pd.Series:
        """
        Impute isolated missing months (0 or NaN) surrounded by non-zero months.
        
        Args:
            series (pd.Series): Time series of monthly spend.
            
        Returns:
            pd.Series: Series with isolated zeros imputed.
        """
        if len(series) < 3:
            return series.copy()

        imputed_series = series.copy()
        # Convert 0 to NaN temporarily for interpolation
        imputed_series = imputed_series.replace(0, np.nan)
        
        # Identify isolated NaNs (NaN surrounded by non-NaNs)
        # Mask where current is NaN, prev is NOT NaN, next is NOT NaN
        mask = (
            imputed_series.isna() & 
            imputed_series.shift(1).notna() & 
            imputed_series.shift(-1).notna()
        )
        
        # We only interpolate isolated NaNs to avoid filling long gaps (Episodic series)
        for i in range(1, len(imputed_series) - 1):
            if mask.iloc[i]:
                # Simple linear interpolation between neighbors
                prev_val = imputed_series.iloc[i-1]
                next_val = imputed_series.iloc[i+1]
                imputed_series.iloc[i] = (prev_val + next_val) / 2
        
        # Return to zeros if they weren't isolated
        return imputed_series.fillna(0)

    def process(self, series: Union[list, pd.Series, np.ndarray]) -> pd.Series:
        """
        Applies full sanity layer: Imputation first, then Winsorization.
        """
        if not isinstance(series, pd.Series):
            series = pd.Series(series)
            
        # 1. Fill isolated missing data
        clean_series = self.impute_missing_periods(series)
        
        # 2. Cap non-persistent outliers
        clean_series = self.apply_conditional_winsorization(clean_series)
        
        return clean_series
