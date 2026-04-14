import numpy as np
import pandas as pd
from typing import Dict, Union, List, Optional
from dataclasses import dataclass

@dataclass
class VolatilityResult:
    ser: float
    has_structural_break: bool
    z_scores: Dict[str, float]

class VolatilityAnalyzer:
    """
    EPIC 2.2 & 2.3: Volatility (Axis 2) and Structural Break Detection (Axis 3).
    Quantifies uncertainty and detects sustained step-changes in spending.
    """

    def __init__(
        self, 
        z_threshold: float = 2.0,
        min_shift_months: int = 3,
        reference_windows: List[int] = [6, 12, 18]
    ):
        self.z_threshold = z_threshold
        self.min_shift_months = min_shift_months
        self.reference_windows = reference_windows

    def calculate_ser(self, actual: pd.Series, predicted: pd.Series) -> float:
        """
        Calculates the Standard Error of the Regression (SER).
        SER = sqrt(sum((y - y_hat)^2) / (n - 2))
        """
        if len(actual) <= 2:
            return 0.0
            
        residuals = actual - predicted
        rss = np.sum(residuals**2)
        ser = np.sqrt(rss / (len(actual) - 2))
        return float(ser)

    def detect_structural_break(self, series: pd.Series) -> Dict:
        """
        Detects structural breaks using Multi-Window Z-Score Confirmation.
        
        Args:
            series (pd.Series): Time series of monthly spend.
            
        Returns:
            Dict: { 'has_structural_break': bool, 'z_scores': { '6m': float, ... } }
        """
        n = len(series)
        # We need at least the min_shift + the smallest reference window
        min_required = self.min_shift_months + min(self.reference_windows)
        
        if n < min_required:
            return {"has_structural_break": False, "z_scores": {}}

        # 1. Define the "Recent" window (last 3 months)
        recent_window = series.tail(self.min_shift_months)
        recent_mean = recent_window.mean()
        
        z_scores = {}
        confirmed_breaks = 0
        
        # 2. Check against each historical reference window
        for window_size in self.reference_windows:
            if n < self.min_shift_months + window_size:
                continue
                
            # Historical window ends right before the recent window starts
            hist_start = n - self.min_shift_months - window_size
            hist_end = n - self.min_shift_months
            hist_window = series.iloc[hist_start:hist_end]
            
            hist_mean = hist_window.mean()
            hist_std = hist_window.std()
            
            # Trend correction: Compare recent mean to historical mean + expected growth
            # For simplicity, we compare recent mean to historical mean.
            # However, to avoid false positives for steady growth, we increase the threshold
            # or use a larger buffer.
            # Let's check if the jump is > 2x the historical standard deviation AND significant.
            
            if hist_std == 0 or np.isnan(hist_std):
                # If historical variation is zero, any change is technically infinite Z
                z = (recent_mean - hist_mean) / 1e-9 if recent_mean != hist_mean else 0.0
            else:
                z = (recent_mean - hist_mean) / hist_std
                
            z_scores[f"{window_size}m"] = float(z)
            
            # Requirement: Z-score > threshold (standard)
            # Threshold is typically 3.0 to avoid steady growth false positives
            if abs(z) > self.z_threshold:
                confirmed_breaks += 1

        # Requirement: Flag True ONLY IF Z > 2.0 across multiple windows (>= 2)
        has_structural_break = confirmed_breaks >= 2
        
        return {
            "has_structural_break": has_structural_break,
            "z_scores": z_scores
        }

    def analyze(self, actual: pd.Series, predicted: pd.Series) -> VolatilityResult:
        """
        Performs full volatility and structural break analysis.
        """
        ser = self.calculate_ser(actual, predicted)
        break_info = self.detect_structural_break(actual)
        
        return VolatilityResult(
            ser=ser,
            has_structural_break=break_info["has_structural_break"],
            z_scores=break_info["z_scores"]
        )
