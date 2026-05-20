from ninja import Router, Schema
from ninja.errors import HttpError
from django.shortcuts import get_object_or_404
from typing import List, Optional
from decimal import Decimal
from datetime import date

from .models import SinkingFundProject, SinkingFundLineItem
from accounting.models import Account
from assets.models import TangibleAsset

router = Router(tags=["Projects"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class LineItemIn(Schema):
    description: str
    today_price: Decimal
    quantity: Decimal = Decimal('1')
    expense_category_id: Optional[int] = None
    inflation_rate_override: Optional[Decimal] = None
    source_asset_id: Optional[int] = None


class LineItemOut(Schema):
    id: int
    description: str
    today_price: Decimal
    quantity: Decimal
    total_today_price: Decimal
    expense_category_id: Optional[int] = None
    expense_category_name: Optional[str] = None
    statcan_vector_id: Optional[int] = None
    inflation_rate_override: Optional[Decimal] = None
    source_asset_id: Optional[int] = None
    source_asset_name: Optional[str] = None


class ProjectIn(Schema):
    name: str
    target_date: date
    savings_start_date: Optional[date] = None
    notes: str = ''


class ProjectOut(Schema):
    id: int
    name: str
    target_date: date
    savings_start_date: Optional[date] = None
    notes: str
    line_items: List[LineItemOut]
    created_at: str


class ProjectListOut(Schema):
    id: int
    name: str
    target_date: date
    savings_start_date: Optional[date] = None
    line_item_count: int
    created_at: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _line_item_out(item: SinkingFundLineItem) -> LineItemOut:
    cat = item.expense_category
    asset = item.source_asset
    return LineItemOut(
        id=item.id,
        description=item.description,
        today_price=item.today_price,
        quantity=item.quantity,
        total_today_price=item.total_today_price,
        expense_category_id=cat.id if cat else None,
        expense_category_name=cat.name if cat else None,
        statcan_vector_id=cat.statcan_vector_id if cat else None,
        inflation_rate_override=item.inflation_rate_override,
        source_asset_id=asset.id if asset else None,
        source_asset_name=asset.name if asset else None,
    )


def _project_out(project: SinkingFundProject) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        target_date=project.target_date,
        savings_start_date=project.savings_start_date,
        notes=project.notes,
        line_items=[
            _line_item_out(item)
            for item in project.line_items.select_related('expense_category', 'source_asset').all()
        ],
        created_at=project.created_at.isoformat(),
    )


# ── Project CRUD ──────────────────────────────────────────────────────────────

@router.get("/", response=List[ProjectListOut])
def list_projects(request):
    qs = SinkingFundProject.objects.filter(
        family=request.auth.family
    ).prefetch_related('line_items')
    return [
        ProjectListOut(
            id=p.id,
            name=p.name,
            target_date=p.target_date,
            savings_start_date=p.savings_start_date,
            line_item_count=p.line_items.count(),
            created_at=p.created_at.isoformat(),
        )
        for p in qs
    ]


@router.post("/", response=ProjectOut)
def create_project(request, payload: ProjectIn):
    project = SinkingFundProject.objects.create(
        family=request.auth.family,
        name=payload.name,
        target_date=payload.target_date,
        savings_start_date=payload.savings_start_date,
        notes=payload.notes,
    )
    return _project_out(project)


@router.get("/{project_id}", response=ProjectOut)
def get_project(request, project_id: int):
    project = get_object_or_404(
        SinkingFundProject, id=project_id, family=request.auth.family
    )
    return _project_out(project)


@router.patch("/{project_id}", response=ProjectOut)
def update_project(request, project_id: int, payload: ProjectIn):
    project = get_object_or_404(
        SinkingFundProject, id=project_id, family=request.auth.family
    )
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(project, field, value)
    project.save()
    return _project_out(project)


@router.delete("/{project_id}")
def delete_project(request, project_id: int):
    project = get_object_or_404(
        SinkingFundProject, id=project_id, family=request.auth.family
    )
    project.delete()
    return {"message": "Project deleted."}


# ── Line Item CRUD ────────────────────────────────────────────────────────────

@router.post("/{project_id}/line-items", response=ProjectOut)
def add_line_item(request, project_id: int, payload: LineItemIn):
    project = get_object_or_404(
        SinkingFundProject, id=project_id, family=request.auth.family
    )
    family = request.auth.family

    category = None
    if payload.expense_category_id:
        category = get_object_or_404(
            Account, id=payload.expense_category_id,
            account_type=Account.AccountType.EXPENSE
        )

    asset = None
    if payload.source_asset_id:
        asset = get_object_or_404(TangibleAsset, id=payload.source_asset_id, family=family)

    SinkingFundLineItem.objects.create(
        project=project,
        description=payload.description,
        today_price=payload.today_price,
        quantity=payload.quantity,
        expense_category=category,
        inflation_rate_override=payload.inflation_rate_override,
        source_asset=asset,
    )
    return _project_out(project)


@router.patch("/{project_id}/line-items/{item_id}", response=ProjectOut)
def update_line_item(request, project_id: int, item_id: int, payload: LineItemIn):
    project = get_object_or_404(
        SinkingFundProject, id=project_id, family=request.auth.family
    )
    item = get_object_or_404(SinkingFundLineItem, id=item_id, project=project)
    family = request.auth.family

    item.description = payload.description
    item.today_price = payload.today_price
    item.quantity = payload.quantity
    item.inflation_rate_override = payload.inflation_rate_override

    item.expense_category = (
        get_object_or_404(Account, id=payload.expense_category_id,
                          account_type=Account.AccountType.EXPENSE)
        if payload.expense_category_id else None
    )
    item.source_asset = (
        get_object_or_404(TangibleAsset, id=payload.source_asset_id, family=family)
        if payload.source_asset_id else None
    )
    item.save()
    return _project_out(project)


@router.delete("/{project_id}/line-items/{item_id}", response=ProjectOut)
def delete_line_item(request, project_id: int, item_id: int):
    project = get_object_or_404(
        SinkingFundProject, id=project_id, family=request.auth.family
    )
    item = get_object_or_404(SinkingFundLineItem, id=item_id, project=project)
    item.delete()
    return _project_out(project)
