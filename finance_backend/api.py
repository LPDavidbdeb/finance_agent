from ninja import NinjaAPI, Router, errors
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_jwt.routers.obtain import obtain_pair_router
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from decimal import Decimal
from typing import List

from .schemas import AccountSchema, AccountMoveIn, StagedTransactionSchema, JournalEntryIn, JournalEntryOut
from accounting.models import Account, JournalEntry, TransactionLine
from banking.models import StagedTransaction

api = NinjaAPI(title="Finance Headless API")

api.add_router("/auth/", obtain_pair_router)
api.add_router("/users/", "users.api.router")
api.add_router("/banking/", "banking.api.router")

@api.get("/accounts/tree", response=List[AccountSchema])
def get_account_tree(request):
    """
    Returns the MPTT nested set tree.
    """
    roots = Account.objects.root_nodes().prefetch_related('children')
    return list(roots)

@api.delete("/accounts/{account_id}")
def delete_account(request, account_id: int):
    account = Account.objects.get(id=account_id)
    account.delete()
    return {"message": "Account deleted successfully."}

@api.patch("/accounts/{account_id}/move")
def move_account(request, account_id: int, payload: AccountMoveIn):
    account = Account.objects.get(id=account_id)
    target_parent = Account.objects.get(id=payload.target_parent_id)
    account.parent = target_parent
    account.save()
    return {"message": "Account moved successfully."}

@api.get("/banking/staged", response=List[StagedTransactionSchema])
def get_staged_transactions(request):
    """
    Fetch all StagedTransactions requiring human review.
    """
    return StagedTransaction.objects.filter(status=StagedTransaction.Status.PENDING_REVIEW)

@api.post("/accounting/journal-entry", response=JournalEntryOut)
def create_journal_entry(request, payload: JournalEntryIn):
    """
    Creates a JournalEntry and its associated TransactionLines.
    Validates that the Double-Entry Accounting equation balances (Debits == Credits).
    """
    total_balance = sum(line.amount for line in payload.lines)
    if total_balance != Decimal('0.00'):
        raise errors.HttpError(400, f"Transaction lines must sum to zero. Current sum: {total_balance}")

    with transaction.atomic():
        # TODO: Link to actual request.user.family when auth is fully integrated
        from users.models import Family
        family = Family.objects.first()
        if not family:
            raise errors.HttpError(400, "No Family tenant exists in the database. Please create one.")

        entry = JournalEntry.objects.create(
            family=family,
            date=payload.date,
            description=payload.description
        )

        for line_data in payload.lines:
            try:
                account = Account.objects.get(id=line_data.account_id)
            except ObjectDoesNotExist:
                raise errors.HttpError(404, f"Account with ID {line_data.account_id} not found.")

            TransactionLine.objects.create(
                journal_entry=entry,
                account=account,
                amount=line_data.amount
            )

    return entry
