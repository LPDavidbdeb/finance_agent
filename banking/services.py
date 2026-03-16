from .models import FinancialProduct, BankStatementImport
from ai_core.extractors.factory import get_extractor
from .validators import validate_statement_math
from .mappers import create_staged_transactions
import tempfile
import os

def process_statement_upload(file, financial_product_id: int):
    """
    Orchestrates the entire process of handling a PDF statement upload,
    including AI extraction, validation, and record creation.
    """
    product = FinancialProduct.objects.get(id=financial_product_id)
    import_record = BankStatementImport.objects.create(
        financial_product=product,
        status='PROCESSING',
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        for chunk in file.chunks():
            temp_file.write(chunk)
        temp_file_path = temp_file.name

    try:
        # Step 1: Get extractor and run AI extraction
        print(f"Getting extractor for: {product.institution.name}, {product.product_type}")
        extractor = get_extractor(product.institution.name, product.product_type)
        raw_json = extractor.execute(temp_file_path, import_record.id)

        # Step 2: Run deterministic validation
        print("AI extraction complete. Running validation...")
        validation_errors = validate_statement_math(raw_json)

        # Step 3: Check for validation errors
        if validation_errors:
            print(f"Validation failed with errors: {validation_errors}")
            import_record.status = 'VALIDATION_FAILED'
            import_record.validation_errors = validation_errors
            import_record.save()
            return {"status": "error", "import_id": import_record.id, "errors": validation_errors}
        
        # Step 4: If validation passes, create the records
        print("Validation passed. Creating staged transactions...")
        create_staged_transactions(import_record, raw_json)
        
        import_record.status = 'VALIDATED'
        import_record.save()

        return {"status": "success", "import_id": import_record.id, "message": "Statement processed and validated successfully."}

    except Exception as e:
        import_record.status = 'FAILED'
        import_record.save()
        print(f"A critical error occurred during statement processing: {e}")
        # It's good practice to log the full exception here
        raise

    finally:
        os.remove(temp_file_path)
