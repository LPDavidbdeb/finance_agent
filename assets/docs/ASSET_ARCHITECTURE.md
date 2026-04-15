# Asset & Liability Lifecycle Architecture

**Epic Goal:** Support physical assets and debt financing through automated, double-entry payment stripping.

**Strict Architectural Rules:**
1. **Service Layer Pattern:** Complex business logic (origination, payment stripping, re-amortization) MUST be placed in dedicated service modules (e.g., `services.py`). Do not put business logic in models or views.
2. **Observer Pattern (Django Signals):** Use pre/post-save signals to handle system state synchronicity (e.g., auto-generating categorization rules).
3. **Double-Entry Integrity:** Any script generating `JournalEntry` records must ensure `Debits = Credits`. Use compound (3+ line) entries for splitting principal and interest.
4. **State-Machine Projections:** Future `AnnuityPeriod` records are mutable projections. They must be dynamically calculated from the most recent rate in the `AnnuityRateHistory` table.