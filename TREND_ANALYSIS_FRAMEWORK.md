# Financial Trend Analysis & Inference Framework (v4 - Engine)

## Purpose
This framework specifies a high-performance **Inference Engine** for household finance. It decomposes spending into structural, behavioral, and external components, using adaptive modeling to ensure that insights are statistically grounded, materially relevant, and contextually aware of inflation and income shifts.

---

## 1. Step 0: Data Process Classification
Before analysis, the system MUST classify the "Data Generating Process" for the category:
- **Deterministic**: Fixed, recurring amounts (e.g., Rent, Insurance, Netflix). 
    - *Model*: Step-Change detection + Mean Reversion.
- **Stochastic**: Variable, frequent spending (e.g., Groceries, Restaurants). 
    - *Model*: Log-Linear Regression + Seasonal Decomposition.
- **Episodic**: Rare, high-variance events (e.g., Home Repair, Car Purchase). 
    - *Model*: Percentile-based "Reserve" estimation; skip trend analysis.

---

## 2. Axis 1: Trend & Non-Linearity (Robust)
- **Primary Metric**: **Log-Linear Regression Slope (b)**.
- **Significance Guardrails**:
    - If `n >= 6`: Use **P-value (< 0.05)** for trend confirmation.
    - If `n < 6`: Use **Effect Size (Slope > ±2%)** as the primary indicator (P-values are unstable).
- **Non-Linearity Detection**: Compare the Linear Slope against a **Rolling 2-Year Trend**.
    - If `|Linear - Rolling| > 15%`, flag as **"Non-Linear / Plateau Detected."**

---

## 3. Axis 2: Uncertainty & Error (Model-Based)
- **Projection Uncertainty**: Use **Standard Error of the Regression (SER)** or **MAPE (Mean Absolute Percentage Error)** from backtesting.
- **Visual Standard**: Render a **"Confidence Corridor"** representing the 95% Prediction Interval. Avoid using CoV for uncertainty.

---

## 4. Axis 3: Structural Breaks (Multi-Window)
- **Detection**: **Multi-Window Z-Score Confirmation**.
    - Test for breaks at 6m, 12m, and 18m intervals.
- **Confidence**: High confidence only if the break is detected across multiple windows and persists for ≥ 3 months.
- **Capping**: Conditional Winsorization. Do NOT cap data that is part of a confirmed structural break.

---

## 5. Axis 4: Seasonality (Lag-Tolerant)
- **Metric**: **Cross-Correlation with Lag Tolerance**.
    - Allow for a ±1 month shift (e.g., Easter drift, billing delays) when computing YoY stability.
- **Requirement**: Only apply seasonal adjustments if **Stability Correlation > 0.7**.

---

## 6. The Diagnostic Layer (Causal & External)
- **Internal Decomposition**:
    - **Volume Effect**: Transaction Count Δ.
    - **Price Effect**: Average Ticket Δ.
- **External Normalization (The "Real" Insight)**:
    - Compare Category Slope against **External Benchmarks** (CPI or Income Growth).
    - *Classification*:
        - `Slope > Benchmark`: **Real Growth / Lifestyle Creep**.
        - `Slope ≈ Benchmark`: **Inflation-Tracked**.
        - `Slope < Benchmark`: **Efficiency Gain**.

---

## 7. Adaptive Projection Logic (Feedback Loop)
Projections use an **Adaptive Hierarchy**:

1.  **Backtest**: Calculate the MAPE for the last 6 months using the current model.
2.  **Adjust**:
    - If `MAPE < 10%`: Maintain current model weights.
    - If `MAPE > 20%`: Shift toward **Mean Reversion** (The model is failing to capture the noise).
3.  **Compose**: Combine **Seasonally Adjusted Base** + **Trend Component** (if R² > 0.6).

---

## 8. Implementation Guidance for AI Agents

1.  **Categorize the Process**: Is this a bill, a habit, or an event?
2.  **Check for Linearity**: Does the single slope represent the whole story, or has it plateaued?
3.  **Normalize**: Is the 10% increase just inflation, or is the user buying more?
4.  **Evaluate Accuracy**: Check the "Model Error" before presenting a confident projection.
5.  **Report Structure**:
    - *Expert*: "Category 'Groceries' is a **Deterministic Stochastic Process** with **Real Growth** (Slope: +12%, CPI: +4%). The drift is **Price-Driven** (+15% avg ticket). Non-linearity detected in Q3 (Plateau). 2026 Projection: $12,400 ± 4% (High Confidence based on past MAPE)."
