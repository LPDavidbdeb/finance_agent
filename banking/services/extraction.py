import logging
from datetime import datetime
from decimal import Decimal

from banking.models import BankStatementImport, StagedTransaction
from categorization.services import find_matching_rule

logger = logging.getLogger(__name__)


def extract_transactions_from_statement(import_id: int):
    """
    Extracts transactions from a BankStatementImport PDF file, matches merchant names,
    and creates StagedTransaction records. Sets status and processing flags accordingly.
    """
    try:
        statement_import = BankStatementImport.objects.get(id=import_id)
    except BankStatementImport.DoesNotExist:
        logger.error(f"BankStatementImport with id {import_id} not found.")
        return

    # Mark as processing
    statement_import.status = BankStatementImport.Status.PROCESSING
    statement_import.save(update_fields=['status'])

    try:
        if not statement_import.file:
            raise ValueError("No file attached to statement import.")

        # Get the PDF file path
        file_path = statement_import.file.path
        institution_id = statement_import.financial_product.institution_id
        product_type = statement_import.financial_product.product_type

        # Parse the PDF and extract transactions
        # For now, return an empty list since we're just staging,
        # but in a full implementation, call your PDF extractor here.
        transactions_data = []

        # Example structure each transaction should have:
        # {
        #     'date': datetime.date,
        #     'description': str,
        #     'amount': Decimal,
        #     'unique_bank_id': str (optional),
        # }

        # If using your AI extractors:
        # from ai_core.extractors.factory import get_extractor
        # extractor = get_extractor(statement_import.financial_product.institution.name, product_type)
        # result = extractor.execute(file_path, import_id)
        # transactions_data = parse_extractor_result(result)

        # If using pandas+tabula extractors (future):
        # from ai_core.extractors.factory import PDFExtractorFactory
        # extractor = PDFExtractorFactory.get_extractor(institution_name, product_type)
        # df = extractor.extract(file_path, extract_year=datetime.now().year)
        # transactions_data = [{
        #     'date': row.date,
        #     'description': row.description,
        #     'amount': Decimal(str(row.amount)),
        # } for row in df.itertuples()]

        staged_transactions = []
        for tx_data in transactions_data:
            raw_description = tx_data.get('description', '')

            # Find matching rule and normalize merchant name
            rule = find_matching_rule(raw_description, institution_id)
            if rule:
                final_description = rule.merchant_name
            else:
                final_description = raw_description

            staged_tx = StagedTransaction(
                statement_import=statement_import,
                bank_date=tx_data.get('date'),
                raw_description=final_description,
                amount=Decimal(str(tx_data.get('amount', 0))),
                unique_bank_id=tx_data.get('unique_bank_id'),
                status=StagedTransaction.Status.UNPROCESSED,
            )
            staged_transactions.append(staged_tx)

        # Bulk create all staged transactions
        if staged_transactions:
            StagedTransaction.objects.bulk_create(staged_transactions, batch_size=1000)
            logger.info(f"Created {len(staged_transactions)} staged transactions for import {import_id}.")

        # Mark extraction complete
        statement_import.processed_by_python = True
        statement_import.status = BankStatementImport.Status.PROCESSING
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

