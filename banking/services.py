from django.db import transaction
from .models import FinancialProduct, FinancialInstitution, BankStatementImport
from accounting.models import Account
from users.models import Family, FamilyMember
from ai_core.extractors.factory import get_extractor
import tempfile
import os
from .validators import validate_statement_math
from .mappers import create_staged_transactions

# Defines how a banking product type maps into the accounting ledger tree
ACCOUNT_ROUTING_MAP = {
    FinancialProduct.ProductType.CHECKING: {"account_type": Account.AccountType.ASSET, "parent_name": "Bank Accounts"},
    FinancialProduct.ProductType.SAVINGS: {"account_type": Account.AccountType.ASSET, "parent_name": "Bank Accounts"},
    FinancialProduct.ProductType.CREDIT_CARD: {"account_type": Account.AccountType.LIABILITY, "parent_name": "Credit Cards"},
    FinancialProduct.ProductType.LOAN: {"account_type": Account.AccountType.LIABILITY, "parent_name": "Loans & Mortgages"},
    FinancialProduct.ProductType.INVESTMENT: {"account_type": Account.AccountType.ASSET, "parent_name": "Investments"},
    FinancialProduct.ProductType.REGISTERED: {"account_type": Account.AccountType.ASSET, "parent_name": "Investments"},
}

@transaction.atomic
def provision_financial_product(family: Family, owner: FamilyMember, institution_id: int, product_type: str, product_name: str, account_number: str = None) -> FinancialProduct:
    """
    Creates a FinancialProduct and its corresponding double-entry Account.
    """
    institution = FinancialInstitution.objects.get(id=institution_id)
    routing = ACCOUNT_ROUTING_MAP[product_type]

    # 1. Get or Create the Parent Account (e.g., "Bank Accounts" under "Assets")
    # This assumes the master template (Assets, Liabilities, etc.) exists in the DB
    parent_account, _ = Account.objects.get_or_create(
        name=routing["parent_name"],
        account_type=routing["account_type"],
        # We don't link the parent to a family if it's part of the global template, 
        # but for safety in a multi-tenant setup, we might scope it.
        # Assuming your master template seeds with family=None, this get_or_create 
        # might need adjusting depending on your exact MPTT structure.
        family=None # Or family=family based on your business logic
    )

    # 2. Create the Ledger Anchor Account
    full_account_name = f"{institution.name} {product_name}"
    
    account = Account.objects.create(
        name=full_account_name,
        account_type=routing["account_type"],
        parent=parent_account,
        family=family
    )
    
    # Ensure MPTT tree is correct
    # In a production app with heavy writes, you might rebuild periodically rather than inline
    # Account.objects.rebuild() 

    # 3. Create the Financial Product
    product = FinancialProduct.objects.create(
        institution=institution,
        family=family,
        owner=owner,
        account=account,
        product_type=product_type,
        account_number=account_number
    )

    return product

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