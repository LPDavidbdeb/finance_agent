# Epic: Automated Asset & Liability Lifecycle Management

## System Context
This document is the authoritative source of truth for the implementation of the "Automated Asset & Liability Lifecycle Management" feature. 

**For the AI Coding Agent:** You are acting as an Expert Django/React Developer. You will be assigned specific **Phases** of this Epic one at a time by the Product Owner. **Do not execute phases you have not been explicitly assigned in your prompt.** Use this document to understand the overarching architecture, ensure your current task aligns with the final vision, and strictly adhere to the development rules below.

---

## 🏗️ Architectural Rules & Design Patterns

To maintain a clean, DRY, and scalable Django architecture, all code written for this epic must adhere to the following principles:

1. **Service Layer Pattern (No Fat Models/Views):**
   * Complex business logic (e.g., loan origination, payment stripping, schedule re-calculation) MUST be decoupled from Django models and views.
   * Place this logic in dedicated service modules (e.g., `planning/services/origination.py`, `banking/services/reconciliation.py`).
2. **Observer Pattern (Django Signals):**
   * System state synchronicity (e.g., automatically generating a `TransactionMappingRule` when an `AnnuitySchedule` is created) MUST be handled via Django pre/post-save signals. Do not hardcode this into views or basic save methods.
3. **Double-Entry Integrity (Factory Method):**
   * Generation of multi-line `JournalEntry` records MUST be handled by centralized factory/service functions. 
   * An entry must always strictly balance: `Assets = Liabilities + Equity` (or `Debits = Credits`).
4. **State-Machine Projections:**
   * Reconciled ledger entries are immutable. 
   * Future `AnnuityPeriod` records are highly mutable *projections*. They are dynamically generated and re-calculated based on the latest state of the `AnnuityRateHistory` table.

---

## 🚦 Rules of Engagement (AI Agent Mandates)

When you complete an assigned Phase, you MUST stop coding and provide an **Execution Report** to the Product Owner. Do not proceed to the next phase.

**Your Execution Report must include:**
1. **Summary of Files Modified/Created.**
2. **Architectural Decisions:** Why did you place models/services where you did?
3. **Test Results:** Proof that your code meets the Phase's Acceptance Criteria.
4. **Next Steps:** A brief note acknowledging readiness for the next Phase.

**Testing Mandate:** No phase is complete without accompanying Pytest/Django `TestCase` coverage. You must write unit tests for mathematical accuracy and integration tests for ledger balancing.

---

## 📋 Implementation Phases & Status

*(Product Owner: Check these boxes `[x]` as phases are completed and merged)*

### [ ] Phase 1: Foundation (Data Layer & Projections)
**Goal:** Extend the data models to represent physical assets and variable interest rate histories.
* **Acceptance Criteria:**
  * Create `TangibleAsset` model (likely in `planning/models.py` or a new `assets` app).
  * `TangibleAsset` must link to `Family`, `FamilyMember`, `purchase_transaction`, `loan_schedule`, and have a 1-to-1 relationship with an `Account` of type `ASSET`. Include `purchase_value` and `current_market_value`.
  * Create `AnnuityRateHistory` model (`effective_date`, `annual_rate`) linked to `AnnuitySchedule`.
  * Refactor `AnnuitySchedule` to drop the static rate field and instead query the most recent rate from `AnnuityRateHistory` for forward-looking math.
  * **Tests:** Validate that the rate history queries correctly for a given date.

### [ ] Phase 2: The Origination Engine (CapEx Setup)
**Goal:** Initialize an asset purchase with a mixed capital structure (cash down + debt).
* **Acceptance Criteria:**
  * Implement `OriginationService.acquire_financed_asset()`.
  * Must accept asset details, total cost, cash down, financed amount, origination date, term, and initial rate.
  * Must generate a balanced 3-line `JournalEntry` (Debit Asset, Credit Cash, Credit Liability).
  * Must instantiate the `AnnuitySchedule` and generate the initial set of `AnnuityPeriod` projections.
  * **Tests:** Assert the generated `JournalEntry` mathematically balances perfectly.

### [ ] Phase 3: Smart Categorization Interception
**Goal:** Link categorization rules to amortization schedules to flag transactions for payment stripping.
* **Acceptance Criteria:**
  * Add `linked_schedule` (ForeignKey to `AnnuitySchedule`) to `categorization.TransactionMappingRule`.
  * Implement a Django Signal: Upon creation of an `AnnuitySchedule`, auto-generate a `TransactionMappingRule` (e.g., match the institution name and the `computed_payment` ± $5.00).
  * Expose the `linked_schedule` flag to the main statement processing pipeline.
  * **Tests:** Assert the signal fires correctly and creates an accurate mapping rule bounds.

### [ ] Phase 4: The Reconciler (Automated Payment Stripping)
**Goal:** Intercept bank statement processing to split loan payments into principal and interest.
* **Acceptance Criteria:**
  * Implement `AmortizationReconciliationService`.
  * When a `StagedTransaction` triggers a rule with a `linked_schedule`, query for the oldest unpaid `AnnuityPeriod` within a ± 5-day window of the bank transaction date.
  * Generate a 3-line compound `JournalEntry` (Credit Bank, Debit Liability [Principal], Debit Expense [Interest]).
  * Mark the `AnnuityPeriod` as `is_paid = True` and link the Journal Entry.
  * **Tests