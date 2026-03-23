import re
import unicodedata
from django.db import models

def normalize_search_text(text: str) -> str:
    """Utility to normalize search text: strip accents, flatten whitespace, and lowercase."""
    if not text:
        return ""
    # Normalize unicode and drop accents
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    # Flatten whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()

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
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.search_text:
            self.search_text = normalize_search_text(self.search_text)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.min_amount is not None or self.max_amount is not None:
            min_label = self.min_amount if self.min_amount is not None else '-inf'
            max_label = self.max_amount if self.max_amount is not None else '+inf'
            return f"{self.search_text} [{min_label}..{max_label}] -> {self.merchant.name}"
        return f"{self.search_text} -> {self.merchant.name}"
