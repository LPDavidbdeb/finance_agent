from django.db import models
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

class Merchant(models.Model):
    family = models.ForeignKey('users.Family', on_delete=models.CASCADE, related_name='merchants')
    name = models.CharField(max_length=255)
    default_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, related_name='merchants')
    is_unique_provider = models.BooleanField(default=True)

    class Meta:
        unique_together = ('family', 'name')

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class TransactionMappingRule(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='mapping_rules')
    search_text = models.CharField(max_length=255)
    # Note: Using string reference 'banking.FinancialInstitution' to avoid circular imports
    institution = models.ForeignKey('banking.FinancialInstitution', on_delete=models.CASCADE, null=True, blank=True, related_name='mapping_rules')

    def __str__(self):
        return f"{self.search_text} -> {self.merchant.name}"

@receiver(pre_save, sender=Merchant)
def capture_old_account(sender, instance, **kwargs):
    """
    Captures the old default_account_id before the Merchant is saved
    so we know if it actually changed.
    """
    if instance.pk:
        try:
            old_instance = Merchant.objects.get(pk=instance.pk)
            instance._old_account_id = old_instance.default_account_id
        except Merchant.DoesNotExist:
            instance._old_account_id = None
    else:
        instance._old_account_id = None

@receiver(post_save, sender=Merchant)
def sync_ledger_on_merchant_update(sender, instance, created, **kwargs):
    """
    If the default_account changed, safely sweep the TransactionLine table 
    and update historical records to point to the new account.
    """
    from accounting.models import TransactionLine
    if not created:
        old_account_id = getattr(instance, '_old_account_id', None)
        new_account_id = instance.default_account_id
        
        # If the account changed and we have a new account to point to
        if old_account_id != new_account_id and new_account_id:
            # Filter specifically by the exact old account ID and description
            # to safely avoid touching the Bank/Asset side of the Journal Entry
            TransactionLine.objects.filter(
                journal_entry__description=instance.name,
                account_id=old_account_id
            ).update(account_id=new_account_id)
