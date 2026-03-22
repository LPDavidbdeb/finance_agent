from django.db import models
from users.models import Family, FamilyMember
from accounting.models import Account, JournalEntry

class FinancialInstitution(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class FinancialProduct(models.Model):
    class ProductType(models.TextChoices):
        CHECKING = 'CHECKING', 'Checking'
        SAVINGS = 'SAVINGS', 'Savings'
        CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
        LOAN = 'LOAN', 'Loan'
        INVESTMENT = 'INVESTMENT', 'Investment'
        REGISTERED = 'REGISTERED', 'Registered Account'

    institution = models.ForeignKey(FinancialInstitution, on_delete=models.CASCADE, related_name='products')
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='financial_products')
    owner = models.ForeignKey(FamilyMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='financial_products')
    account = models.OneToOneField(Account, on_delete=models.PROTECT, related_name='financial_product')
    product_type = models.CharField(max_length=50, choices=ProductType.choices)
    account_number = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="The exact account, contract, or card number used for statement reconciliation."
    )
    
    def __str__(self):
        return f"{self.institution.name} - {self.get_product_type_display()} ({self.family.name})"

class BankStatementImport(models.Model):
    class Status(models.TextChoices):
        STAGED = 'STAGED', 'Staged'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        VALIDATION_FAILED = 'VALIDATION_FAILED', 'Validation Failed'

    financial_product = models.ForeignKey('FinancialProduct', on_delete=models.CASCADE, related_name='statement_imports')
    file = models.FileField(upload_to='statements/%Y/%m/', null=True, blank=True)
    
    upload_date = models.DateTimeField(auto_now_add=True)
    document_date = models.DateField(null=True, blank=True)
    
    processed_by_ai = models.BooleanField(default=False)
    processed_by_python = models.BooleanField(default=False)
    
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.STAGED)
    shadow_mode_mismatch = models.BooleanField(default=False)
    
    raw_ai_extraction = models.JSONField(null=True, blank=True)
    validation_errors = models.JSONField(null=True, blank=True)
    
    def __str__(self):
        return f"Statement Import {self.id} - {self.financial_product}"

class StagedTransaction(models.Model):
    class Status(models.TextChoices):
        UNPROCESSED = 'UNPROCESSED', 'Unprocessed'
        PENDING_REVIEW = 'PENDING_REVIEW', 'Pending Review'
        RECONCILED = 'RECONCILED', 'Reconciled'

    statement_import = models.ForeignKey(BankStatementImport, on_delete=models.CASCADE, related_name='staged_transactions')
    bank_date = models.DateField()
    raw_description = models.CharField(max_length=1024)
    clean_description = models.CharField(max_length=1024, null=True, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    unique_bank_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.UNPROCESSED)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='staged_transactions')
    predicted_account = models.ForeignKey(
        'accounting.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='predicted_for_transactions'
    )
    merchant = models.ForeignKey(
        'categorization.Merchant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staged_transactions'
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['statement_import', 'unique_bank_id'], 
                name='unique_transaction_per_import',
                condition=models.Q(unique_bank_id__isnull=False)
            )
        ]

    def __str__(self):
        return f"{self.bank_date} - {self.raw_description} - {self.amount}"
