from ninja import Router, File, Form
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja_jwt.authentication import JWTAuth
from typing import List, Optional
from datetime import date
from django.shortcuts import get_object_or_404
from django.db.models import ProtectedError, Count
from django.db.models.functions import TruncMonth
from users.models import FamilyMember

from .schemas import (
    FinancialProductIn,
    FinancialProductOut,
    InstitutionOut,
    InstitutionIn,
    StatementUploadOut,
    StatementImportOut,
    StagedTransactionOut,
    TransactionApproveIn,
    StatementMonthOut,
)
from .models import FinancialInstitution, FinancialProduct, BankStatementImport, StagedTransaction
from .services import provision_financial_product, approve_staged_transaction

router = Router(auth=JWTAuth())

# --- Institutions CRUD ---

@router.get("/institutions", response=List[InstitutionOut], auth=None)
def list_institutions(request):
    """Returns a list of all supported financial institutions."""
    return FinancialInstitution.objects.all()

@router.get("/institutions/{institution_id}", response=InstitutionOut, auth=None)
def get_institution(request, institution_id: int):
    """Returns a specific institution."""
    return get_object_or_404(FinancialInstitution, id=institution_id)

@router.post("/institutions", response=InstitutionOut)
def create_institution(request, payload: InstitutionIn):
    """Creates a new financial institution."""
    institution = FinancialInstitution.objects.create(name=payload.name)
    return institution

@router.put("/institutions/{institution_id}", response=InstitutionOut)
def update_institution(request, institution_id: int, payload: InstitutionIn):
    """Updates an existing financial institution."""
    institution = get_object_or_404(FinancialInstitution, id=institution_id)
    institution.name = payload.name
    institution.save()
    return institution

@router.delete("/institutions/{institution_id}")
def delete_institution(request, institution_id: int):
    """Deletes a financial institution."""
    institution = get_object_or_404(FinancialInstitution, id=institution_id)
    try:
        institution.delete()
        return {"success": True}
    except ProtectedError:
        raise HttpError(400, "Cannot delete this institution because it is currently linked to one or more financial products.")


# --- Products ---

@router.get("/products", response=List[FinancialProductOut])
def list_products(request, owner_id: Optional[int] = None):
    """Returns financial products, optionally filtered by owner."""
    user = request.auth
    queryset = FinancialProduct.objects.filter(family=user.family).select_related('institution', 'account', 'account__parent')
    
    if owner_id:
        queryset = queryset.filter(owner_id=owner_id)
        
    return queryset

@router.get("/products/{product_id}", response=FinancialProductOut)
def get_product(request, product_id: int):
    """Returns a specific financial product."""
    user = request.auth
    product = get_object_or_404(FinancialProduct.objects.select_related('institution', 'account', 'account__parent'), id=product_id, family=user.family)
    return product

@router.post("/products", response=FinancialProductOut)
def create_product(request, payload: FinancialProductIn):
    """Provisions a new financial product and creates its corresponding ledger account."""
    user = request.auth
    
    # Verify owner belongs to the same family
    owner = get_object_or_404(FamilyMember, id=payload.owner_id, family=user.family)
        
    product = provision_financial_product(
        family=user.family,
        owner=owner,
        institution_id=payload.institution_id,
        product_type=payload.product_type,
        product_name=payload.product_name,
        account_number=payload.account_number
    )
    
    return product

@router.post("/products/{product_id}/statements/upload", response=StatementUploadOut)
def upload_statement(request, product_id: int, file: File[UploadedFile], document_date: Optional[date] = Form(None)):
    """Stores a bank statement and triggers Python extraction pipeline."""
    import logging
    from banking.extraction import extract_transactions_from_statement

    user = request.auth
    product = get_object_or_404(FinancialProduct, id=product_id, family=user.family)

    statement = BankStatementImport.objects.create(
        financial_product=product,
        file=file,
        document_date=document_date,
        status=BankStatementImport.Status.STAGED,
        processed_by_ai=False,
        processed_by_python=False,
    )

    # Trigger extraction in a try/except so HTTP response is not disrupted
    try:
        extract_transactions_from_statement(statement.id, user)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Extraction failed for statement {statement.id}: {str(e)}")
        # Error is already persisted in the statement_import record by extract_transactions_from_statement

    return statement


