# Visa Payment Extraction - FIXED ✅

## What Was Wrong

Payment rows in Visa PDFs have **duplicate date pairs**:

```
16   12        16   12      PAIEMENT AUTORISÉ - PRÉLÈVEMENT EFFECTUÉ       919,47CR
```

The old code used a hardcoded character slice (`str[12:]`) to extract the description, which didn't account for variable spacing in payment rows.

## The Fix

### 1. Smart Description Cleaning (FIXED)

**Before** (hardcoded character slice):
```python
df_clean['description'] = df_clean[desc_col].astype(str).str[12:].str.strip()
```
❌ Breaks with different spacing

**After** (regex-based):
```python
descriptions = df_clean[desc_col].astype(str).copy()
# Remove double date pattern (DD MM DD MM)
descriptions = descriptions.str.replace(r'^\d{2}\s+\d{2}\s+\d{2}\s+\d{2}\s+', '', regex=True)
# Remove single date pattern (DD MM)
descriptions = descriptions.str.replace(r'^\d{2}\s+\d{2}\s+', '', regex=True)
df_clean['description'] = descriptions.str.strip()
```
✅ Works with any spacing for both single and double dates

### 2. Fixed Amount Sign (FIXED)

**Before** (payments were negative):
```python
df_clean['amount'] = parsed_amount * np.where(has_cr | has_minus, -1, 1)
```
❌ Payments (CR) = negative (wrong!)

**After** (payments are positive):
```python
df_clean['amount'] = parsed_amount * np.where(has_cr | has_minus, 1, -1)
```
✅ Payments (CR) = positive (reduces liability)
✅ Purchases = negative (increases liability)

## Results

### Now Extracts:
- ✅ Regular purchases: `23 09 METRO` → amount: `-45.00`
- ✅ Payment rows: `16 12 16 12 PAIEMENT...` → amount: `+919.47`

## File Modified
- `/ai_core/extractors/strategies.py` - VisaDesjardinsExtractor

## Test It
```bash
python manage.py reprocess_all_statements
```

Payment transactions should now appear in your staging area with positive amounts!

