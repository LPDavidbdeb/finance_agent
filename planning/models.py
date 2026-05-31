from django.db import models
from decimal import Decimal


class AnnuitySchedule(models.Model):

    class ScheduleType(models.TextChoices):
        LOAN_AMORTIZATION = 'LOAN_AMORTIZATION', 'Loan / Mortgage'
        SINKING_FUND = 'SINKING_FUND', 'Sinking Fund'

    class Frequency(models.TextChoices):
        MONTHLY = 'MONTHLY', 'Monthly'
        BIWEEKLY = 'BIWEEKLY', 'Bi-weekly'
        WEEKLY = 'WEEKLY', 'Weekly'
        ANNUALLY = 'ANNUALLY', 'Annually'

    family = models.ForeignKey(
        'users.Family', on_delete=models.CASCADE, related_name='annuity_schedules'
    )
    name = models.CharField(max_length=255)
    schedule_type = models.CharField(max_length=30, choices=ScheduleType.choices)

    # Financial parameters
    principal_amount = models.DecimalField(max_digits=14, decimal_places=2)
    annual_rate = models.DecimalField(max_digits=7, decimal_places=4)   # e.g. 4.5000
    n_periods = models.IntegerField()
    payment_frequency = models.CharField(max_length=20, choices=Frequency.choices)

    # The origination date — payment schedule flows from this
    start_date = models.DateField()

    # Computed at commit time, stored for fast reads
    computed_payment = models.DecimalField(max_digits=14, decimal_places=2)

    # Optionally linked to the originating lump-sum journal entry
    linked_journal_entry = models.ForeignKey(
        'accounting.JournalEntry',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='annuity_schedule',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    financing_contract = models.FileField(
        upload_to='contracts/financing/',
        null=True,
        blank=True,
        help_text="Optional PDF or image of the loan / mortgage agreement."
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.schedule_type})"

    @property
    def current_rate(self) -> Decimal:
        """
        Returns the most recent annual_rate from history.
        Falls back to the static annual_rate field if no history exists.
        """
        latest = self.rate_history.order_by('-effective_date').first()
        if latest:
            return latest.annual_rate
        return self.annual_rate


class AnnuityRateHistory(models.Model):
    """
    Stores time-series interest rates for a schedule.
    Supports floating-rate loans or sinking funds.
    """
    annuity_schedule = models.ForeignKey(
        AnnuitySchedule, on_delete=models.CASCADE, related_name='rate_history'
    )
    effective_date = models.DateField()
    annual_rate = models.DecimalField(max_digits=7, decimal_places=4)

    class Meta:
        ordering = ['-effective_date']
        unique_together = [('annuity_schedule', 'effective_date')]

    def __str__(self):
        return f"{self.annuity_schedule.name} @ {self.annual_rate} ({self.effective_date})"


class AnnuityPeriod(models.Model):

    schedule = models.ForeignKey(
        AnnuitySchedule, on_delete=models.CASCADE, related_name='periods'
    )
    period_number = models.IntegerField()
    payment_date = models.DateField()

    payment_amount = models.DecimalField(max_digits=14, decimal_places=2)
    interest_portion = models.DecimalField(max_digits=14, decimal_places=2)
    principal_portion = models.DecimalField(max_digits=14, decimal_places=2)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)

    # Set once the payment is posted to the ledger
    journal_entry = models.OneToOneField(
        'accounting.JournalEntry',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='annuity_period',
    )
    is_paid = models.BooleanField(default=False)

    class Meta:
        ordering = ['period_number']
        unique_together = [('schedule', 'period_number')]

    def __str__(self):
        return f"{self.schedule.name} — Period {self.period_number} ({self.payment_date})"
