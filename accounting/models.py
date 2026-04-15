from django.db import models
from decimal import Decimal
from mptt.models import MPTTModel, TreeForeignKey
from users.models import Family


class Account(MPTTModel):
    class AccountType(models.TextChoices):
        ASSET = 'ASSET', 'Asset'
        LIABILITY = 'LIABILITY', 'Liability'
        EQUITY = 'EQUITY', 'Equity'
        REVENUE = 'REVENUE', 'Revenue'
        EXPENSE = 'EXPENSE', 'Expense'

    name = models.CharField(max_length=255)
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices
    )
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='accounts',
        help_text="If null, this is a system-wide standard account."
    )
    global_reference = TreeForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='cloned_accounts', 
        help_text="Link to the global StatCan master template"
    )

    class MPTTMeta:
        order_insertion_by = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

class JournalEntry(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='journal_entries')
    date = models.DateField()
    description = models.CharField(max_length=512)
    is_reconciled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.date} - {self.description}"

class TransactionLine(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transaction_lines')
    amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Positive for Debit, Negative for Credit (or vice-versa depending on standard)")

    def __str__(self):
        return f"{self.account.name}: {self.amount}"


# =========================================================================
# LAYER 3: Insight Fact Store (Append-Only Versioned Log)
# =========================================================================

class AnalysisRun(models.Model):
    """
    Cohesive execution record for one analytics pipeline run.

    This model groups InsightFact rows that were computed together so the system
    can answer "what did we believe at run X" deterministically.
    """

    class Status(models.TextChoices):
        RUNNING = 'RUNNING', 'Running'
        SUCCEEDED = 'SUCCEEDED', 'Succeeded'
        FAILED = 'FAILED', 'Failed'

    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        related_name='analysis_runs',
        help_text="Tenant boundary for this analytical run"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    version = models.CharField(max_length=32, default='v1')
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    source_refreshed_at = models.DateTimeField(null=True, blank=True)
    insights_created = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['family', '-started_at']),
            models.Index(fields=['status', '-started_at']),
        ]

    def __str__(self):
        return f"Run {self.id} ({self.status}) - {self.family.name}"

class InsightFact(models.Model):
    """
    OLAP Layer 3: Versioned append-only log of computed insights for auditability and historicity.

    Each row is a snapshot of a category's insight metrics at a point in time.
    Never updated after creation; new insights are appended for versioning.

    Used for:
    - Audit trail of what insights were computed when
    - Time-series tracking of how insight scores evolve
    - Debugging and reproducibility of analytical decisions
    """

    category = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='insight_facts',
        help_text="The spending category this insight describes"
    )
    analysis_run = models.ForeignKey(
        AnalysisRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='insight_facts',
        help_text="Pipeline execution that produced this insight"
    )
    computed_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when this insight was computed (append-only)"
    )

    # Core Insight Metrics
    insight_score = models.FloatField(
        help_text="Materiality-weighted severity score (base_severity × materiality_multiplier)"
    )
    materiality_pct = models.FloatField(
        help_text="Percentage of total household spend (0-100)"
    )
    process_type = models.CharField(
        max_length=20,
        choices=[
            ('DETERMINISTIC', 'Deterministic'),
            ('STOCHASTIC', 'Stochastic'),
            ('EPISODIC', 'Episodic'),
        ],
        help_text="Classification of the underlying process"
    )

    # Trend Analysis Metrics
    slope = models.FloatField(
        null=True,
        blank=True,
        help_text="Log-linear regression slope (EPIC 2.1)"
    )
    has_structural_break = models.BooleanField(
        default=False,
        help_text="Whether a structural break was detected (EPIC 2.2)"
    )

    # Causal Decomposition Metrics
    causal_volume_pct = models.FloatField(
        null=True,
        blank=True,
        help_text="Volume effect % change (EPIC 3)"
    )
    causal_price_pct = models.FloatField(
        null=True,
        blank=True,
        help_text="Price effect % change (EPIC 3)"
    )

    # Projection Metrics
    projected_value = models.FloatField(
        null=True,
        blank=True,
        help_text="12-month projected spend (EPIC 4.1)"
    )
    projected_lower_bound = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Lower bound of the 95% prediction interval (Confidence Corridor)"
    )
    projected_upper_bound = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Upper bound of the 95% prediction interval (Confidence Corridor)"
    )

    # Natural Language Summary
    expert_summary = models.TextField(
        help_text="Expert-grade natural language summary of the insight (EPIC 4.2)"
    )

    # External Normalization (EPIC 3.2)
    benchmark_slope = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="The external baseline slope (e.g., CPI) used for comparison"
    )
    benchmark_classification = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('REAL_GROWTH', 'Real Growth'),
            ('INFLATION_TRACKED', 'Inflation Tracked'),
            ('EFFICIENCY_GAIN', 'Efficiency Gain'),
        ],
        help_text="Classification: REAL_GROWTH, INFLATION_TRACKED, or EFFICIENCY_GAIN"
    )

    class Meta:
        ordering = ['-computed_at']
        indexes = [
            models.Index(fields=['category', '-computed_at']),
            models.Index(fields=['computed_at']),
        ]
        verbose_name = "Insight Fact"
        verbose_name_plural = "Insight Facts"

    def __str__(self):
        return f"{self.category.name} @ {self.computed_at.isoformat()} (score: {self.insight_score:.0f})"


# =========================================================================
# LAYER 1: Materialized View for Monthly Statistics (Unmanaged)
# =========================================================================

class CategoryMonthlyStat(models.Model):
    """
    OLAP Layer 1: Unmanaged model representing a PostgreSQL Materialized View.

    This view pre-aggregates validated transactions by Category and Month for fast
    analysis pipeline execution. The view is built from verified journal entries.

    Materialization strategy:
    - Aggregated once per day (or on-demand)
    - Indexed for rapid time-series queries
    - Supports rolling window analysis (last 12, 24, 36 months)
    - Read-only from application perspective

    SQL materialized view name: accounting_categorymonthlystat
    """

    # Composite key components (used for grouping in the view)
    id = models.BigAutoField(primary_key=True)
    category_id = models.IntegerField(
        db_index=True,
        help_text="Foreign key to Account (category)"
    )

    # Time dimension
    month = models.DateField(
        db_index=True,
        help_text="First day of the month (DATE_TRUNC('month', date))"
    )

    # Aggregated metrics
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Sum of all transaction amounts for the category in the month"
    )
    transaction_count = models.IntegerField(
        default=0,
        help_text="Count of transactions for the category in the month"
    )
    avg_ticket = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Average transaction amount (total_amount / transaction_count)"
    )

    class Meta:
        managed = False  # This table is managed by raw SQL migration
        db_table = 'accounting_categorymonthlystat'
        verbose_name = "Category Monthly Stat"
        verbose_name_plural = "Category Monthly Stats"
        indexes = [
            models.Index(fields=['category_id', 'month']),
            models.Index(fields=['month']),
        ]

    def __str__(self):
        return f"Category {self.category_id} - {self.month.strftime('%Y-%m')} ({self.transaction_count} txns, ${self.total_amount})"


