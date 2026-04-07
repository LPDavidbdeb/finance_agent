from decimal import Decimal
from django.db import transaction, models
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
def provision_financial_product(family: Family, institution_id: int, product_type: str, product_name: str, owner: FamilyMember = None, account_number: str = None) -> FinancialProduct:
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

def _resolve_entry_accounts(source_account: Account, target_account: Account, amount: Decimal):
    """Resolve debit and credit accounts from staged cash-flow semantics.

    amount is cash-flow based: negative=outflow, positive=inflow.
    TransactionLine invariant remains: debit is positive, credit is negative.
    """
    if amount == 0:
        raise ValueError("Cannot approve a zero-amount transaction.")

    source_type = source_account.account_type
    target_type = target_account.account_type

    # --- Routing Logic ---

    # Case 1: Transfer between balance sheet accounts (Asset/Liability/Equity)
    if target_type in {Account.AccountType.ASSET, Account.AccountType.LIABILITY, Account.AccountType.EQUITY}:
        # Logic: We determine which account is receiving value (Debit) vs giving value (Credit)
        
        if source_type == Account.AccountType.LIABILITY:
            # Liability Source (Convention: Purchase=+, Payment=-)
            if amount > 0: # Purchase/Transfer-Out (Increase Debt)
                return target_account, source_account
            return source_account, target_account # Payment/Transfer-In (Decrease Debt)
        else:
            # Asset Source (Convention: Inflow=+, Outflow=-)
            if amount < 0: # Outflow (Transfer to somewhere else)
                return target_account, source_account
            return source_account, target_account # Inflow (Transfer from somewhere else)

    # Case 2: P&L - Expenses
    if target_type == Account.AccountType.EXPENSE:
        if source_type == Account.AccountType.LIABILITY:
            # Purchase (+): Debit Expense, Credit Liability
            # Refund (-): Debit Liability, Credit Expense
            if amount > 0:
                return target_account, source_account
            return source_account, target_account
        else:
            # Asset Source (Debit Card):
            # Purchase (-): Debit Expense, Credit Asset
            # Refund (+): Debit Asset, Credit Expense
            if amount < 0:
                return target_account, source_account
            return source_account, target_account

    # Case 3: P&L - Revenue
    if target_type == Account.AccountType.REVENUE:
        if source_type == Account.AccountType.LIABILITY:
            # Inflow (- on CC? rare): Credit Revenue, Debit Liability
            if amount < 0:
                return source_account, target_account
            return target_account, source_account
        else:
            # Asset Source: Inflow (+) -> Debit Asset, Credit Revenue
            if amount > 0:
                return source_account, target_account
            return target_account, source_account

    raise ValueError(f"Unsupported target account type: {target_type}")


@transaction.atomic
def approve_staged_transaction(transaction_id: int, target_account_id: int, user):
    """
    Approves a staged transaction by creating a double-entry Journal Entry
    and updating the staged transaction status.
    """
    try:
        staged_tx = StagedTransaction.objects.select_for_update(of=('self',)).select_related(
            'financial_product__family',
            'financial_product__account',
            'statement_import__financial_product__family',
            'statement_import__financial_product__account',
        ).get(id=transaction_id)
    except StagedTransaction.DoesNotExist:
        raise ValueError("Staged Transaction not found.")

    # Per-row product (set by Phase 3 routing) takes precedence over the legacy
    # statement-level product.  One of these must be set.
    resolved_product = staged_tx.financial_product or staged_tx.statement_import.financial_product
    if not resolved_product:
        raise ValueError(
            f"StagedTransaction {transaction_id} has no associated FinancialProduct. "
            "Cannot resolve source account or family."
        )

    family = resolved_product.family
    if user.family != family:
        raise PermissionError("User does not have access to this transaction's family.")

    if staged_tx.status != StagedTransaction.Status.UNPROCESSED:
        raise ValueError(f"Transaction is already processed (Status: {staged_tx.status}).")

    # --- Phase 4: Smart Categorization Interception ---
    # If the transaction matches a rule with a linked schedule, we use the 
    # compound entry logic (AmortizationReconciliationService).
    from categorization.services import find_matching_rule
    from planning.services import AmortizationReconciliationService
    
    rule = find_matching_rule(
        staged_tx.raw_description,
        resolved_product.institution_id,
        family.id,
        transaction_amount=staged_tx.amount
    )
    
    if rule and rule.linked_schedule:
        je = AmortizationReconciliationService.reconcile_amortization_payment(staged_tx, rule, user)
        if je:
            return je

    source_account = resolved_product.account
    try:
        # Allow accounts that belong to the family OR are global (None)
        target_account = Account.objects.get(
            models.Q(family=family) | models.Q(family__isnull=True),
            id=target_account_id
        )
    except Account.DoesNotExist:
        raise ValueError("Target account not found or access denied.")

    journal_entry = JournalEntry.objects.create(
        family=family,
        date=staged_tx.bank_date,
        description=staged_tx.merchant.name if staged_tx.merchant else staged_tx.raw_description,
        is_reconciled=True
    )

    amount = staged_tx.amount
    debit_account, credit_account = _resolve_entry_accounts(source_account, target_account, amount)

    # Guarantee balanced entry by construction: +abs(amount) and -abs(amount).
    line_amount = abs(amount)

    TransactionLine.objects.create(
        journal_entry=journal_entry,
        account=debit_account,
        amount=line_amount
    )

    TransactionLine.objects.create(
        journal_entry=journal_entry,
        account=credit_account,
        amount=-line_amount
    )

    staged_tx.status = StagedTransaction.Status.RECONCILED
    staged_tx.journal_entry = journal_entry
    staged_tx.save()

    return journal_entry
