import pandas as pd
import numpy as np
from typing import List, Union, Dict

class SignalFilter:
    """
    Step 0: Signal Filtering for the Financial Inference Engine.
    Filters out noise, immaterial spending, and heavily sparse datasets before statistical modeling.
    """

    def __init__(
        self, 
        materiality_threshold: float = 0.01,  # Default 1.0%
        sparsity_threshold: float = 0.30      # Default 30%
    ):
        self.materiality_threshold = materiality_threshold
        self.sparsity_threshold = sparsity_threshold

    def classify_materiality(
        self, 
        category_total: float, 
        total_spend: float
    ) -> str:
        """
        Classify a category as 'Muted' or 'Active' based on its percentage of total spend.
        
        Args:
            category_total (float): Total spend for the category in a given window.
            total_spend (float): Total household spend for the same window.
            
        Returns:
            str: 'Muted' if percentage < threshold, otherwise 'Active'.
        """
        if total_spend <= 0:
            return "Muted"
            
        percentage = category_total / total_spend
        return "Muted" if percentage < self.materiality_threshold else "Active"

    def classify_sparsity(
        self, 
        series: Union[List[float], pd.Series, np.ndarray]
    ) -> str:
        """
        Classify a monthly time-series as 'Sparse' or 'Dense'.
        If the series contains >30% zeros (no spend), it is 'Sparse'.
        
        Args:
            series (Union[List[float], pd.Series, np.ndarray]): Monthly spend amounts.
            
        Returns:
            str: 'Sparse' if percentage of zeros > threshold, otherwise 'Dense'.
        """
        if len(series) == 0:
            return "Sparse"
            
        series_arr = np.array(series)
        zero_count = np.count_nonzero(series_arr == 0)
        zero_percentage = zero_count / len(series_arr)
        
        return "Sparse" if zero_percentage > self.sparsity_threshold else "Dense"

    def analyze(
        self, 
        category_series: pd.Series, 
        total_spend: float
    ) -> Dict[str, str]:
        """
        Combines materiality and sparsity checks for a given category.
        
        Args:
            category_series (pd.Series): Time series of monthly spend for a category.
            total_spend (float): Total household spend for the same period.
            
        Returns:
            Dict[str, str]: Results of both filters.
        """
        category_total = category_series.sum()
        
        return {
            "materiality": self.classify_materiality(category_total, total_spend),
            "sparsity": self.classify_sparsity(category_series)
        }
