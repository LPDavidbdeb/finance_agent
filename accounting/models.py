from django.db import models
from mptt.models import MPTTModel, TreeForeignKey
from users.models import Family

class AccountType(models.TextChoices):
    ASSET = 'ASSET', 'Asset'
    LIABILITY = 'LIABILITY', 'Liability'
    EQUITY = 'EQUITY', 'Equity'
    REVENUE = 'REVENUE', 'Revenue'
    EXPENSE = 'EXPENSE', 'Expense'

class Account(MPTTModel):
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
