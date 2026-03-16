from django.db import models
from users.models import Family
from accounting.models import Account

class GlobalMerchant(models.Model):
    canonical_name = models.CharField(max_length=255)
    default_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='global_merchants')

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
