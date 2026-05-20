# Reviewer Note: Benchmark Approved, Exact Simulator Not Approved

## Decision

This module is approved as a **historical benchmark engine**. It is **not approved as an exact ETF simulator**.

The distinction matters:
- The engine is mathematically consistent inside its discrete cash-flow model.
- The inputs are proxy instruments, not a complete representation of real ETF cash flows.
- Therefore, the output is suitable for benchmarking, scenario analysis, and relative comparison, but not for claiming exact realized ETF probabilities.

## What Is Approved

- Rolling historical probability estimates over calendar-aligned monthly windows.
- Fee-adjusted hurdle modeling using a multiplicative gross hurdle.
- Discrete DCA evaluation on the same monthly grid as the sampled series.
- Fail-fast behavior when a required ticker is missing.
- Cached data reuse and incremental update behavior for operational efficiency.

## What Is Not Approved

- Exact ETF cash-flow simulation.
- Currency-complete portfolio replication without a translation layer.
- Dividend-timing exactness for all instruments in the proxy set.
- Withholding-tax exactness.
- Tracking-error exactness.
- Silent substitution of missing tickers or partial proxy portfolios.

## Required Assumptions

The engine must state these assumptions whenever probabilities are shown:

- The results are based on historical proxy data, not guaranteed future outcomes.
- Price-index or adjusted-close proxies may understate or distort true total-return behavior.
- Cross-currency proxies are only approximate unless daily FX translation is explicitly modeled.
- The DCA return distribution assumes the chosen contribution schedule and contribution timing are intentional model inputs.
- The fee adjustment is modeled multiplicatively as a gross hurdle derived from the target net annualized return and blended MER.

## Recommended Labeling

Use this wording in UI, notebooks, and reports:

> Approved as benchmark engine. Not approved as exact simulator.

> Outputs are historical proxy estimates subject to currency, dividend, tax, and tracking-error limitations.

## Implementation Boundary

The correct architecture is:

1. Fetch proxy data through `YahooDAO`.
2. Build the synthetic portfolio series in the mathematical engine.
3. Downsample to monthly observations.
4. Apply the fee-adjusted probability engine.
5. Present the results as benchmark probabilities only.

If any required proxy is unavailable, the engine should fail fast rather than silently proceed with a reduced portfolio.