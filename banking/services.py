from .models import FinancialProduct, BankStatementImport
from ai_core.extractors.factory import get_extractor
import tempfile
import os

def process_statement_upload(file, financial_product_id: int):
    """
    Orchestrates the entire process of handling a PDF statement upload.
    """
    # 1. Get the FinancialProduct
    product = FinancialProduct.objects.get(id=financial_product_id)

    # 2. Create an empty BankStatementImport record
    # This gives us an ID to pass to the extractor.
    import_record = BankStatementImport.objects.create(
        financial_product=product,
        status='PROCESSING',
        # Other fields like file_path can be set here if needed
    )

    # Save the uploaded file temporarily to pass its path to the extractor
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        for chunk in file.chunks():
            temp_file.write(chunk)
        temp_file_path = temp_file.name

    try:
        # 3. Call the Factory to get the appropriate extractor
        print(f"Getting extractor for: {product.institution.name}, {product.product_type}")
        extractor = get_extractor(product.institution.name, product.product_type)

        # 4. Run the extraction process
        # The execute method handles the AI call and saving the raw JSON
        raw_json = extractor.execute(temp_file_path, import_record.id)

        # 5. (Placeholder for tomorrow) Trigger deterministic validation
        print("AI extraction complete. Raw JSON received:")
        print(raw_json)
        # Here you would call your Python math-validation script, e.g.:
        # validation_errors = validate_extracted_data(raw_json)
        # if not validation_errors:
        #     import_record.status = 'VALIDATED'
        # else:
        #     import_record.status = 'VALIDATION_FAILED'
        #     import_record.validation_errors = validation_errors
        
        import_record.status = 'COMPLETED' # Placeholder status
        import_record.save()

        return {"status": "success", "import_id": import_record.id, "data": raw_json}

    except Exception as e:
        # If anything goes wrong, mark the import as failed
        import_record.status = 'FAILED'
        import_record.save()
        print(f"An error occurred during statement processing: {e}")
        # Re-raise the exception to be handled by the calling API view
        raise

    finally:
        # Clean up the temporary file
        os.remove(temp_file_path)
