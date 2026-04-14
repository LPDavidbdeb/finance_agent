import pandas as pd
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class CausalAnalysisResult:
    """
    Result of causal decomposition analysis.

    Attributes:
        volume_effect_pct: % change in transaction count (L12M vs P12M)
        price_effect_pct: % change in average ticket size (L12M vs P12M)
        mix_shift_detected: True if top merchant share changed by >±10 percentage points
        l12m_transaction_count: Number of transactions in Last 12 Months
        p12m_transaction_count: Number of transactions in Previous 12 Months
        l12m_avg_ticket: Average transaction amount in Last 12 Months
        p12m_avg_ticket: Average transaction amount in Previous 12 Months
        l12m_top_merchant_share: Top merchant % share in Last 12 Months
        p12m_top_merchant_share: Top merchant % share in Previous 12 Months
    """
    volume_effect_pct: float
    price_effect_pct: float
    mix_shift_detected: bool
    l12m_transaction_count: int
    p12m_transaction_count: int
    l12m_avg_ticket: float
    p12m_avg_ticket: float
    l12m_top_merchant_share: float
    p12m_top_merchant_share: float


class CausalAnalyzer:
    """
    EPIC 3: Causal Decomposition (Price, Volume, Mix) for the Financial Inference Engine.

    Breaks down spend changes into:
    - Volume Effect: % change in transaction count
    - Price Effect: % change in average ticket size (amount per transaction)
    - Mix Shift: Change in merchant concentration (top merchant share)
    """

    def __init__(self, mix_shift_threshold_pct: float = 10.0):
        """
        Args:
            mix_shift_threshold_pct: Threshold for flagging mix shift (default 10 percentage points).
                                     If top merchant share changes by >±10pp, flag detected=True.
        """
        self.mix_shift_threshold_pct = mix_shift_threshold_pct

    def analyze(
        self,
        transactions_df: pd.DataFrame,
        reference_date: Optional[pd.Timestamp] = None
    ) -> CausalAnalysisResult:
        """
        Perform causal decomposition on transaction-level data.

        Args:
            transactions_df: DataFrame with columns [date, amount, merchant_name].
                            - date: datetime-like (will be converted to datetime64)
                            - amount: numeric (int, float, or Decimal)
                            - merchant_name: str
            reference_date: Optional reference point. If None, uses max(date) in the data.

        Returns:
            CausalAnalysisResult containing volume, price, and mix effects.

        Raises:
            ValueError: If DataFrame is empty, missing required columns, or has <2 months of data.
        """
        # Validate input
        if transactions_df.empty:
            raise ValueError("transactions_df cannot be empty")

        required_cols = {'date', 'amount', 'merchant_name'}
        if not required_cols.issubset(set(transactions_df.columns)):
            raise ValueError(f"DataFrame must have columns: {required_cols}")

        # Make a copy to avoid modifying original
        df = transactions_df.copy()

        # Convert date to datetime
        df['date'] = pd.to_datetime(df['date'])

        # Convert amount to float (handles Decimal, int, float)
        df['amount'] = df['amount'].astype(float)

        # Determine reference date
        if reference_date is None:
            reference_date = df['date'].max()
        else:
            reference_date = pd.Timestamp(reference_date)

        # Define the two 12-month windows
        l12m_end = reference_date
        l12m_start = l12m_end - pd.DateOffset(months=12)
        p12m_end = l12m_start - pd.DateOffset(days=1)
        p12m_start = p12m_end - pd.DateOffset(months=12)

        # Split into two periods
        l12m_df = df[(df['date'] >= l12m_start) & (df['date'] <= l12m_end)]
        p12m_df = df[(df['date'] >= p12m_start) & (df['date'] <= p12m_end)]

        # Fallback: If either period is empty, use the median split
        if l12m_df.empty or p12m_df.empty:
            df_sorted = df.sort_values('date')
            mid_idx = len(df_sorted) // 2
            p12m_df = df_sorted.iloc[:mid_idx]
            l12m_df = df_sorted.iloc[mid_idx:]

            if l12m_df.empty or p12m_df.empty:
                raise ValueError(
                    "Cannot split data into two meaningful periods. "
                    "Ensure at least 2 months of transaction data."
                )

        # Calculate metrics for each period
        (l12m_count, l12m_avg_ticket, l12m_top_share) = self._calculate_period_metrics(l12m_df)
        (p12m_count, p12m_avg_ticket, p12m_top_share) = self._calculate_period_metrics(p12m_df)

        # Calculate effects
        volume_effect_pct = self._calculate_percentage_change(p12m_count, l12m_count)
        price_effect_pct = self._calculate_percentage_change(p12m_avg_ticket, l12m_avg_ticket)

        # Detect mix shift (convert to Python bool)
        mix_shift_detected = bool(abs(l12m_top_share - p12m_top_share) > self.mix_shift_threshold_pct)

        return CausalAnalysisResult(
            volume_effect_pct=volume_effect_pct,
            price_effect_pct=price_effect_pct,
            mix_shift_detected=mix_shift_detected,
            l12m_transaction_count=l12m_count,
            p12m_transaction_count=p12m_count,
            l12m_avg_ticket=l12m_avg_ticket,
            p12m_avg_ticket=p12m_avg_ticket,
            l12m_top_merchant_share=l12m_top_share,
            p12m_top_merchant_share=p12m_top_share,
        )

    @staticmethod
    def _calculate_period_metrics(period_df: pd.DataFrame) -> Tuple[int, float, float]:
        """
        Calculate metrics for a single period.

        Args:
            period_df: DataFrame with columns [amount, merchant_name] for a single period.

        Returns:
            (transaction_count, avg_ticket_size, top_merchant_share_pct)
        """
        if period_df.empty:
            return 0, 0.0, 0.0

        transaction_count = len(period_df)
        total_amount = period_df['amount'].sum()
        avg_ticket = total_amount / transaction_count if transaction_count > 0 else 0.0

        # Calculate top merchant share
        merchant_totals = period_df.groupby('merchant_name')['amount'].sum()
        top_merchant_amount = merchant_totals.max() if not merchant_totals.empty else 0.0
        top_merchant_share = (top_merchant_amount / total_amount * 100) if total_amount > 0 else 0.0

        return transaction_count, avg_ticket, top_merchant_share

    @staticmethod
    def _calculate_percentage_change(old_value: float, new_value: float) -> float:
        """
        Calculate percentage change from old_value to new_value.

        Formula: ((new - old) / old) * 100

        Args:
            old_value: Baseline value (P12M)
            new_value: New value (L12M)

        Returns:
            Percentage change. Returns 0.0 if old_value is 0.
        """
        if old_value == 0:
            if new_value == 0:
                return 0.0
            # If old was 0 and new is non-zero, return inf-like behavior
            # For practical purposes, we'll return a large number
            return float('inf') if new_value > 0 else float('-inf')

        return ((new_value - old_value) / old_value) * 100.0

