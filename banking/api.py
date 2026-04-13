from ninja import Router, File, Form
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja_jwt.authentication import JWTAuth
from typing import List, Optional
from datetime import date
from dateutil.relativedelta import relativedelta
import hashlib
import logging
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)

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
    StatementCoverageOut,
)
from django.db.models import Q
from .models import FinancialInstitution, FinancialProduct, BankStatementImport, StagedTransaction
from .services import provision_financial_product, approve_staged_transaction
from .validators import validate_pdf_magic_bytes

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
        institution_id=payload.institution_id,
        product_type=payload.product_type,
        product_name=payload.product_name,
        owner=owner,
        account_number=payload.account_number,
    )
    
    return product

@router.post("/products/{product_id}/statements/batch-upload")
def batch_upload_statements(request, product_id: int, files: List[UploadedFile] = File(...)):
    """Stores multiple bank statements, skips duplicate files, and triggers Celery extraction for new ones."""
    from banking.tasks import extract_transactions_task

    user = request.auth
    product = get_object_or_404(FinancialProduct, id=product_id, family=user.family)

    results = {
        "uploaded": [],
        "skipped": [],
        "failed": []
    }

    validated_files = []
    for file in files:
        file_content = file.read()
        try:
            validate_pdf_magic_bytes(file_content)
        except ValueError as exc:
            raise HttpError(400, str(exc))
        file.seek(0)
        validated_files.append((file, file_content))

    for file, file_content in validated_files:
        try:
            file_hash = hashlib.sha256(file_content).hexdigest()
            file.seek(0)

            if BankStatementImport.objects.filter(file_hash=file_hash).exists():
                results["skipped"].append({"name": file.name, "reason": "Duplicate file."})
                continue

            statement = BankStatementImport.objects.create(
                financial_product=product,
                institution=product.institution,
                file=file,
                file_hash=file_hash,
                status=BankStatementImport.Status.STAGED,
                processed_by_ai=False,
                processed_by_python=False,
                processing_log=[],
            )

            # Queue extraction task
            extract_transactions_task.delay(statement.id, user.id)
            results["uploaded"].append({"name": file.name, "id": statement.id})

        except Exception as e:
            logger.exception(f"[BATCH] Failed to process {file.name}")
            results["failed"].append({"name": file.name, "reason": str(e)})

    return results


def _get_statement_for_family(import_id: int, family) -> BankStatementImport:
    """
    Fetch a BankStatementImport and assert family ownership.
    Handles both legacy (financial_product set) and multi-product (institution only) imports.
    Raises 404 on any ownership mismatch to avoid leaking resource existence.
    """
    from ninja.errors import HttpError
    statement = get_object_or_404(BankStatementImport, id=import_id)
    if statement.financial_product_id:
        if statement.financial_product.family_id != family.id:
            raise HttpError(404, "Not found.")
    elif statement.institution_id:
        if not FinancialProduct.objects.filter(
            institution_id=statement.institution_id, family=family
        ).exists():
            raise HttpError(404, "Not found.")
    else:
        raise HttpError(404, "Not found.")
    return statement


