from ninja import Router, Schema, File, Form
from ninja.files import UploadedFile
from ninja.errors import HttpError
from django.db import transaction
from django.shortcuts import get_object_or_404
from typing import List, Optional
from decimal import Decimal
from datetime import date

from .schemas import (
    ScenarioSpec, ScenarioResult, PeriodRow, ScenarioType, PaymentFrequencyIn,
    CommitIn, AnnuityScheduleOut, AnnuityScheduleListOut, AnnuityPeriodOut, LinkedRuleOut,
    PortfolioScenariosRequest, PortfolioScenariosResponse, AllocationResult,
    AllocationWeight, PortfolioOptimizationResult, ScenarioMetrics, DistributionData,
)
from .models import AnnuitySchedule, AnnuityPeriod
from .services import AnnuityService
from .optimization import PortfolioOptimizer
from .returns import PortfolioReturnsCalculator
from .oracle import OracleEvaluationRequest, OracleEvaluationResponse, PortfolioOracle
import logging

logger = logging.getLogger(__name__)

router = Router(tags=["Planning"])


class CpiRateOut(Schema):
    vector_id: int
    years: int
    cagr: Optional[float]        # decimal fraction, e.g. 0.021 = 2.1%
    cagr_pct: Optional[float]    # percentage, e.g. 2.1


@router.get("/cpi-rate/{vector_id}", response=CpiRateOut, auth=None)
def get_cpi_rate(request, vector_id: int, years: int = 10):
    """
    Return the trailing CAGR for a StatCan CPI vector (table 18100004).
    Used by the asset creation form to auto-fill the inflation assumption
    when the user picks an asset category linked to an expense account.

    auth=None — read-only market data, no family scoping needed.
    """
    from market_data.statcan import get_dao
    cpi = get_dao("cpi")
    rate = cpi.cagr(vector_id, years=years)
    return CpiRateOut(
        vector_id=vector_id,
        years=years,
        cagr=rate,
        cagr_pct=round(rate * 100, 2) if rate is not None else None,
    )


# ── Simulation (stateless) ────────────────────────────────────────────────────

@router.post("/simulate", response=List[ScenarioResult])
def simulate(request, scenarios: List[ScenarioSpec]):
    """
    Stateless: given N scenario specs compute and return N results.
    No DB writes — call repeatedly as the user tweaks inputs.
    """
    results: List[ScenarioResult] = []
    baseline_pmt: Decimal | None = None

    for spec in scenarios:
        pmt, schedule_dicts, _ = AnnuityService.compute_scenario(spec)
        schedule = [PeriodRow(**row) for row in schedule_dicts]
        total_interest = sum(row.interest_portion for row in schedule)
        total_cost = sum(row.payment_amount for row in schedule)

        if baseline_pmt is None:
            baseline_pmt = pmt

        results.append(ScenarioResult(
            name=spec.name,
            type=spec.type,
            payment_amount=pmt,
            total_interest_paid=total_interest,
            total_cost=total_cost,
            fcf_impact_monthly=-pmt,
            delta_vs_baseline=(pmt - baseline_pmt) if pmt != baseline_pmt else None,
            schedule=schedule,
        ))

    return results


# ── Commit (persist) ──────────────────────────────────────────────────────────

@router.post("/schedules", response=AnnuityScheduleOut)
def commit_schedule(request, payload: CommitIn):
    """
    Commit a chosen scenario: persist AnnuitySchedule + all AnnuityPeriod rows.
    The start_date on the spec is the loan origination date; payment dates flow from it.
    """
    spec = payload.spec
    family = request.auth.family

    # Optionally validate the linked JE belongs to this family
    linked_je = None
    if payload.linked_journal_entry_id:
        from accounting.models import JournalEntry
        try:
            linked_je = JournalEntry.objects.get(
                id=payload.linked_journal_entry_id, family=family
            )
        except JournalEntry.DoesNotExist:
            raise HttpError(404, "Journal entry not found in your family.")

    schedule = AnnuityService.commit_schedule(family, spec, linked_je)

    return _schedule_to_out(schedule, include_periods=True)



@router.get("/schedules", response=List[AnnuityScheduleListOut])
def list_schedules(request):
    """List all committed schedules for this family."""
    return list(
        AnnuitySchedule.objects.filter(family=request.auth.family)
    )


