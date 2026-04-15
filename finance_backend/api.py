from ninja import NinjaAPI, errors
from ninja_jwt.routers.obtain import obtain_pair_router
from ninja_jwt.authentication import JWTAuth
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from decimal import Decimal
from typing import List

from .schemas import AccountSchema, AccountMoveIn, StagedTransactionSchema, JournalEntryIn, JournalEntryOut
from accounting.models import Account, JournalEntry, TransactionLine
from banking.models import StagedTransaction

api = NinjaAPI(
    title="Finance Headless API",
    auth=JWTAuth(),
    docs_url="/docs" if settings.DEBUG else None,
    urls_namespace="finance_api",
)

api.add_router("/auth/", obtain_pair_router, auth=None)
api.add_router("/users/", "users.api.router")
api.add_router("/banking/", "banking.api.router")
api.add_router("/categorization/", "categorization.api.router")
api.add_router("/accounting/", "accounting.api.router")
api.add_router("/analysis/", "accounting.analysis.api.router")
api.add_router("/maintenance/", "finance_backend.maintenance_api.router")
api.add_router("/planning/", "planning.api.router")
api.add_router("/quality/", "quality.api.router")

@api.get("/accounts/tree", response=List[AccountSchema])
def get_account_tree(request):
    """
    Returns the MPTT nested set tree filtered by the user's family.
    """
    user = request.auth
    # root_nodes() is a manager method, so we filter afterwards or use parent=None
    roots = Account.objects.filter(family=user.family, parent=None).prefetch_related('children')
    return list(roots)

@api.delete("/accounts/{account_id}")
def delete_account(request, account_id: int):
    user = request.auth
    account = get_object_or_404(Account, id=account_id, family=user.family)
    account.delete()
    return {"message": "Account deleted successfully."}

@api.patch("/accounts/{account_id}/move")
def move_account(request, account_id: int, payload: AccountMoveIn):
    user = request.auth
    account = get_object_or_404(Account, id=account_id, family=user.family)
    target_parent = get_object_or_404(Account, id=payload.target_parent_id, family=user.family)
    account.parent = target_parent
    account.save()
    return {"message": "Account moved successfully."}

@api.get("/banking/staged", response=List[StagedTransactionSchema])
def get_staged_transactions(request):
    """
    Fetch all StagedTransactions requiring human review for the user's family.
    """
    user = request.auth
    return StagedTransaction.objects.filter(
        statement_import__financial_product__family=user.family,
        status=StagedTransaction.Status.PENDING_REVIEW
    )

@api.post("/accounting/journal-entry", response=JournalEntryOut)
def create_journal_entry(request, payload: JournalEntryIn):
    """
    Creates a JournalEntry and its associated TransactionLines.
    Validates that the Double-Entry Accounting equation balances (Debits == Credits).
    """
    user = request.auth
    total_balance = sum(line.amount for line in payload.lines)
    if total_balance != Decimal('0.00'):
        raise errors.HttpError(400, f"Transaction lines must sum to zero. Current sum: {total_balance}")

    with transaction.atomic():
        family = user.family
        if not family:
            raise errors.HttpError(400, "User is not associated with a family.")

        entry = JournalEntry.objects.create(
            family=family,
            date=payload.date,
            description=payload.description
        )

        for line_data in payload.lines:
            try:
                # Ensure the account belongs to the family
                account = Account.objects.get(id=line_data.account_id, family=family)
            except ObjectDoesNotExist:
                raise errors.HttpError(404, f"Account with ID {line_data.account_id} not found in your family.")

            TransactionLine.objects.create(
                journal_entry=entry,
                account=account,
                amount=line_data.amount
            )

    return entry