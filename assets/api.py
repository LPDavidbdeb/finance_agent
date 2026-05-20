from ninja import Router, Schema
from ninja import errors
from django.shortcuts import get_object_or_404
from django.db import transaction
from decimal import Decimal
from typing import Optional, List

from accounting.models import Account
from .models import TangibleAsset

router = Router()


class ExpenseCategoryOut(Schema):
    id: int
    name: str
    statcan_vector_id: Optional[int] = None


@router.get("/expense-categories", response=List[ExpenseCategoryOut], auth=None)
def list_expense_categories(request):
    """
    Return all distinct EXPENSE accounts that have a StatCan vector ID.
    Used by the asset creation form to drive the inflation-assumption picker.
    auth=None — read-only reference data shared across families.
    """
    # Deduplicate by name — same category name exists per-family; pick the lowest id.
    seen: set[str] = set()
    result = []
    qs = (
        Account.objects
        .filter(account_type=Account.AccountType.EXPENSE)
        .exclude(statcan_vector_id__isnull=True)
        .order_by("name", "id")
    )
    for acct in qs:
        if acct.name not in seen:
            seen.add(acct.name)
            result.append(ExpenseCategoryOut(
                id=acct.id,
                name=acct.name,
                statcan_vector_id=acct.statcan_vector_id,
            ))
    return result


class CreateAssetIn(Schema):
    name: str
    purchase_value: Decimal
    current_market_value: Decimal
    purchase_date: Optional[str] = None
    account_id: Optional[int] = None
    account_name: Optional[str] = None


class CreateAssetOut(Schema):
    id: int
    name: str


@router.post("/", response=CreateAssetOut)
def create_asset(request, payload: CreateAssetIn):
    user = request.auth
    family = getattr(user, 'family', None)
    if not family:
        raise errors.HttpError(400, "User not associated with a family")

    with transaction.atomic():
        # Resolve or create an Account for this asset
        account = None
        if payload.account_id:
            account = get_object_or_404(Account, id=payload.account_id, family=family)
        elif payload.account_name:
            account = Account.objects.create(name=payload.account_name, account_type=Account.AccountType.ASSET, family=family)
        else:
            raise errors.HttpError(400, "Either account_id or account_name must be provided to create an asset")

        asset = TangibleAsset.objects.create(
            family=family,
            account=account,
            name=payload.name,
            purchase_value=payload.purchase_value,
            current_market_value=payload.current_market_value,
            purchase_date=payload.purchase_date or None,
        )

    return CreateAssetOut(id=asset.id, name=asset.name)
