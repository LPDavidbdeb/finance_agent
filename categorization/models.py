from django.db import models
from users.models import Family
from accounting.models import Account
from banking.models import FinancialInstitution

class GlobalMerchant(models.Model):
    """
    A shared canonical representation of a merchant (e.g., 'Super C', 'Costco').
    """
    canonical_name = models.CharField(max_length=255, unique=True)
    default_statcan_account = models.ForeignKey(
        Account, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='global_merchants',
        help_text="Points to the global StatCan template account."
    )

    def __str__(self):
        return self.canonical_name

class GlobalPattern(models.Model):
    merchant = models.ForeignKey(GlobalMerchant, on_delete=models.CASCADE, related_name='patterns')
    pattern_regex = models.CharField(max_length=512)

    def __str__(self):
        return f"{self.merchant.canonical_name} - {self.pattern_regex}"

class PrivateMerchantConfig(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='merchant_configs')
    merchant = models.ForeignKey(GlobalMerchant, on_delete=models.CASCADE, related_name='private_configs')
    custom_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='private_merchant_configs')
    auto_post = models.BooleanField(default=False)

    class Meta:
        unique_together = ('family', 'merchant')

    def __str__(self):
        return f"{self.merchant.canonical_name} config for {self.family.name}"

class TransactionMappingRule(models.Model):
    search_text = models.CharField(max_length=255)
    merchant_name = models.CharField(max_length=255)
    target_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transaction_mapping_rules',
    )
    institution = models.ForeignKey(
        FinancialInstitution,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='transaction_mapping_rules',
    )

    class Meta:
        unique_together = ('search_text', 'institution')

    def __str__(self):
        institution_name = self.institution.name if self.institution else 'Global'
        return f"{self.search_text} -> {self.merchant_name} ({institution_name})"
