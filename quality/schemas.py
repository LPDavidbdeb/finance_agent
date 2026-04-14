from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from ninja import Schema


class ConsistencyRunTriggerIn(Schema):
    statement_ids: Optional[list[int]] = None


class ConsistencyReportRunOut(Schema):
    id: int
    family_id: UUID
    trigger_source: str
    status: str
    scope: dict[str, Any]
    summary: dict[str, Any]
    error_message: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    finding_count: int


class ConsistencyReportFindingOut(Schema):
    id: int
    run_id: int
    severity: str
    category: str
    title: str
    message: str
    details: dict[str, Any]
    statement_import_id: Optional[int] = None
    staged_transaction_id: Optional[int] = None
    journal_entry_id: Optional[int] = None
    transaction_line_id: Optional[int] = None
    created_at: datetime


class ConsistencyRunTransactionOut(Schema):
    id: int
    statement_import_id: int
    statement_import_label: str
    financial_product_id: Optional[int] = None
    bank_date: date
    raw_description: str
    amount: str
    status: str
    predicted_account_id: Optional[int] = None
    journal_entry_id: Optional[int] = None
    cutoff_date: date
    days_past_cutoff: int