@router.post("/institutions/{institution_id}/statements/upload", response=StatementUploadOut)
def upload_consolidated_statement(
    request, institution_id: int, file: File[UploadedFile], document_date: Optional[date] = Form(None)
):
    """
    Upload a consolidated multi-product statement for an institution (e.g. Tangerine).
    The extraction pipeline will route each row to the correct FinancialProduct by
    account_number, auto-spawning new products as needed.
    """
    from banking.tasks import extract_transactions_task
    try:
        user = request.auth
        institution = get_object_or_404(FinancialInstitution, id=institution_id)

        # Guard: family must have at least one product registered under this institution.
        if not FinancialProduct.objects.filter(institution=institution, family=user.family).exists():
            raise HttpError(
                403,
                "No products are registered under this institution for your family. "
                "Register at least one product before uploading a consolidated statement."
            )

        file_content = file.read()
        validate_pdf_magic_bytes(file_content)
        file_hash = hashlib.sha256(file_content).hexdigest()
        file.seek(0)

        if BankStatementImport.objects.filter(file_hash=file_hash).exists():
            raise HttpError(409, "This specific PDF has already been uploaded to the system.")

        statement = BankStatementImport.objects.create(
            institution=institution,
            financial_product=None,
            file=file,
            file_hash=file_hash,
            document_date=document_date,
            status=BankStatementImport.Status.STAGED,
            processed_by_ai=False,
            processed_by_python=False,
            processing_log=[],
        )

        extract_transactions_task.delay(statement.id, user.id)
        return statement
    except HttpError:
        raise
    except ValueError as exc:
        raise HttpError(400, str(exc))
    except Exception:
        logger.exception(f"[UPLOAD] Unexpected error during consolidated upload for institution {institution_id}")
        raise HttpError(500, "Internal server error.")


@router.post("/products/{product_id}/statements/upload", response=StatementUploadOut)
def upload_statement(request, product_id: int, file: File[UploadedFile], document_date: Optional[date] = Form(None)):
    """Stores a bank statement, blocks duplicate files, and triggers Celery extraction pipeline."""
    from banking.tasks import extract_transactions_task

    try:
        user = request.auth
        product = get_object_or_404(FinancialProduct, id=product_id, family=user.family)

        file_content = file.read()
        validate_pdf_magic_bytes(file_content)
        file_hash = hashlib.sha256(file_content).hexdigest()
        file.seek(0)

        if BankStatementImport.objects.filter(file_hash=file_hash).exists():
            logger.warning(f"[UPLOAD] Duplicate upload: {file.name} (hash: {file_hash})")
            raise HttpError(409, "This specific PDF has already been uploaded to the system.")

        statement = BankStatementImport.objects.create(
            financial_product=product,
            institution=product.institution,
            file=file,
            file_hash=file_hash,
            document_date=document_date,
            status=BankStatementImport.Status.STAGED,
            processed_by_ai=False,
            processed_by_python=False,
            processing_log=[],
        )

        # Queue extraction task
        extract_transactions_task.delay(statement.id, user.id)

        return statement
    except HttpError:
        raise
    except ValueError as exc:
        raise HttpError(400, str(exc))
    except Exception:
        logger.exception(f"[UPLOAD] Unexpected error during upload of {file.name}")
        raise HttpError(500, "Internal server error.")


@router.get("/products/{product_id}/statements", response=List[StatementImportOut])
def list_product_statements(request, product_id: int):
    """Returns staged/imported statements for one product in newest-first order."""
    user = request.auth
    product = get_object_or_404(FinancialProduct, id=product_id, family=user.family)
    return BankStatementImport.objects.filter(financial_product=product).order_by("-upload_date")


@router.get("/statements/{import_id}", response=StatementImportOut)
def get_statement_import(request, import_id: int):
    """Returns a specific statement import."""
    user = request.auth
    return _get_statement_for_family(import_id, user.family)


@router.get("/statements/{import_id}/transactions", response=List[StagedTransactionOut])
def get_statement_import_transactions(request, import_id: int):
    """Returns all transactions for a specific statement import."""
    user = request.auth
    statement = _get_statement_for_family(import_id, user.family)
    return StagedTransaction.objects.filter(
        statement_import=statement
    ).select_related('predicted_account', 'journal_entry').prefetch_related('journal_entry__lines__account').order_by("bank_date")


@router.delete("/imports/{import_id}")
def delete_statement_import(request, import_id: int):
    """Deletes a statement import, its staged transactions, and its journal entries via CASCADE."""
    user = request.auth
    statement = _get_statement_for_family(import_id, user.family)
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


