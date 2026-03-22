from django.db import transaction
from .models import FinancialProduct, FinancialInstitution, BankStatementImport, StagedTransaction
from accounting.models import Account, JournalEntry, TransactionLine
from users.models import Family, FamilyMember
import logging

logger = logging.getLogger(__name__)

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
    parent_account, _ = Account.objects.get_or_create(
        name=routing["parent_name"],
        account_type=routing["account_type"],
        family=None
    )

    # 2. Create the Ledger Anchor Account
    full_account_name = f"{institution.name} {product_name}"
    
    account = Account.objects.create(
        name=full_account_name,
        account_type=routing["account_type"],
        parent=parent_account,
        family=family
    )
    
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

@transaction.atomic
def approve_staged_transaction(transaction_id: int, target_account_id: int, user):
    """
    Approves a staged transaction by creating a double-entry Journal Entry
    and updating the staged transaction status.
    """
    try:
        staged_tx = StagedTransaction.objects.select_related(
            'statement_import__financial_product__family',
            'statement_import__financial_product__account'
        ).get(id=transaction_id)
    except StagedTransaction.DoesNotExist:
        raise ValueError("Staged Transaction not found.")

    family = staged_tx.statement_import.financial_product.family
    if user.family != family:
        raise PermissionError("User does not have access to this transaction's family.")

    if staged_tx.status != StagedTransaction.Status.UNPROCESSED:
        raise ValueError(f"Transaction is already processed (Status: {staged_tx.status}).")

    source_account = staged_tx.statement_import.financial_product.account
    try:
        target_account = Account.objects.get(id=target_account_id, family=family)
    except Account.DoesNotExist:
        raise ValueError("Target account not found for this family.")

    journal_entry = JournalEntry.objects.create(
        family=family,
        date=staged_tx.bank_date,
        description=staged_tx.merchant.name if staged_tx.merchant else staged_tx.raw_description,
        is_reconciled=True
    )

    amount = staged_tx.amount
    
    if source_account.account_type == Account.AccountType.LIABILITY:
        # Credit card purchases are usually imported as positive. 
        # A purchase INCREASES liability (Credit) and INCREASES expense (Debit).
        if amount > 0:
            debit_account, credit_account = target_account, source_account
        else: # A payment to the credit card or a refund
            debit_account, credit_account = source_account, target_account
    else:
        # Asset accounts (Checking/Savings)
        # Deposits are positive, Expenses are negative
        if amount > 0:
            debit_account, credit_account = source_account, target_account
        else:
            debit_account, credit_account = target_account, source_account

    TransactionLine.objects.create(
        journal_entry=journal_entry,
        account=debit_account,
        amount=abs(amount)
    )
    
    TransactionLine.objects.create(
        journal_entry=journal_entry,
        account=credit_account,
        amount=-abs(amount)
    )

    staged_tx.status = StagedTransaction.Status.RECONCILED
    staged_tx.journal_entry = journal_entry
    staged_tx.save()

    return journal_entry
