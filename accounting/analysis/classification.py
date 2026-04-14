import pandas as pd
import numpy as np
from typing import Union, Optional
from enum import Enum
from .filters import SignalFilter

class ProcessType(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    STOCHASTIC = "STOCHASTIC"
    EPISODIC = "EPISODIC"

class ProcessClassifier:
    """
    Step 0 (Part 2): Data Process Classification for the Financial Inference Engine.
    Classifies "Active" categories into Deterministic, Stochastic, or Episodic.
    """

    def __init__(
        self, 
        cov_threshold: float = 0.05,        # Default 5% for Deterministic
        sparsity_threshold: float = 0.30     # Matches SignalFilter default
    ):
        self.cov_threshold = cov_threshold
        self.signal_filter = SignalFilter(sparsity_threshold=sparsity_threshold)

    def classify(
        self, 
        series: Union[list, pd.Series, np.ndarray],
        sparsity_status: Optional[str] = None
    ) -> ProcessType:
        """
        Classifies the process generating the financial time series.
        
        Args:
            series (Union[list, pd.Series, np.ndarray]): Monthly spend amounts.
            sparsity_status (Optional[str]): Pre-calculated 'Sparse' or 'Dense' status.
            
        Returns:
            ProcessType: DETERMINISTIC, STOCHASTIC, or EPISODIC.
        """
        if not isinstance(series, pd.Series):
            series = pd.Series(series)

        if len(series) == 0:
            return ProcessType.EPISODIC

        # Rule 1: Episodic (Sparse series)
        if sparsity_status is None:
            sparsity_status = self.signal_filter.classify_sparsity(series)
            
        if sparsity_status == "Sparse":
            return ProcessType.EPISODIC

        # Rule 2: Deterministic (Dense series + Very Low CoV on non-zero months)
        # We calculate CoV on non-zero months to avoid sparsity-induced variance
        non_zero_series = series[series > 0]
        if len(non_zero_series) == 0:
            return ProcessType.EPISODIC
            
        mean = non_zero_series.mean()
        std = non_zero_series.std()
        
        if mean == 0:
            return ProcessType.EPISODIC
            
        # pandas std() returns NaN for series with 1 element
        if len(non_zero_series) == 1:
            # A single non-zero month in an otherwise dense series is unlikely, 
            # but we'll treat it as Stochastic unless it's perfectly consistent.
            return ProcessType.STOCHASTIC

        cov = std / mean
        
        if cov < self.cov_threshold:
            return ProcessType.DETERMINISTIC
            
        # Rule 3: Stochastic (Dense series + High CoV)
        return ProcessType.STOCHASTIC
