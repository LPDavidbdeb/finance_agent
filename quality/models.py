from django.db import models

from accounting.models import JournalEntry, TransactionLine
from banking.models import BankStatementImport, StagedTransaction
from users.models import Family


class ConsistencyReportRun(models.Model):
    class TriggerSource(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual'
        CLI = 'CLI', 'Command Line'
        LEDGER_RESET = 'LEDGER_RESET', 'Ledger Reset'
        REPROCESS = 'REPROCESS', 'Reprocess'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='consistency_report_runs')
    trigger_source = models.CharField(max_length=32, choices=TriggerSource.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    scope = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-started_at', '-id']
        indexes = [
            models.Index(fields=['family', 'status', '-started_at']),
            models.Index(fields=['family', 'trigger_source', '-started_at']),
        ]

    def __str__(self):
        return f"Consistency run {self.id} ({self.family_id}) - {self.status}"


class ConsistencyReportFinding(models.Model):
    class Severity(models.TextChoices):
        INFO = 'INFO', 'Info'
        WARNING = 'WARNING', 'Warning'
        ERROR = 'ERROR', 'Error'

    run = models.ForeignKey(ConsistencyReportRun, on_delete=models.CASCADE, related_name='findings')
    severity = models.CharField(max_length=16, choices=Severity.choices)
    category = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    statement_import = models.ForeignKey(BankStatementImport, on_delete=models.SET_NULL, null=True, blank=True, related_name='consistency_findings')
    staged_transaction = models.ForeignKey(StagedTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='consistency_findings')
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='consistency_findings')
    transaction_line = models.ForeignKey(TransactionLine, on_delete=models.SET_NULL, null=True, blank=True, related_name='consistency_findings')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['severity', 'category', 'id']
        indexes = [
            models.Index(fields=['run', 'severity']),
            models.Index(fields=['run', 'category']),
        ]

    def __str__(self):
        return f"{self.severity} {self.category}: {self.title}"

