# Nuclear Reset Command - FIXED

## What It Does

Safely deletes ALL transactional data from your accounting system:
- ❌ Deletes all `JournalEntry` records
- ❌ Deletes all `TransactionLine` records  
- ❌ Deletes all `StagedTransaction` records
- ✅ Keeps all PDFs in `/media/statements/`
- ✅ Keeps all `BankStatementImport` records (just resets their status)
- ✅ Keeps your account chart of accounts

## Usage

### Step 1: Dry Run (See what will be deleted)
```bash
python manage.py ledger_reset --dry-run
```

Expected output:
```
Summary of records to be deleted:
  TransactionLine:  XXXX
  JournalEntry:     XXXX
  StagedTransaction: XXXX

DRY RUN COMPLETE. No data was mutated.
```

### Step 2: Execute (Actually delete everything)
```bash
python manage.py ledger_reset --confirm
```

Expected output:
```
DESTRUCTIVE RESET STARTED...
  Processing 709rueBeaudoin (dacbb90a-406b-4645-87d2-419645aead0a)...
    - Deleted XXXX TransactionLines
    - Deleted XXXX JournalEntries
    - Deleted XXXX StagedTransactions
    - Reset XX BankStatementImports to STAGED

RESET COMPLETE in X.XXs
```

## Safety Features

✅ Requires either `--dry-run` OR `--confirm` (not both, not neither)  
✅ Uses atomic transactions (all-or-nothing per deletion step)  
✅ Deletes in proper dependency order:
  1. TransactionLine (foreign key to JournalEntry)
  2. JournalEntry (foreign key from StagedTransaction)
  3. StagedTransaction (links back to statement)
  
✅ Resets statement status to `STAGED` for re-processing  

## After Reset

Your database will be:
- Empty of all transactional data
- Ready for re-import from PDFs
- All BankStatementImport records reset to `STAGED` status

Then you can:
```bash
python manage.py reprocess_all_statements
```

to re-extract all transactions from PDFs.

---

## The Fix Applied

Changed line 79 from:
```python
status='PENDING'  # ❌ Invalid status value
```

To:
```python
status=BankStatementImport.Status.STAGED  # ✅ Valid enum value
```

This is now the nuclear option that actually works.

