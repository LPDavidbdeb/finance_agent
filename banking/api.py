from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth
from typing import List, Optional
from django.shortcuts import get_object_or_404
from django.db.models import ProtectedError
from users.models import FamilyMember

from .schemas import FinancialProductIn, FinancialProductOut, InstitutionOut, InstitutionIn
from .models import FinancialInstitution, FinancialProduct
from .services import provision_financial_product

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
    queryset = FinancialProduct.objects.filter(family=user.family)
    
    if owner_id:
        queryset = queryset.filter(owner_id=owner_id)
        
    return queryset

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