@router.get("/statement-coverage", response=StatementCoverageOut)
def get_statement_coverage(request):
    """
    Returns a month-by-month coverage grid grouped by Upload Target.

    A target is one of:
      INSTITUTION — an institution that has ≥1 consolidated (multi-product)
                    BankStatementImport (financial_product=None).
      PRODUCT     — a legacy FinancialProduct that has its own per-statement uploads.

    Both target types can coexist for the same institution (e.g. Desjardins has
    per-product legacy uploads; Tangerine has consolidated institution-level uploads).
    """
    user = request.auth
    family = user.family

    family_institution_ids = set(
        FinancialProduct.objects.filter(family=family).values_list('institution_id', flat=True)
    )
    if not family_institution_ids:
        return {"all_months": [], "targets": []}

    # Fetch all statements visible to this family:
    #   legacy path  → financial_product belongs to this family
    #   consolidated → financial_product is null, institution belongs to this family
    statements = (
        BankStatementImport.objects
        .filter(document_date__isnull=False)
        .filter(
            Q(financial_product__family=family) |
            Q(financial_product__isnull=True, institution_id__in=family_institution_ids)
        )
        .values('id', 'financial_product_id', 'institution_id', 'document_date', 'status')
    )

    institution_map: dict = {}   # institution_id → { "YYYY-MM": {statement_id, status} }
    product_map: dict = {}       # product_id     → { "YYYY-MM": {statement_id, status} }
    global_min_date: Optional[date] = None

    for s in statements:
        key = s['document_date'].strftime('%Y-%m')
        if global_min_date is None or s['document_date'] < global_min_date:
            global_min_date = s['document_date']

        if s['financial_product_id'] is None:
            iid = s['institution_id']
            if iid not in institution_map:
                institution_map[iid] = {}
            if key not in institution_map[iid]:
                institution_map[iid][key] = {'statement_id': s['id'], 'status': s['status']}
        else:
            pid = s['financial_product_id']
            if pid not in product_map:
                product_map[pid] = {}
            if key not in product_map[pid]:
                product_map[pid][key] = {'statement_id': s['id'], 'status': s['status']}

    if global_min_date is None:
        return {"all_months": [], "targets": []}

    today = date.today()
    current = global_min_date.replace(day=1)
    end = today.replace(day=1)
    all_months: List[str] = []
    while current <= end:
        all_months.append(current.strftime('%Y-%m'))
        current += relativedelta(months=1)

    def _build_cells(coverage: dict) -> list:
        months_present = sorted(coverage.keys())
        start = months_present[0] if months_present else None
        cells = []
        for m in all_months:
            if start is None or m < start:
                cells.append({'month': m, 'statement_id': None, 'status': 'before_start'})
            elif m in coverage:
                cells.append({'month': m, 'statement_id': coverage[m]['statement_id'], 'status': coverage[m]['status']})
            else:
                cells.append({'month': m, 'statement_id': None, 'status': 'missing'})
        return cells

    targets = []

    # --- Institution targets (consolidated) ---
    if institution_map:
        institutions = {
            inst.id: inst
            for inst in FinancialInstitution.objects.filter(id__in=institution_map.keys())
        }
        for iid, coverage in sorted(institution_map.items(), key=lambda x: institutions[x[0]].name):
            inst = institutions[iid]
            targets.append({
                'target_id': iid,
                'target_name': f"{inst.name} (Consolidé)",
                'target_type': 'INSTITUTION',
                'months': _build_cells(coverage),
            })

    # --- Product targets (legacy) ---
    products = (
        FinancialProduct.objects
        .filter(family=family)
        .select_related('institution', 'account')
        .order_by('institution__name', 'account__name')
    )
    for product in products:
        targets.append({
            'target_id': product.id,
            'target_name': product.account.name,
            'target_type': 'PRODUCT',
            'months': _build_cells(product_map.get(product.id, {})),
        })

    return {'all_months': all_months, 'targets': targets}


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
