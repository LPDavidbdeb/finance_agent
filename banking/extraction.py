from .models import BankStatementImport, StagedTransaction
from ai_core.extractors.factory import PDFExtractorFactory
from decimal import Decimal
from datetime import datetime
from categorization.services import find_matching_rule
import logging
import pandas as pd

logger = logging.getLogger(__name__)

def extract_transactions_from_statement(import_id: int):
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

        product = statement_import.financial_product
        extractor = PDFExtractorFactory.get_extractor(product.institution.name, product.product_type)
        extract_year = statement_import.document_date.year if statement_import.document_date else datetime.now().year
        df = extractor.extract(statement_import.file.path, extract_year)
        
        transactions_data = df.to_dict('records')
        institution_id = statement_import.financial_product.institution_id

        staged_transactions = []
        for tx_data in transactions_data:
            raw_description = str(tx_data.get('description', ''))
            rule = find_matching_rule(raw_description, institution_id)
            
            clean_desc = rule.merchant_name if rule else raw_description
            predicted_acc = rule.target_account if rule else None
            
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
                    amount=Decimal(str(amount_val)),
                    unique_bank_id=tx_data.get('unique_bank_id'),
                    status=StagedTransaction.Status.UNPROCESSED,
                )
            )

        if staged_transactions:
            StagedTransaction.objects.bulk_create(staged_transactions, batch_size=1000)

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


def rerun_categorization(import_id: int):
    """
    Re-applies categorization rules to all UNPROCESSED staged transactions
    for a given statement import.
    """
    try:
        statement_import = BankStatementImport.objects.select_related('financial_product').get(id=import_id)
    except BankStatementImport.DoesNotExist:
        logger.error(f"BankStatementImport with id {import_id} not found.")
        return 0

    institution_id = statement_import.financial_product.institution_id
    
    staged_transactions = StagedTransaction.objects.filter(
        statement_import_id=import_id,
        status=StagedTransaction.Status.UNPROCESSED
    )

    updated_count = 0
    to_update = []
    
    for tx in staged_transactions:
        rule = find_matching_rule(tx.raw_description, institution_id)
        if rule:
            # Only update if something actually changed
            if tx.clean_description != rule.merchant_name or tx.predicted_account_id != rule.target_account_id:
                tx.clean_description = rule.merchant_name
                tx.predicted_account = rule.target_account
                to_update.append(tx)
                updated_count += 1

    if to_update:
        StagedTransaction.objects.bulk_update(to_update, ['clean_description', 'predicted_account'])
    
    return updated_count
