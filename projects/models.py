from django.db import models
from decimal import Decimal


class SinkingFundProject(models.Model):
    family = models.ForeignKey(
        'users.Family', on_delete=models.CASCADE, related_name='sinking_fund_projects'
    )
    name = models.CharField(max_length=255)
    target_date = models.DateField(
        help_text="Date by which the full amount must be available."
    )
    savings_start_date = models.DateField(
        null=True, blank=True,
        help_text="When contributions began (or are planned to begin). Defaults to today when blank."
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['target_date']

    def __str__(self):
        return f"{self.name} ({self.family.name})"


class SinkingFundLineItem(models.Model):
    project = models.ForeignKey(
        SinkingFundProject, on_delete=models.CASCADE, related_name='line_items'
    )
    description = models.CharField(max_length=255)
    today_price = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text="Current estimated cost per unit in today's dollars."
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1'))
    expense_category = models.ForeignKey(
        'accounting.Account',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sinking_fund_line_items',
        help_text="Expense account whose StatCan CPI vector drives the inflation assumption."
    )
    inflation_rate_override = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Manual annual inflation % override. Used when no expense_category is set."
    )
    source_asset = models.ForeignKey(
        'assets.TangibleAsset',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='absorbed_by_line_items',
        help_text="Existing asset whose accumulated sinking fund is credited against this line item's target."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.description} (×{self.quantity}) — {self.project.name}"

    @property
    def total_today_price(self) -> Decimal:
        return self.today_price * self.quantity
