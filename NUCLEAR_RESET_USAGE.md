# Nuclear Reset & Reseed Procedure

This document formalizes the standard procedure for wiping all transactional data and regenerating the ledger from source PDF statements. This is useful when extraction logic has been updated or when debugging data integrity issues.

## ⚠️ Important: Scope
- **DELETES**: All `JournalEntry`, `TransactionLine`, and `StagedTransaction` records.
- **KEEPS**: 
  - Source PDF files in `/media/statements/`
  - `BankStatementImport` records (metadata only)
  - Chart of Accounts (Account tree structure)
  - Merchant Categorization Rules
  - Family and User records

---

## Step 1: The Wipe (ledger_reset)
This command clears the transactional slate. It handles dependencies correctly and resets database sequences so new transactions start from ID 1.
After completion, it prints a post-reset consistency check so you can confirm the ledger was fully wiped.

### 1.1 Dry Run (Recommended)
Verify how many records will be affected without actually deleting them.
```bash
python manage.py ledger_reset --dry-run
```

### 1.2 Execute
Perform the destructive reset.
```bash
python manage.py ledger_reset --confirm
```

---

## Step 2: The Reseed (reprocess_all_statements)
This command goes through every `BankStatementImport` record, finds the associated PDF, and re-runs the entire extraction pipeline.
When it finishes, it prints a consistency analysis covering:
- auto-routed transactions matched by categorization rules
- fallback-routed transactions older than 3 months
- recent transactions left for manual review
- zero-amount exceptions and any ledger integrity issues

### Why this works:
- It uses the latest **Extractor logic** (including fixed CR/Refund detection).
- It applies the **3-Month Rule**:
  - Transactions matched to rules are auto-approved to the ledger.
  - Unmapped transactions **< 3 months old** stay in the Staging area for review.
  - Unmapped transactions **>= 3 months old** are auto-approved to fallback accounts (UNCATEGORIZED) to keep the ledger complete.

### 2.1 Start Reprocessing
```bash
python manage.py reprocess_all_statements
```

---

## Summary of Commands
| Action | Command |
| :--- | :--- |
| **Reset** | `python manage.py ledger_reset --confirm` |
| **Reseed** | `python manage.py reprocess_all_statements` |

## Specialized Reprocessing (Optional)
If you only want to reprocess specific statements:
- **By Family**: `python manage.py reprocess_all_statements --family-id <UUID>`
- **By Date**: `python manage.py reprocess_all_statements --since 2025-01-01`
- **Tangerine Only**: `python manage.py reprocess_all_statements --tangerine`