@router.get("/schedules/{schedule_id}", response=AnnuityScheduleOut)
def get_schedule(request, schedule_id: int):
    """Get a specific schedule with its full period table."""
    schedule = get_object_or_404(AnnuitySchedule, id=schedule_id, family=request.auth.family)
    return _schedule_to_out(schedule, include_periods=True)


@router.delete("/schedules/{schedule_id}")
def delete_schedule(request, schedule_id: int):
    """Delete a committed schedule and all its periods."""
    schedule = get_object_or_404(AnnuitySchedule, id=schedule_id, family=request.auth.family)
    schedule.delete()
    return {"message": "Schedule deleted."}


# ── Loan Initiation ──────────────────────────────────────────────────────────

class LoanSetupIn(Schema):
    """One-shot: creates the purchase JE and commits the amortization schedule."""
    # Asset / purchase
    purchase_description: str          # e.g. "Honda Civic 2024"
    purchase_date: date
    purchase_price: Decimal
    down_payment: Decimal = Decimal('0')
    loan_amount: Decimal               # actual financed amount
    asset_account_id: int              # ASSET account to DR
    cash_account_id: int               # ASSET account to CR (down payment)
    loan_account_id: Optional[int] = None      # LIABILITY account to CR. Optional if creating new.
    new_loan_account_name: Optional[str] = None # Name of a new liability account to create.

    # Schedule terms
    schedule_name: str                 # e.g. "Honda Civic — Auto Loan"
    annual_rate: Decimal               # e.g. 5.9 (percentage)
    amortization_years: int
    payment_frequency: PaymentFrequencyIn
    schedule_start_date: date          # origination / first-period anchor date


class PayPeriodIn(Schema):
    cash_account_id: int
    loan_account_id: int
    interest_account_id: int
    payment_date: Optional[date] = None   # override; uses period.payment_date if None


class BulkPayIn(Schema):
    period_ids: List[int]
    cash_account_id: int
    loan_account_id: int
    interest_account_id: int


def _create_payment_je(family, period: AnnuityPeriod, cash_account_id: int,
                        loan_account_id: int, interest_account_id: int,
                        payment_date: Optional[date]) -> None:
    """Create the 3-line compound JE for a single loan payment and mark the period paid."""
    from accounting.models import JournalEntry, TransactionLine, Account

    if period.is_paid:
        raise HttpError(409, f"Period {period.period_number} is already paid.")

    def _get_account(account_id: int) -> "Account":
        try:
            return Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            raise HttpError(404, f"Account {account_id} not found.")

    cash_acct = _get_account(cash_account_id)
    loan_acct = _get_account(loan_account_id)
    interest_acct = _get_account(interest_account_id)

    effective_date = payment_date or period.payment_date

    je = JournalEntry.objects.create(
        family=family,
        date=effective_date,
        description=f"Loan Payment: {period.schedule.name} — Period {period.period_number}",
        is_reconciled=True,
    )

    # CR Cash — full payment leaves the bank
    TransactionLine.objects.create(journal_entry=je, account=cash_acct, amount=-period.payment_amount)
    # DR Loan Payable — principal reduces the liability
    TransactionLine.objects.create(journal_entry=je, account=loan_acct, amount=period.principal_portion)
    # DR Interest Expense — interest hits the P&L
    TransactionLine.objects.create(journal_entry=je, account=interest_acct, amount=period.interest_portion)

    period.is_paid = True
    period.journal_entry = je
    period.save(update_fields=['is_paid', 'journal_entry'])


