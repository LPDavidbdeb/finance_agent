# Zero-Amount Transaction Workflow (`ZERO_AMOUNT_UNPROCESSED`)

This document defines how the system handles `0.00` transactions and why they appear as an `INFO` finding in Quality reports.

## Objective
- Reduce ingestion noise from non-financial rows (informational lines, layout artifacts, OCR/table parsing residue).
- Keep observability for investigation instead of silently hiding historical anomalies.
- Avoid treating zero-amount rows as ledger integrity failures.

## Current Policy
- `0.00` rows are surfaced as `ZERO_AMOUNT_UNPROCESSED` with severity `INFO`.
- They are not counted as hard failures in the consistency run status.
- They remain queryable for investigation and root-cause analysis.

## End-to-End Flow
1. **Extraction phase**
   - Extractors attempt to normalize amount fields.
   - When an extractor can confidently detect a `0.00` row as non-transactional noise, it skips row creation.

2. **Staging phase**
   - Any remaining zero-amount records that still enter staging stay `UNPROCESSED`.
   - Zero-amount staged rows are never auto-approved into accounting.

3. **Approval safeguards**
   - Approval service blocks zero-amount reconciliation into journal entries.
   - This prevents zero-value accounting mutations.

4. **Consistency analysis**
   - Report builder counts zero-amount staged rows as `zero_amount_unprocessed_count`.
   - Finding generator emits `ZERO_AMOUNT_UNPROCESSED` as `INFO`.

5. **UI/API visibility**
   - Appears in `/dashboard/quality` run findings.
   - Available via Quality API findings endpoints for filtering and follow-up.

## Why `INFO` and not `ERROR`
- The row is potentially noisy/useless, but not automatically a double-entry integrity violation.
- The system intentionally separates:
  - **Integrity failures** (unbalanced entries, missing journal links) -> blocking signals.
  - **Data quality anomalies** (zero rows) -> investigatory signals.

## Investigation Playbook
1. Open latest run in `Data Quality` page (`/dashboard/quality`).
2. Filter findings and locate `ZERO_AMOUNT_UNPROCESSED`.
3. Inspect related statement period/import source.
4. Classify root cause:
   - extractor/parser artifact,
   - bank informational line,
   - malformed input row.
5. Apply fix at the right layer:
   - extractor parsing rule,
   - statement mapping/cleanup,
   - explicit dismissal/cleanup of legacy rows.

## Related Components
- Extractor behavior: `ai_core/extractors/strategies.py`
- Approval guardrail: `banking/services.py`
- Report metrics: `banking/consistency.py`
- Finding generation: `quality/services.py`
- UI surface: `frontend/src/pages/QualityReportsPage.tsx`

## Escalation Option
If product policy changes to "zero amount must be zero always", promote this finding to `WARNING` or `ERROR` and include it in unexpected issue scoring.

