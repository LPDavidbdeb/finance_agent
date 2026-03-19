from django.db import models

class Merchant(models.Model):
    family = models.ForeignKey('users.Family', on_delete=models.CASCADE, related_name='merchants')
    name = models.CharField(max_length=255)
    default_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, related_name='merchants')

    class Meta:
        unique_together = ('family', 'name')

    def __str__(self):
        return self.name

class TransactionMappingRule(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='mapping_rules')
    search_text = models.CharField(max_length=255)
    # Note: Using string reference 'banking.FinancialInstitution' to avoid circular imports
    institution = models.ForeignKey('banking.FinancialInstitution', on_delete=models.CASCADE, null=True, blank=True, related_name='mapping_rules')

    def __str__(self):
        return f"{self.search_text} -> {self.merchant.name}"
