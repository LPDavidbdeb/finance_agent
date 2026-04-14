# Roadmap: Financial Inference Engine Implementation

## Overview
This roadmap translates the **Financial Trend Analysis & Inference Framework (v4)** into a structured implementation backlog. It follows a logical build order to ensure that each stage has the necessary data foundation and statistical validation before moving to higher-level diagnostics.

---

## 🧠 EPIC 1: Data Foundation & Signal Filtering
**Goal**: Ensure all downstream analysis operates on clean, meaningful, and sufficient data.

### 1.1 Materiality & Sparsity Filters (Step 0)
- **Feature**: Automatic classification of "Muted" vs "Active" categories based on % of total spend.
- **Feature**: Detection of "Sparse" series (>30% zeros) to prevent regression noise.

### 1.2 Data Process Classification
- **Feature**: Categorize accounts into **Deterministic** (Fixed bills), **Stochastic** (Habitual/Discretionary), and **Episodic** (One-offs).
- **Constraint**: Models in later Epics must be selected based on this classification.

### 1.3 Outlier & Sanity Layer
- **Feature**: Implementation of **Conditional Winsorization** (capping extreme values unless they are part of a structural break).
- **Feature**: Handling of missing periods via log-linear fallback.

---

## 📈 EPIC 2: Core Statistical Decomposition (Axis 1-4)
**Goal**: Compute the four analytical axes reliably and independently.

### 2.1 Trend & Predictability (Axis 1)
- **Feature**: **Log-Linear Regression** implementation (`ln(y + 1)`).
- **Feature**: Significance testing (P-values for $n \ge 6$, Effect Size for $n < 6$).
- **Feature**: Non-linearity detection (Linear vs Rolling 2Y trend divergence).

### 2.2 Volatility & Structural Breaks (Axis 2 & 3)
- **Feature**: **Residual Standard Deviation** calculation for noise quantification.
- **Feature**: **Multi-Window Z-Score Detection** for structural breaks (6m, 12m, 18m windows).

### 2.3 Seasonality Robustness (Axis 4)
- **Feature**: **Lag-Tolerant Cross-Correlation** for monthly vector stability.
- **Feature**: Seasonal Amplitude & Stability Index calculation.

---

## 🔍 EPIC 3: Causal Decomposition (The "Why" Layer)
**Goal**: Explain the drivers behind detected trends.

### 3.1 Price vs. Volume vs. Mix
- **Feature**: **Volume Effect**: Transaction count Δ analysis.
- **Feature**: **Price Effect**: Average ticket (Avg Transaction) Δ analysis.
- **Feature**: **Mix Shift**: Merchant entropy and loyalty shift detection.

### 3.2 External Normalization (Benchmarks)
- **Feature**: **Nominal vs. Real Growth** calculation.
- **Feature**: Integration of CPI/Inflation or Income growth as a normalization baseline.

---

## 🔮 EPIC 4: Projection & Forecast Engine
**Goal**: Generate reliable, context-aware forecasts.

### 4.1 Hierarchy of Estimators
- **Feature**: Model selection logic (Seasonally Adjusted vs Regression vs Mean Reversion).
- **Feature**: **Prediction Intervals**: Rendering of the "Confidence Corridor" based on Standard Error (SER).

### 4.2 Materiality-Weighted Insights
- **Feature**: Ranking and filtering of insights so that materiality (spend weight) dictates UI prominence.

---

## 🖥️ EPIC 5: Visualization & UX Layer
**Goal**: Make complex statistical inferences immediately understandable.

### 5.1 The "Delta Perspective"
- **Feature**: YoY % Change overlay to show acceleration/deceleration.
- **Feature**: Stacked Bar standard (Realized + Projected).

### 5.2 Diagnostic Annotations
- **Feature**: Causal Badges (`↑ Price Driven`, `↑ Volume Driven`).
- **Feature**: Structural Break markers and Confidence Corridors.

---

## 🔁 EPIC 6: Adaptive Learning (Elite+)
**Goal**: Make the system self-correcting over time.

### 6.1 Forecast Feedback Loop
- **Feature**: **MAPE Tracking**: Compare past projections to realized actuals.
- **Feature**: **Adaptive Weighting**: Automatically shift models toward Mean Reversion if forecast error exceeds thresholds.

---

## 🧩 Logical Build Order
1. **EPIC 1**: Build the filters and classification logic first.
2. **EPIC 2**: Implement the core math for Trend, Noise, and Breaks.
3. **EPIC 3**: Add the Causal layer (Price/Volume) to explain the math from EPIC 2.
4. **EPIC 4 & 5**: Build the projection engine and the UI concurrently.
5. **EPIC 6**: Add the adaptive feedback loop once historical forecast data is available.