@router.post("/loan-setup", response=AnnuityScheduleOut)
@transaction.atomic
def loan_setup(
    request, 
    payload: LoanSetupIn = Form(...), 
    sales_contract: Optional[UploadedFile] = File(None),
    financing_contract: Optional[UploadedFile] = File(None)
):
    """
    Atomic: create the asset-purchase JE, create TangibleAsset, and commit the amortization schedule.
    Uses assets.services.OriginationService for orchestration.
    """
    from accounting.models import Account
    from assets.services import OriginationService

    family = request.auth.family

    def _get_family_account(account_id: int) -> Account:
        """Accept family-owned or global (family=None) accounts."""
        try:
            acct = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            raise HttpError(404, f"Account {account_id} not found.")
        if acct.family is not None and acct.family_id != family.id:
            raise HttpError(403, f"Account {account_id} does not belong to your family.")
        return acct

    asset_acct = _get_family_account(payload.asset_account_id)
    cash_acct = _get_family_account(payload.cash_account_id)
    
    # Resolve or create the loan liability account
    if payload.loan_account_id:
        loan_acct = _get_family_account(payload.loan_account_id)
        if loan_acct.account_type != Account.AccountType.LIABILITY:
            raise HttpError(400, "loan_account_id must be a LIABILITY account.")
    elif payload.new_loan_account_name:
        # Create a new liability account under the "Liabilities" root
        liabilities_root = Account.objects.filter(family=family, name='Liabilities', parent=None).first()
        if not liabilities_root:
             # Fallback: find any LIABILITY account and use its root
             any_lib = Account.objects.filter(family=family, account_type=Account.AccountType.LIABILITY).first()
             if any_lib:
                 liabilities_root = any_lib.get_root()
             else:
                 raise HttpError(400, "No Liabilities root found. Please create one in the Ledger first.")
        
        loan_acct = Account.objects.create(
            name=payload.new_loan_account_name.strip().upper(),
            parent=liabilities_root,
            account_type=Account.AccountType.LIABILITY,
            family=family
        )
    else:
        raise HttpError(400, "Must provide either loan_account_id or new_loan_account_name.")

    # Delegate core orchestration to OriginationService
    # This creates: JournalEntry, TangibleAsset, and AnnuitySchedule
    asset = OriginationService.acquire_financed_asset(
        name=payload.purchase_description,
        family=family,
        total_cost=payload.purchase_price,
        down_payment=payload.down_payment,
        financed_amount=payload.loan_amount,
        origination_date=payload.purchase_date,
        loan_term_years=payload.amortization_years,
        annual_rate=payload.annual_rate,
        cash_account=cash_acct,
        liability_account=loan_acct,
        payment_frequency=payload.payment_frequency,
        existing_asset_account=asset_acct,
        sales_contract_file=sales_contract,
        financing_contract_file=financing_contract
    )

    # Note: OriginationService uses a default schedule name. 
    # If the payload specified a different schedule name, we update it.
    schedule = asset.annuity_schedule
    if schedule and payload.schedule_name and schedule.name != payload.schedule_name:
        schedule.name = payload.schedule_name
        schedule.save(update_fields=['name'])
        # Also update the auto-generated merchant if it was based on the old name
        rule = schedule.mapping_rules.first()
        if rule and rule.merchant:
            rule.merchant.name = f"[LOAN] {payload.schedule_name}"
            rule.merchant.save(update_fields=['name'])

    return _schedule_to_out(schedule, include_periods=True)


@router.post("/schedules/{schedule_id}/periods/{period_id}/pay", response=AnnuityScheduleOut)
@transaction.atomic
def pay_period(request, schedule_id: int, period_id: int, payload: PayPeriodIn):
    """Record a single manual payment: creates the 3-line compound JE and marks the period paid."""
    schedule = get_object_or_404(AnnuitySchedule, id=schedule_id, family=request.auth.family)
    period = get_object_or_404(AnnuityPeriod, id=period_id, schedule=schedule)

    _create_payment_je(
        family=request.auth.family,
        period=period,
        cash_account_id=payload.cash_account_id,
        loan_account_id=payload.loan_account_id,
        interest_account_id=payload.interest_account_id,
        payment_date=payload.payment_date,
    )
    return _schedule_to_out(schedule, include_periods=True)


