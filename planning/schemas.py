from ninja import Schema
from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional
from enum import Enum


class ScenarioType(str, Enum):
    LOAN_AMORTIZATION = 'LOAN_AMORTIZATION'
    SINKING_FUND = 'SINKING_FUND'


class PaymentFrequencyIn(str, Enum):
    MONTHLY = 'MONTHLY'
    BIWEEKLY = 'BIWEEKLY'
    WEEKLY = 'WEEKLY'
    ANNUALLY = 'ANNUALLY'


class ScenarioSpec(Schema):
    name: str
    type: ScenarioType = ScenarioType.LOAN_AMORTIZATION
    principal: Decimal                     # PV for loan; FV target for sinking fund
    annual_rate: Decimal                   # percentage, e.g. 4.5 means 4.5%
    amortization_years: int
    payment_frequency: PaymentFrequencyIn = PaymentFrequencyIn.MONTHLY
    start_date: date                       # loan origination date; payments flow from here
    current_balance: Optional[Decimal] = Decimal('0')   # sinking fund only


class PeriodRow(Schema):
    period_number: int
    payment_date: date
    payment_amount: Decimal
    interest_portion: Decimal
    principal_portion: Decimal
    balance_after: Decimal


class ScenarioResult(Schema):
    name: str
    type: ScenarioType
    payment_amount: Decimal
    total_interest_paid: Decimal
    total_cost: Decimal
    fcf_impact_monthly: Decimal
    delta_vs_baseline: Optional[Decimal] = None
    schedule: List[PeriodRow]


# ── Persisted schedule schemas ────────────────────────────────────────────────

class CommitIn(Schema):
    """Commit a scenario to a persisted AnnuitySchedule."""
    spec: ScenarioSpec
    linked_journal_entry_id: Optional[int] = None   # originating lump-sum JE, if known


class AnnuityPeriodOut(Schema):
    id: int
    period_number: int
    payment_date: date
    payment_amount: Decimal
    interest_portion: Decimal
    principal_portion: Decimal
    balance_after: Decimal
    is_paid: bool
    journal_entry_id: Optional[int] = None


class LinkedRuleOut(Schema):
    id: int
    search_text: str
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    merchant_name: str
    institution_id: Optional[int] = None


class AnnuityScheduleOut(Schema):
    id: int
    name: str
    schedule_type: str
    principal_amount: Decimal
    annual_rate: Decimal
    n_periods: int
    payment_frequency: str
    start_date: date
    computed_payment: Decimal
    linked_journal_entry_id: Optional[int] = None
    linked_rule: Optional[LinkedRuleOut] = None
    financing_contract: Optional[str] = None
    created_at: datetime
    periods: List[AnnuityPeriodOut] = []


class AnnuityScheduleListOut(Schema):
    id: int
    name: str
    schedule_type: str
    principal_amount: Decimal
    annual_rate: Decimal
    n_periods: int
    payment_frequency: str
    start_date: date
    computed_payment: Decimal
    created_at: datetime


# ── Portfolio Scenario Schemas ────────────────────────────────────────────────

class PortfolioStats(Schema):
    mean: float
    median: float
    std: float
    min: float
    max: float
    skewness: float
    kurtosis: float
    percentile_5: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_95: float


class DistributionData(Schema):
    """Distribution of returns (histogram + KDE + raw samples)."""
    count: int                          # Number of scenarios
    stats: PortfolioStats
    histogram_edges: List[float]        # Bin edges for histogram
    histogram_counts: List[int]         # Counts per bin
    kde_x: List[float]                 # KDE x-axis points
    kde_y: List[float]                 # KDE density values
    returns: Optional[List[float]] = None  # Raw returns (capped to 10k)


class ScenarioMetrics(Schema):
    """Return metrics for one scenario (horizon + pattern)."""
    horizon_years: int
    pattern: str  # "lump_sum" or "dca"
    lump_sum: DistributionData
    dca: DistributionData


class AllocationWeight(Schema):
    """Ticker weight in an allocation."""
    ticker: str
    weight: float


class AllocationResult(Schema):
    """One suggested portfolio allocation."""
    label: str
    weights: List[AllocationWeight]
    expected_return: float
    volatility: float
    sharpe_ratio: float


class PortfolioOptimizationResult(Schema):
    """Result of portfolio optimization."""
    tickers: List[str]
    period_start: str
    period_end: str
    optimal: AllocationResult
    alternatives: List[AllocationResult]


class PortfolioScenariosRequest(Schema):
    """Request for portfolio scenario analysis."""
    tickers: List[str]                                      # ETF tickers (e.g., ['XIU.TO', 'XWD.TO'])
    horizons_years: List[int] = [2, 5, 10, 15, 25]         # Investment horizons
    monthly_dca_amount: Optional[float] = 1000.0            # DCA contribution amount
    rebalance_freq_months: Optional[int] = 1               # Rebalancing frequency
    optimize: bool = True                                   # Run optimization


class PortfolioScenariosResponse(Schema):
    """Response with optimization + scenario metrics."""
    optimization: PortfolioOptimizationResult
    scenarios: List[ScenarioMetrics]
    heatmap_data: Optional[List[List[float]]] = None       # 2D array for frontend
