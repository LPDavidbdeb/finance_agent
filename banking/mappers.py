from .models import StagedTransaction, BankStatementImport
from typing import Dict, Any
import hashlib

def create_staged_transactions(import_record: BankStatementImport, raw_json: Dict[str, Any]):
    """
    Maps the validated JSON data to StagedTransaction model instances and bulk-creates them.
    """
    transactions_to_create = []
    
    for tx_data in raw_json.get('transactions', []):
        # Create a unique ID for the transaction to prevent duplicates
        # This hash is based on the data itself
        tx_string = f"{tx_data.get('date', '')}-{tx_data.get('transaction_date', '')}-{tx_data['description']}-{tx_data['amount']}"
        unique_id = hashlib.md5(tx_string.encode('utf-8')).hexdigest()

        # Separate core fields from metadata
        core_fields = {
            'statement_import': import_record,
            'bank_date': tx_data.get('date') or tx_data.get('transaction_date'), # Handle different date field names
            'raw_description': tx_data['description'],
            'amount': tx_data['amount'],
            'unique_bank_id': unique_id,
        }
        
        # All other fields from the transaction are stored in metadata
        metadata = {k: v for k, v in tx_data.items() if k not in ['date', 'transaction_date', 'description', 'amount']}

        transactions_to_create.append(
            StagedTransaction(**core_fields, metadata=metadata)
        )

    if transactions_to_create:
        StagedTransaction.objects.bulk_create(transactions_to_create)
        print(f"Successfully created {len(transactions_to_create)} staged transactions.")
    else:
        print("No transactions found in JSON to create.")