@router.post("/schedules/{schedule_id}/bulk-pay", response=AnnuityScheduleOut)
@transaction.atomic
def bulk_pay(request, schedule_id: int, payload: BulkPayIn):
    """Record payments for multiple periods at once (catch-up for past payments)."""
    schedule = get_object_or_404(AnnuitySchedule, id=schedule_id, family=request.auth.family)

    periods = AnnuityPeriod.objects.filter(
        id__in=payload.period_ids, schedule=schedule, is_paid=False
    ).order_by('period_number')

    for period in periods:
        _create_payment_je(
            family=request.auth.family,
            period=period,
            cash_account_id=payload.cash_account_id,
            loan_account_id=payload.loan_account_id,
            interest_account_id=payload.interest_account_id,
            payment_date=None,
        )

    return _schedule_to_out(schedule, include_periods=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _schedule_to_out(schedule: AnnuitySchedule, include_periods: bool = False) -> AnnuityScheduleOut:
    periods = []
    if include_periods:
        periods = [
            AnnuityPeriodOut(
                id=p.id,
                period_number=p.period_number,
                payment_date=p.payment_date,
                payment_amount=p.payment_amount,
                interest_portion=p.interest_portion,
                principal_portion=p.principal_portion,
                balance_after=p.balance_after,
                is_paid=p.is_paid,
                journal_entry_id=p.journal_entry_id,
            )
            for p in schedule.periods.all()
        ]

    linked_rule = None
    rule = schedule.mapping_rules.select_related('merchant').first()
    if rule:
        linked_rule = LinkedRuleOut(
            id=rule.id,
            search_text=rule.search_text,
            min_amount=rule.min_amount,
            max_amount=rule.max_amount,
            merchant_name=rule.merchant.name,
            institution_id=rule.institution_id,
        )

    return AnnuityScheduleOut(
        id=schedule.id,
        name=schedule.name,
        schedule_type=schedule.schedule_type,
        principal_amount=schedule.principal_amount,
        annual_rate=schedule.annual_rate,
        n_periods=schedule.n_periods,
        payment_frequency=schedule.payment_frequency,
        start_date=schedule.start_date,
        computed_payment=schedule.computed_payment,
        linked_journal_entry_id=schedule.linked_journal_entry_id,
        linked_rule=linked_rule,
        financing_contract=schedule.financing_contract.url if schedule.financing_contract else None,
        created_at=schedule.created_at,
        periods=periods,
    )


# ── Statement matching rule ───────────────────────────────────────────────────

class UpdateRuleIn(Schema):
    """Update the auto-created statement-matching rule for a schedule."""
    search_text: str                        # The bank's merchant string (e.g. "toyota financial")
    institution_id: Optional[int] = None    # Scope to one bank; None = match all institutions


@router.patch("/schedules/{schedule_id}/rule", response=AnnuityScheduleOut)
@transaction.atomic
def update_schedule_rule(request, schedule_id: int, payload: UpdateRuleIn):
    """
    Update the search_text (and optional institution scope) of the auto-created
    TransactionMappingRule linked to this schedule.

    Call this once after registering a new loan so that incoming bank statement
    lines are intercepted and split into principal + interest components
    automatically during the approve flow.
    """
    from categorization.models import TransactionMappingRule
    schedule = get_object_or_404(AnnuitySchedule, id=schedule_id, family=request.auth.family)

    rule = schedule.mapping_rules.first()
    if not rule:
        raise HttpError(404, "No mapping rule found for this schedule. Was the schedule committed via the normal flow?")

    rule.search_text = payload.search_text   # model.save() will normalize it
    rule.institution_id = payload.institution_id
    rule.save()

    return _schedule_to_out(schedule, include_periods=True)


# ── Portfolio Scenarios (stateless) ───────────────────────────────────────────


@router.post("/oracle/evaluate", response=OracleEvaluationResponse, auth=None)
def evaluate_oracle(request, payload: OracleEvaluationRequest):
    """
    Evaluate a lifecycle goal against the historical probability Oracle.

    This is the lifecycle-engine boundary: the caller provides a desired horizon,
    target net annual return, blended MER, and asset allocation. The Oracle owns
    the market-data fetch, proxy translation, and probability computation.
    """

    try:
        if not payload.asset_allocation:
            raise HttpError(400, "Must provide an asset_allocation.")
        if payload.horizon_years <= 0:
            raise HttpError(400, "horizon_years must be positive.")
        if payload.blended_mer < 0:
            raise HttpError(400, "blended_mer cannot be negative.")

        return PortfolioOracle.evaluate(payload)
    except HttpError:
        raise
    except Exception as e:
        logger.error(f"Error evaluating oracle: {e}", exc_info=True)
        raise HttpError(500, f"Failed to evaluate oracle: {str(e)}")

@router.post("/portfolio-scenarios", response=PortfolioScenariosResponse, auth=None)
def compute_portfolio_scenarios(request, payload: PortfolioScenariosRequest):
    """
    Compute portfolio return distributions for multiple horizons and investment patterns.

    Stateless endpoint: given ETF tickers and horizons, returns:
    - Optimized portfolio allocation (max Sharpe ratio) + alternatives
    - Return distributions for lump-sum and DCA strategies
    - Heatmap data for visualization

    auth=None — read-only market data, no family scoping needed.
    """
    try:
        # Validate input
        if not payload.tickers or len(payload.tickers) == 0:
            raise HttpError(400, "Must provide at least one ticker.")
        if not payload.horizons_years or len(payload.horizons_years) == 0:
            raise HttpError(400, "Must provide at least one horizon.")

        # Phase 1: Run portfolio optimization
        optimizer = PortfolioOptimizer(lookback_years=5)
        opt_result = optimizer.optimize(payload.tickers, min_weight=0.0, max_weight=1.0)

        # Fetch prices for return calculations (will use for all horizons)
        prices = optimizer.fetch_prices(payload.tickers)

        # Use optimal weights as primary scenario
        optimal_weights = opt_result['optimal']['weights']

        # Phase 2: Compute return scenarios for each horizon
        scenario_metrics = []
        heatmap_rows = []

        for horizon_years in sorted(payload.horizons_years):
            horizon_days = PortfolioReturnsCalculator.trading_days_to_index_length(horizon_years)

            # Compute portfolio price series
            portfolio_series = PortfolioReturnsCalculator.compute_portfolio_price_series(
                prices, optimal_weights
            )

            # Lump-sum returns
            lump_sum_result = PortfolioReturnsCalculator.compute_lump_sum_returns(
                portfolio_series, horizon_days
            )

            # KDE and histogram for lump-sum
            lump_sum_edges, lump_sum_counts = PortfolioReturnsCalculator.compute_histogram_bins(
                lump_sum_result['returns'], n_bins=50
            )
            lump_sum_kde_x, lump_sum_kde_y = PortfolioReturnsCalculator.compute_kde_points(
                lump_sum_result['returns'], n_points=200
            )

            # DCA returns
            dca_result = PortfolioReturnsCalculator.compute_dca_returns(
                prices,
                optimal_weights,
                horizon_years,
                monthly_contribution=payload.monthly_dca_amount or 1000.0,
                rebalance_freq_months=payload.rebalance_freq_months or 1,
            )

            # KDE and histogram for DCA
            dca_edges, dca_counts = PortfolioReturnsCalculator.compute_histogram_bins(
                dca_result['returns'], n_bins=50
            )
            dca_kde_x, dca_kde_y = PortfolioReturnsCalculator.compute_kde_points(
                dca_result['returns'], n_points=200
            )

            # Build scenario metrics
            scenario = ScenarioMetrics(
                horizon_years=horizon_years,
                pattern='combined',
                lump_sum=DistributionData(
                    count=lump_sum_result['count'],
                    stats=lump_sum_result['stats'],
                    histogram_edges=lump_sum_edges,
                    histogram_counts=lump_sum_counts,
                    kde_x=lump_sum_kde_x,
                    kde_y=lump_sum_kde_y,
                    returns=lump_sum_result['returns'][:10000] if len(lump_sum_result['returns']) > 0 else [],
                ),
                dca=DistributionData(
                    count=dca_result['count'],
                    stats=dca_result['stats'],
                    histogram_edges=dca_edges,
                    histogram_counts=dca_counts,
                    kde_x=dca_kde_x,
                    kde_y=dca_kde_y,
                    returns=dca_result['returns'][:10000] if len(dca_result['returns']) > 0 else [],
                ),
            )
            scenario_metrics.append(scenario)

            # Add row to heatmap (mean return for lump-sum and DCA)
            lump_sum_mean = lump_sum_result['stats'].get('mean', 0)
            dca_mean = dca_result['stats'].get('mean', 0)
            heatmap_rows.append([lump_sum_mean, dca_mean])

        # Format optimization result
        def _format_allocation(alloc_dict) -> AllocationResult:
            weights_list = [
                AllocationWeight(ticker=t, weight=w)
                for t, w in alloc_dict['weights'].items()
            ]
            return AllocationResult(
                label=alloc_dict['label'],
                weights=weights_list,
                expected_return=alloc_dict['expected_return'],
                volatility=alloc_dict['volatility'],
                sharpe_ratio=alloc_dict['sharpe_ratio'],
            )

        optimal_allocation = _format_allocation(opt_result['optimal'])
        alternative_allocations = [
            _format_allocation(alt) for alt in opt_result['alternatives']
        ]

        optimization_result = PortfolioOptimizationResult(
            tickers=opt_result['tickers'],
            period_start=opt_result['period_start'],
            period_end=opt_result['period_end'],
            optimal=optimal_allocation,
            alternatives=alternative_allocations,
        )

        return PortfolioScenariosResponse(
            optimization=optimization_result,
            scenarios=scenario_metrics,
            heatmap_data=heatmap_rows,
        )

    except HttpError:
        raise
    except Exception as e:
        logger.error(f"Error computing portfolio scenarios: {e}", exc_info=True)
        raise HttpError(500, f"Failed to compute scenarios: {str(e)}")
