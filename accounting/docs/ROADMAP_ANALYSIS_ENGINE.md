Roadmap: Financial Inference Engine Implementation
Overview
This roadmap translates the Financial Trend Analysis & Inference Framework (v4) into a structured implementation backlog. It follows a logical build order to ensure that each stage has the necessary data foundation, statistical validation, and scalable database architecture before moving to higher-level diagnostics.

🧠 EPIC 1: Data Foundation & Signal Filtering [✅ COMPLETED]
Goal: Ensure all downstream analysis operates on clean, meaningful, and sufficient data.

[x] 1.1 Materiality & Sparsity Filters (Step 0)

Feature: Automatic classification of "Muted" vs "Active" categories based on % of total spend.

Feature: Detection of "Sparse" series (>30% zeros) to prevent regression noise.

[x] 1.2 Data Process Classification

Feature: Categorize accounts into Deterministic (Fixed bills), Stochastic (Habitual/Discretionary), and Episodic (One-offs).

Constraint: Models in later Epics must be selected based on this classification.

[x] 1.3 Outlier & Sanity Layer

Feature: Implementation of Conditional Winsorization (capping extreme values unless they are part of a structural break).

Feature: Handling of missing periods via log-linear fallback.

📈 EPIC 2: Core Statistical Decomposition (Axis 1-4) [✅ COMPLETED]
Goal: Compute the four analytical axes reliably and independently using scipy.stats.

[x] 2.1 Trend & Predictability (Axis 1)

Feature: Log-Linear Regression implementation (ln(y + 1)).

Feature: Significance testing (P-values for n≥6, Effect Size for n<6).

Feature: Non-linearity detection (Linear vs Rolling 2Y trend divergence).

[x] 2.2 Volatility & Structural Breaks (Axis 2 & 3)

Feature: Residual Standard Deviation calculation for noise quantification (SER).

Feature: Multi-Window Z-Score Detection for structural breaks (6m, 12m, 18m windows).

[x] 2.3 Seasonality Robustness (Axis 4)

Feature: Lag-Tolerant Cross-Correlation for monthly vector stability.

Feature: Seasonal Amplitude & Stability Index calculation.

🔍 EPIC 3: Causal Decomposition (The "Why" Layer) [🔄 IN PROGRESS]
Goal: Explain the drivers behind detected trends using transaction-level data.

[x] 3.1 Price vs. Volume vs. Mix

Feature: Volume Effect: Transaction count Δ analysis.

Feature: Price Effect: Average ticket (Avg Transaction) Δ analysis.

Feature: Mix Shift: Merchant entropy and loyalty shift detection (with Median-Split fallback).

[ ] 3.2 External Normalization (Benchmarks)

Feature: Nominal vs. Real Growth calculation.

Feature: Integration of CPI/Inflation or Income growth as a normalization baseline.

🔮 EPIC 4: Projection & Forecast Engine [✅ COMPLETED]
Goal: Generate reliable, context-aware forecasts and rank them by severity.

[x] 4.1 Hierarchy of Estimators

Feature: Model selection logic (Seasonally Adjusted vs Regression vs Mean Reversion) with MAPE backtest circuit-breakers.

Feature: Prediction Intervals: Rendering of the "Confidence Corridor" based on Standard Error (SER).

[x] 4.2 Materiality-Weighted Insights

Feature: Natural Language Generation (Expert Summary) and severity scoring formula: Base Severity * (materiality_pct * 100).

🖥️ EPIC 5: Visualization & UX Layer [✅ COMPLETED]
Goal: Make complex statistical inferences immediately understandable in React.

[x] 5.1 Core Diagnostic UI Components

Feature: Causal Badges (↑ Price Driven, ↑ Volume Driven), Process Type indicators, and InsightCard container.

[x] 5.2 Insights Dashboard & Data Hydration

Feature: Responsive, sortable grid layout (Sort by Severity vs. Materiality).

Feature: Frontend API Client hydration with robust null handling.

[x] 5.3 Django Ninja API Bridge

Feature: Pydantic schema validation (InsightResponseSchema) and REST endpoint (/api/analysis/insights/top/).

🗄️ EPIC 6: Data Orchestration & Persistence (Hybrid OLAP) [🚀 NEXT]
Goal: Build a scalable, auditable, 3-layer architecture (Kimball-style Data Mart) to compute and store insights without crashing the transactional database.

[ ] 6.1 Layer 1: The Aggregation Layer (PostgreSQL Materialized View)

Feature: Create unmanaged Django models (CategoryMonthlyStat).

Feature: Custom raw SQL migrations using DATE_TRUNC('month') for lightning-fast monthly sums, counts, and averages.

[ ] 6.2 Layer 3: The Insight Store (Append-Only Model)

Feature: Create a versioned InsightFact Django model to act as an auditable historical log of trends, structural breaks, and projections. (No delete-and-replace patterns).

[ ] 6.3 Layer 2: The Analytical Engine (Celery Worker)

Feature: Wire the InsightEngine to a background task that extracts from Layer 1, runs the heavy Python regressions/causal matrix, and UPSERTs into Layer 3 nightly.

🔁 EPIC 7: Adaptive Learning (Elite+) [⏳ BACKLOG]
Goal: Make the system self-correcting over time.

[ ] 7.1 Forecast Feedback Loop

Feature: MAPE Tracking: Compare past InsightFact projections to realized actuals over time.

Feature: Adaptive Weighting: Automatically shift models toward Mean Reversion if historical forecast error exceeds thresholds.

🧩 Logical Build Order (Current Status)
[DONE] Build the filters, classification, and statistical math (Epics 1-4).

[DONE] Build the API boundary and React visual layers (Epic 5).

[CURRENT] Transition from OLTP to OLAP by building the 3-Layer Hybrid Database Architecture (Epic 6).

[NEXT] Connect the Celery pipeline to pipe live DB transactions into the UI.