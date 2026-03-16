from django.db import models
from users.models import Family
from accounting.models import Account, JournalEntry

class FinancialInstitution(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class ProductType(models.TextChoices):
    CHECKING = 'CHECKING', 'Checking'
    SAVINGS = 'SAVINGS', 'Savings'
    CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
    LOAN = 'LOAN', 'Loan'
    INVESTMENT = 'INVESTMENT', 'Investment'

class FinancialProduct(models.Model):
    institution = models.ForeignKey(FinancialInstitution, on_delete=models.CASCADE, related_name='products')
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='financial_products')
    account = models.OneToOneField(Account, on_delete=models.PROTECT, related_name='financial_product')
    product_type = models.CharField(max_length=50, choices=ProductType.choices)
    
    def __str__(self):
        return f"{self.institution.name} - {self.get_product_type_display()} ({self.family.name})"

class BankStatementImport(models.Model):
    financial_product = models.ForeignKey('FinancialProduct', on_delete=models.CASCADE, related_name='statement_imports')
    file = models.FileField(upload_to='statements/', null=True, blank=True)
    status = models.CharField(max_length=50, default='PROCESSING')
    raw_ai_extraction = models.JSONField(null=True, blank=True)
    validation_errors = models.JSONField(null=True, blank=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Statement Import {self.id} - {self.financial_product}"

class TransactionStatus(models.TextChoices):
    UNPROCESSED = 'UNPROCESSED', 'Unprocessed'
    PENDING_REVIEW = 'PENDING_REVIEW', 'Pending Review'
    RECONCILED = 'RECONCILED', 'Reconciled'

class StagedTransaction(models.Model):
    statement_import = models.ForeignKey(BankStatementImport, on_delete=models.CASCADE, related_name='staged_transactions', null=True)
    bank_date = models.DateField()
    raw_description = models.CharField(max_length=1024)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    unique_bank_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=50, choices=TransactionStatus.choices, default=TransactionStatus.UNPROCESSED)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='staged_transactions')
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.bank_date} - {self.raw_description} - {self.amount}"
