from ninja import Schema, ModelSchema
from typing import List, Optional
from datetime import date
from decimal import Decimal
from accounting.models import Account, JournalEntry, TransactionLine
from banking.models import StagedTransaction

# ----- Account Tree Schemas -----

class AccountSchema(ModelSchema):
    children: List['AccountSchema'] = []

    class Meta:
        model = Account
        fields = ['id', 'name', 'account_type', 'parent']

AccountSchema.model_rebuild()

class AccountMoveIn(Schema):
    target_parent_id: int

# ----- Staged Transaction Schemas -----

class StagedTransactionSchema(ModelSchema):
    class Meta:
        model = StagedTransaction
        fields = ['id', 'bank_date', 'raw_description', 'amount', 'unique_bank_id', 'status']

# ----- Journal Entry Schemas -----

class TransactionLineIn(Schema):
    account_id: int
    amount: Decimal

class JournalEntryIn(Schema):
    date: date
    description: str
    lines: List[TransactionLineIn]

class JournalEntryOut(ModelSchema):
    class Meta:
        model = JournalEntry
        fields = ['id', 'date', 'description', 'is_reconciled']
