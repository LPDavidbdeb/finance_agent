from .models import BankStatementImport, StagedTransaction, FinancialProduct
from .services import approve_staged_transaction
from ai_core.extractors.factory import PDFExtractorFactory
from accounting.models import Account
from decimal import Decimal
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from categorization.services import find_matching_rule
import logging
import pandas as pd
import pdfplumber
import re

logger = logging.getLogger(__name__)

MONTH_MAP = {
    'janvier': 1, 'février': 2, 'fevrier': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
    'juillet': 7, 'août': 8, 'aout': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12, 'decembre': 12,
    'jan': 1, 'fév': 2, 'fev': 2, 'mar': 3, 'avr': 4, 'mai': 5, 'jun': 6, 'jul': 7, 'aoû': 8, 'aou': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'déc': 12, 'dec': 12,
    # English months
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'sept': 9,
}

def get_statement_date_from_pdf(pdf_path: str) -> tuple[int, int]:
    """
    Extracts the statement year and month from the PDF text using regex.
    Supports Visa Desjardins, Compte Desjardins, and Wealthsimple formats.
    Checks the first 3 pages to find the header.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Check the first 3 pages
            for i in range(min(3, len(pdf.pages))):
                page = pdf.pages[i]
                text = page.extract_text()
                if not text:
                    continue
                
                # Pattern 1: Visa Desjardins (DATE DU RELEVÉ Jour DD Mois MM Année YYYY)
                pattern1 = r'DATE DU RELEVÉ\s+Jour\s+\d{2}\s+Mois\s+(\d{2})\s+Année\s+(\d{4})'
                match1 = re.search(pattern1, text)
                if match1:
                    return int(match1.group(2)), int(match1.group(1))
                
                # Pattern 2: Compte Desjardins (au DD [Mois] YYYY)
                # Support abbreviations with dots (e.g., déc.) and more accents
                pattern2 = r'au\s+\d{1,2}\s+([a-zA-ZûéÉÀàâÂêÊîÎôÔûÛëËïÏüÜ\.]+)\s+(\d{4})'
                match2 = re.search(pattern2, text, re.IGNORECASE)
                if match2:
                    month_name = match2.group(1).lower().rstrip('.')
                    month = MONTH_MAP.get(month_name)
                    year = int(match2.group(2))
                    if month:
                        return year, month

                # Pattern 3: Wealthsimple (Month DD - Month DD, YYYY)
                pattern3 = r'([a-zA-Z]+)\s+\d{1,2}\s+-\s+[a-zA-Z]+\s+\d{1,2},\s+(\d{4})'
                match3 = re.search(pattern3, text)
                if match3:
                    month_name = match3.group(1).lower()
                    month = MONTH_MAP.get(month_name)
                    year = int(match3.group(2))
                    if month:
                        return year, month

                # Pattern 4: Wealthsimple Alternative (YYYY-MM-DD - YYYY-MM-DD)
                pattern4 = r'(\d{4})-(\d{2})-\d{2}\s+-\s+\d{4}-\d{2}-\d{2}'
                match4 = re.search(pattern4, text)
                if match4:
                    return int(match4.group(1)), int(match4.group(2))
    except Exception as e:
        logger.warning(f"Failed to extract date from PDF {pdf_path}: {e}")
    
    return None, None

def extract_transactions_from_statement(import_id: int, user):
    """
    Extract transactions from an uploaded statement, auto-categorize them,
    and stage them for review.
    """
    try:
        statement_import = BankStatementImport.objects.get(id=import_id)
    except BankStatementImport.DoesNotExist:
        logger.error(f"BankStatementImport with id {import_id} not found.")
        return

    print(f"[EXTRACT] START statement_id={import_id}")
    statement_import.status = BankStatementImport.Status.PROCESSING
    statement_import.save(update_fields=['status'])

    try:
        if not statement_import.file:
            raise ValueError("No file attached to statement import.")

        print(f"[EXTRACT] Step 1 — reading PDF to detect statement date: {statement_import.file.path}")
        pdf_year, pdf_month = get_statement_date_from_pdf(statement_import.file.path)

        if pdf_year and pdf_month:
            statement_import.document_date = date(pdf_year, pdf_month, 1)
            statement_import.save(update_fields=['document_date'])
            statement_year = pdf_year
            statement_month = pdf_month
            print(f"[EXTRACT] Date detected from PDF: {pdf_year}-{pdf_month:02d}")
        elif statement_import.document_date:
            statement_year = statement_import.document_date.year
            statement_month = statement_import.document_date.month
            print(f"[EXTRACT] Using manually provided date: {statement_year}-{statement_month:02d}")
        else:
            print(f"[EXTRACT] FATAL — could not determine statement date")
            statement_import.status = BankStatementImport.Status.VALIDATION_FAILED
            statement_import.validation_errors = {
                'error': "Could not determine the statement date from the PDF content. Please re-upload and provide an explicit Document Date.",
                'timestamp': datetime.now().isoformat()
            }
            statement_import.save(update_fields=['status', 'validation_errors'])
            return

        # --- Step 2: Select extractor ---
        # Legacy path: financial_product is set → route by institution + product type.
        # Multi-product path: only institution is set → route by institution alone.
        legacy_product = statement_import.financial_product
        institution = statement_import.institution

        if not institution:
            raise ValueError(
                f"BankStatementImport {statement_import.id} has no institution set. "
                "Re-upload via the new import flow or run the institution backfill migration."
            )

        if legacy_product:
            print(f"[EXTRACT] Step 2 — selecting parser for: {institution.name} / {legacy_product.product_type}")
            extractor = PDFExtractorFactory.get_extractor(institution.name, legacy_product.product_type)
        else:
            print(f"[EXTRACT] Step 2 — selecting multi-product parser for: {institution.name}")
            extractor = PDFExtractorFactory.get_extractor(institution.name)
        print(f"[EXTRACT] Parser selected: {type(extractor).__name__}")

        print(f"[EXTRACT] Step 3 — parsing PDF with tabula...")
        df, shadow_mismatch = extractor.extract(statement_import.file.path, statement_year, statement_month)

        statement_import.shadow_mode_mismatch = shadow_mismatch
        statement_import.save(update_fields=['shadow_mode_mismatch'])

        transactions_data = df.to_dict('records')
        print(f"[EXTRACT] Parsed {len(transactions_data)} rows. Shadow mismatch: {shadow_mismatch}")

        # Build a lookup cache: account_number → FinancialProduct for this institution.
        # Used for per-row routing when the extractor emits an account_number column.
        product_by_account_number = {
            p.account_number: p
            for p in FinancialProduct.objects.filter(institution=institution)
            if p.account_number
        }

        print(f"[EXTRACT] Step 4 — categorizing {len(transactions_data)} transactions...")
        staged_transactions = []
        for tx_data in transactions_data:
            raw_description = str(tx_data.get('description', ''))

            amount_val = tx_data.get('amount', 0)
            if pd.isna(amount_val):
                amount_val = 0
            clean_amount = Decimal(str(amount_val))

            # --- Per-row product routing ---
            row_account_number = tx_data.get('account_number') or tx_data.get('account_identifier')
            if row_account_number:
                resolved_product = product_by_account_number.get(str(row_account_number).strip())
                if not resolved_product:
                    raise ValueError(
                        f"No FinancialProduct found for account_number '{row_account_number}' "
                        f"under institution '{institution.name}'. "
                        "Register the product (with that exact account_number) before re-importing."
                    )
            else:
                # Legacy fallback: no account_number in row → use statement-level product.
                if not legacy_product:
                    raise ValueError(
                        f"Row has no account_number and statement_import {statement_import.id} "
                        "has no financial_product. Cannot route transaction."
                    )
                resolved_product = legacy_product

            rule = find_matching_rule(
                raw_description,
                resolved_product.institution_id,
                resolved_product.family_id,
                transaction_amount=clean_amount,
            )

            predicted_acc = None
            merchant_obj = None

            if rule:
                merchant_obj = rule.merchant
                if rule.merchant.is_unique_provider:
                    predicted_acc = rule.merchant.default_account

            staged_transactions.append(
                StagedTransaction(
                    statement_import=statement_import,
                    financial_product=resolved_product,
                    bank_date=tx_data.get('date'),
                    raw_description=raw_description,
                    predicted_account=predicted_acc,
                    merchant=merchant_obj,
                    amount=clean_amount,
                    unique_bank_id=tx_data.get('unique_bank_id'),
                    status=StagedTransaction.Status.UNPROCESSED,
                )
            )


        if staged_transactions:
            StagedTransaction.objects.bulk_create(staged_transactions, batch_size=1000)

        # Auto-approve transactions with a predicted account
        auto_approve_queryset = StagedTransaction.objects.filter(
            statement_import_id=import_id,
            predicted_account__isnull=False,
            status=StagedTransaction.Status.UNPROCESSED
        )
        
        for tx in auto_approve_queryset:
            try:
                approve_staged_transaction(
                    transaction_id=tx.id,
                    target_account_id=tx.predicted_account_id,
                    user=user
                )
            except (PermissionError, ValueError) as e:
                logger.warning(f"Auto-approval skipped for transaction {tx.id}: {str(e)}")
            except Exception as e:
                logger.exception(f"Unexpected error during auto-approval for transaction {tx.id}: {str(e)}")

        # Historical auto-routing: for statements older than 3 months, route all
        # remaining unprocessed transactions rather than leaving them in staging.
        # Payments go to Internal Transfers (balance sheet movement, not an expense).
        # Everything else goes to Uncategorized Expenses (expense is real, category unknown).
        cutoff_date = date.today() - relativedelta(months=3)
        statement_date = statement_import.document_date

        if statement_date and statement_date < cutoff_date:
            if statement_import.financial_product:
                family = statement_import.financial_product.family
            else:
                # Multi-product import: derive family from the first product under the institution.
                first_product = FinancialProduct.objects.filter(institution=institution).first()
                family = first_product.family if first_product else None
            uncategorized = Account.objects.filter(
                family=family, name__iexact='Uncategorized Expenses'
            ).first()
            internal_transfer = Account.objects.filter(
                family=family, name__iexact='Internal Transfers'
            ).first()

            if not uncategorized:
                logger.warning(
                    f"'Uncategorized Expenses' account not found for family {family.id}. "
                    "Skipping historical auto-routing. Run rebuild_accounting_master to create it."
                )
            else:
                remaining = StagedTransaction.objects.filter(
                    statement_import=statement_import,
                    status=StagedTransaction.Status.UNPROCESSED
                )
                for tx in remaining:
                    is_payment = 'PAIEMENT' in tx.raw_description.upper()
                    target = internal_transfer if (is_payment and internal_transfer) else uncategorized
                    try:
                        approve_staged_transaction(
                            transaction_id=tx.id,
                            target_account_id=target.id,
                            user=user
                        )
                    except (PermissionError, ValueError) as e:
                        logger.warning(f"Historical auto-routing skipped for tx {tx.id}: {str(e)}")
                    except Exception as e:
                        logger.exception(f"Unexpected error during historical auto-routing for tx {tx.id}: {str(e)}")

        statement_import.processed_by_python = True
        statement_import.status = BankStatementImport.Status.COMPLETED
        statement_import.validation_errors = None
        statement_import.save(update_fields=['processed_by_python', 'status', 'validation_errors'])

    except Exception as e:
        logger.exception(f"Error extracting transactions from statement {import_id}: {str(e)}")
        statement_import.status = BankStatementImport.Status.FAILED
        statement_import.validation_errors = {
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }
        statement_import.save(update_fields=['status', 'validation_errors'])
