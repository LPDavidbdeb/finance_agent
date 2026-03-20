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

FRENCH_MONTHS = {
    'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
    'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
}

def get_statement_date_from_pdf(pdf_path: str) -> tuple[int, int]:
    """
    Extracts the statement year and month from the PDF text using regex.
    Supports Visa Desjardins and Compte Desjardins formats.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            # Pattern 1: Visa Desjardins (DATE DU RELEVÉ Jour DD Mois MM Année YYYY)
            pattern1 = r'DATE DU RELEVÉ\s+Jour\s+\d{2}\s+Mois\s+(\d{2})\s+Année\s+(\d{4})'
            match1 = re.search(pattern1, text)
            if match1:
                return int(match1.group(2)), int(match1.group(1))
            
            # Pattern 2: Compte Desjardins (au DD [Mois] YYYY)
            pattern2 = r'au\s+\d{1,2}\s+([a-zA-Zûé]+)\s+(\d{4})'
            match2 = re.search(pattern2, text, re.IGNORECASE)
            if match2:
                month_name = match2.group(1).lower()
                month = FRENCH_MONTHS.get(month_name)
                year = int(match2.group(2))
                if month:
                    return year, month
                    
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
        else:
            # Fallback to current date or existing document_date
            fallback_date = statement_import.document_date or datetime.now().date()
            statement_year = fallback_date.year
            statement_month = fallback_date.month

        product = statement_import.financial_product
        extractor = PDFExtractorFactory.get_extractor(product.institution.name, product.product_type)
        
        # 2. Extract with year/month context
        df = extractor.extract(statement_import.file.path, statement_year, statement_month)
        
        transactions_data = df.to_dict('records')
        institution_id = statement_import.financial_product.institution_id
        family_id = statement_import.financial_product.family_id

        staged_transactions = []
        for tx_data in transactions_data:
            raw_description = str(tx_data.get('description', ''))
            rule = find_matching_rule(raw_description, institution_id, family_id)

            clean_desc = raw_description
            predicted_acc = None
            merchant_obj = None

            if rule:
                clean_desc = rule.merchant.name
                merchant_obj = rule.merchant
                if rule.merchant.is_unique_provider:
                    predicted_acc = rule.merchant.default_account

            amount_val = tx_data.get('amount', 0)
            if pd.isna(amount_val):
                amount_val = 0

            staged_transactions.append(
                StagedTransaction(
                    statement_import=statement_import,
                    bank_date=tx_data.get('date'),
                    raw_description=raw_description,
                    clean_description=clean_desc,
                    predicted_account=predicted_acc,
                    merchant=merchant_obj,
                    amount=Decimal(str(amount_val)),
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
