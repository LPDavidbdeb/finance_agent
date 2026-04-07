from decimal import Decimal
from datetime import date
from django.db import transaction
from django.core.exceptions import ValidationError

from accounting.models import Account, JournalEntry, TransactionLine
from planning.models import AnnuitySchedule
from planning.services import AnnuityService
from planning.schemas import ScenarioSpec, ScenarioType, PaymentFrequencyIn
from .models import TangibleAsset

class OriginationService:
    @staticmethod
    @transaction.atomic
    def acquire_financed_asset(
        name: str,
        family,
        total_cost: Decimal,
        down_payment: Decimal,
        financed_amount: Decimal,
        origination_date: date,
        loan_term_years: int,
        annual_rate: Decimal,
        cash_account: Account,
        liability_account: Account,
        owner=None,
        payment_frequency: PaymentFrequencyIn = PaymentFrequencyIn.MONTHLY
    ) -> TangibleAsset:
        """
        Orchestrates the acquisition of a physical asset through debt financing.
        1. Creates a dedicated ASSET account for the physical object.
        2. Generates a balanced, 3-line JournalEntry (Asset / Cash / Liability).
        3. Creates the TangibleAsset record linked to the account.
        4. Initializes the AnnuitySchedule for the debt.
        """
        
        # 1. Validation: ensure the math balances
        if total_cost != (down_payment + financed_amount):
            raise ValidationError(
                f"Accounting mismatch: Total cost ({total_cost}) must equal "
                f"down payment ({down_payment}) + financed amount ({financed_amount})."
            )

        # 2. Create the dedicated Asset Account
        # Usually, a tangible asset like a house or car has its own sub-account in the ledger.
        # We'll try to find a suitable parent (e.g. "Tangible Assets" or "Fixed Assets") 
        # but for now we'll just create it as a top-level Asset for this family.
        asset_account = Account.objects.create(
            name=f"Asset: {name}",
            account_type=Account.AccountType.ASSET,
            family=family
        )

        # 3. Construct the perfectly balanced JournalEntry
        journal_entry = JournalEntry.objects.create(
            family=family,
            date=origination_date,
            description=f"Acquisition of {name}",
            is_reconciled=True
        )

        # Line 1: Debit the new Asset account (Increase Asset)
        TransactionLine.objects.create(
            journal_entry=journal_entry,
            account=asset_account,
            amount=total_cost  # Debit is positive
        )

        # Line 2: Credit the Cash/Bank account (Decrease Asset)
        if down_payment > 0:
            TransactionLine.objects.create(
                journal_entry=journal_entry,
                account=cash_account,
                amount=-down_payment  # Credit is negative
            )

        # Line 3: Credit the Liability account (Increase Liability)
        if financed_amount > 0:
            TransactionLine.objects.create(
                journal_entry=journal_entry,
                account=liability_account,
                amount=-financed_amount  # Credit is negative
            )

        # 4. Instantiate the TangibleAsset
        asset = TangibleAsset.objects.create(
            family=family,
            member=owner,
            account=asset_account,
            name=name,
            purchase_value=total_cost,
            current_market_value=total_cost,
            purchase_date=origination_date
        )

        # 5. Initialize the AnnuitySchedule if financing exists
        if financed_amount > 0:
            spec = ScenarioSpec(
                name=f"Financing: {name}",
                type=ScenarioType.LOAN_AMORTIZATION,
                principal=financed_amount,
                annual_rate=annual_rate,
                amortization_years=loan_term_years,
                payment_frequency=payment_frequency,
                start_date=origination_date
            )
            
            schedule = AnnuityService.commit_schedule(
                family=family,
                spec=spec,
                linked_je=journal_entry
            )
            
            # Link the schedule back to the tangible asset
            asset.annuity_schedule = schedule
            asset.save(update_fields=['annuity_schedule'])

        return asset
