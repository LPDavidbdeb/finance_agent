from django.db import models
from django.core.exceptions import ValidationError

class TangibleAsset(models.Model):
    """
    Foundational model for physical assets (Real Estate, Vehicles, etc.)
    Tracked within the double-entry system via a dedicated ASSET account.
    """
    family = models.ForeignKey(
        'users.Family', on_delete=models.CASCADE, related_name='tangible_assets'
    )
    member = models.ForeignKey(
        'users.FamilyMember', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='tangible_assets',
        help_text="Primary owner within the family (optional)."
    )
    staged_transaction = models.ForeignKey(
        'banking.StagedTransaction', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='tangible_assets',
        help_text="Link to the original purchase transaction if imported via statement."
    )
    annuity_schedule = models.ForeignKey(
        'planning.AnnuitySchedule', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='tangible_assets',
        help_text="Associated financing schedule (e.g. Mortgage)."
    )
    account = models.OneToOneField(
        'accounting.Account', 
        on_delete=models.CASCADE, 
        related_name='tangible_asset',
        help_text="The dedicated ledger account representing this asset's book value."
    )

    name = models.CharField(max_length=255)
    purchase_value = models.DecimalField(max_digits=15, decimal_places=2)
    current_market_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    purchase_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Ensure the linked account is an ASSET type to maintain ledger integrity
        if self.account_id:
            # We use .account directly if already fetched, otherwise check via ID
            # to avoid unnecessary queries if possible, but for validation we need the type.
            if self.account.account_type != 'ASSET':
                raise ValidationError("The linked account must be of type ASSET.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.family.name})"
