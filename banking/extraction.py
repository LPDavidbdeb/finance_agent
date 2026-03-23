from .models import BankStatementImport, StagedTransaction
from .services import approve_staged_transaction
from ai_core.extractors.factory import PDFExtractorFactory
from decimal import Decimal
from datetime import datetime, date
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

    statement_import.status = BankStatementImport.Status.PROCESSING
    statement_import.save(update_fields=['status'])

    try:
        if not statement_import.file:
            raise ValueError("No file attached to statement import.")

        # 1. Attempt to get statement date from PDF content
        pdf_year, pdf_month = get_statement_date_from_pdf(statement_import.file.path)
        
        if pdf_year and pdf_month:
            statement_import.document_date = date(pdf_year, pdf_month, 1)
            statement_import.save(update_fields=['document_date'])
            statement_year = pdf_year
            statement_month = pdf_month
        elif statement_import.document_date:
            statement_year = statement_import.document_date.year
            statement_month = statement_import.document_date.month
        else:
            # FATAL: Cannot determine the statement period
            statement_import.status = BankStatementImport.Status.VALIDATION_FAILED
            statement_import.validation_errors = {
                'error': "Could not determine the statement date from the PDF content. Please re-upload and provide an explicit Document Date.",
                'timestamp': datetime.now().isoformat()
            }
            statement_import.save(update_fields=['status', 'validation_errors'])
            return

        product = statement_import.financial_product
        extractor = PDFExtractorFactory.get_extractor(product.institution.name, product.product_type)
        
        # 2. Extract with year/month context
        df, shadow_mismatch = extractor.extract(statement_import.file.path, statement_year, statement_month)
        
        statement_import.shadow_mode_mismatch = shadow_mismatch
        statement_import.save(update_fields=['shadow_mode_mismatch'])

        transactions_data = df.to_dict('records')
        institution_id = statement_import.financial_product.institution_id
        family_id = statement_import.financial_product.family_id

        staged_transactions = []
        for tx_data in transactions_data:
            raw_description = str(tx_data.get('description', ''))

            amount_val = tx_data.get('amount', 0)
            if pd.isna(amount_val):
                amount_val = 0
            clean_amount = Decimal(str(amount_val))

            rule = find_matching_rule(
                raw_description,
                institution_id,
                family_id,
                transaction_amount=clean_amount,
            )

            clean_desc = raw_description
            predicted_acc = None
            merchant_obj = None

            if rule:
                clean_desc = rule.merchant.name
                merchant_obj = rule.merchant
                if rule.merchant.is_unique_provider:
                    predicted_acc = rule.merchant.default_account

            staged_transactions.append(
                StagedTransaction(
                    statement_import=statement_import,
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