@router.get("/products/{product_id}/statements", response=List[StatementImportOut])
def list_product_statements(request, product_id: int):
    """Returns staged/imported statements for one product in newest-first order."""
    user = request.auth
    product = get_object_or_404(FinancialProduct, id=product_id, family=user.family)
    return BankStatementImport.objects.filter(financial_product=product).order_by("-upload_date")


@router.delete("/imports/{import_id}")
def delete_statement_import(request, import_id: int):
    """Deletes a statement import and all its staged transactions (via CASCADE)."""
    user = request.auth
    statement = get_object_or_404(BankStatementImport, id=import_id, financial_product__family=user.family)
    statement.delete()
    return {"success": True}


@router.get("/products/{product_id}/staged-transactions", response=List[StagedTransactionOut])
def list_staged_transactions(request, product_id: int):
    """Returns all unprocessed staged transactions for a product, ordered by date (newest first)."""
    user = request.auth
    product = get_object_or_404(FinancialProduct, id=product_id, family=user.family)
    return StagedTransaction.objects.filter(
        statement_import__financial_product=product,
        status=StagedTransaction.Status.UNPROCESSED
    ).select_related('predicted_account', 'journal_entry').prefetch_related('journal_entry__lines__account').order_by("-bank_date")


@router.get("/products/{product_id}/statement-months", response=List[StatementMonthOut])
def list_statement_months(request, product_id: int):
    """Returns chronological list of months with transaction counts for a product."""
    user = request.auth
    product = get_object_or_404(FinancialProduct, id=product_id, family=user.family)
    
    months = StagedTransaction.objects.filter(
        statement_import__financial_product=product
    ).annotate(
        month=TruncMonth('bank_date')
    ).values('month').annotate(
        transaction_count=Count('id')
    ).order_by('-month')
    
    return [
        {
            "month": m['month'],
            "display_name": m['month'].strftime("%B %Y"),
            "transaction_count": m['transaction_count']
        }
        for m in months
    ]


@router.get("/products/{product_id}/statements/{year}/{month}/transactions", response=List[StagedTransactionOut])
def list_statement_transactions(request, product_id: int, year: int, month: int):
    """Returns all transactions (unprocessed, pending, and reconciled) for a specific product in a specific month."""
    user = request.auth
    product = get_object_or_404(FinancialProduct, id=product_id, family=user.family)
    
    return StagedTransaction.objects.filter(
        statement_import__financial_product=product,
        bank_date__year=year,
        bank_date__month=month
    ).select_related('predicted_account', 'journal_entry').prefetch_related('journal_entry__lines__account').order_by("-bank_date")


@router.post("/products/{product_id}/staged-transactions/{transaction_id}/approve")
def approve_transaction_endpoint(request, product_id: int, transaction_id: int, payload: TransactionApproveIn):
    """Approves a staged transaction and records it in the double-entry ledger."""
    user = request.auth
    
    # We just need to check if the product exists for the user, logic is handled in service
    get_object_or_404(FinancialProduct, id=product_id, family=user.family)

    try:
        approve_staged_transaction(
            transaction_id=transaction_id,
            target_account_id=payload.target_account_id,
            user=user
        )
        return {"success": True, "message": "Transaction approved and reconciled."}
    except PermissionError as e:
        raise HttpError(403, str(e))
    except ValueError as e:
        raise HttpError(400, str(e))
    except Exception as e:
        # Log unexpected errors
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Unexpected error approving transaction {transaction_id}")
        raise HttpError(500, "An internal error occurred.")
