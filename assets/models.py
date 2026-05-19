from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal


class PhysicalAsset(models.Model):
    """
    Abstract base for physical assets that share the same core valuation fields.

    Concrete subclasses can add domain-specific ownership, composition, and
    financing relations without duplicating the shared asset metadata.
    """

    name = models.CharField(max_length=255)
    purchase_value = models.DecimalField(max_digits=15, decimal_places=2)
    current_market_value = models.DecimalField(max_digits=15, decimal_places=2)
    purchase_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class TangibleAsset(PhysicalAsset):
    """
    Concrete family-owned physical asset tracked within the double-entry system.
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

    def clean(self):
        super().clean()
        # Ensure the linked account is an ASSET type to maintain ledger integrity.
        if self.account_id and self.account.account_type != 'ASSET':
            raise ValidationError("The linked account must be of type ASSET.")

    def __str__(self):
        return f"{self.name} ({self.family.name})"


# ----------------------------
# House / Component Models
# ----------------------------


class HouseAsset(models.Model):
    """A house wrapper that links the financial TangibleAsset to a structural
    organization of floors, rooms and components.

    The real financial identity remains on `TangibleAsset`; `HouseAsset` is
    the structural root used for building and inventory purposes.
    """
    tangible_asset = models.OneToOneField(
        TangibleAsset,
        on_delete=models.CASCADE,
        related_name='house_asset'
    )
    address = models.CharField(max_length=512, blank=True)
    num_floors = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"House: {self.tangible_asset.name}"


class Floor(models.Model):
    house = models.ForeignKey(HouseAsset, on_delete=models.CASCADE, related_name='floors')
    floor_number = models.IntegerField()
    name = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['floor_number']

    def __str__(self):
        return f"{self.house} - Floor {self.floor_number} ({self.name})"

    def total_room_area(self):
        # Sum area for rooms on this floor
        from django.db.models import Sum, F, DecimalField
        agg = self.rooms.aggregate(total=Sum(F('length') * F('width'), output_field=DecimalField()))
        return agg['total'] or Decimal('0.00')


class Room(models.Model):
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=100)
    length = models.DecimalField(max_digits=8, decimal_places=2, help_text='Meters')
    width = models.DecimalField(max_digits=8, decimal_places=2, help_text='Meters')
    height = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text='Meters')

    def __str__(self):
        return f"{self.floor} - Room {self.name}"

    @property
    def area(self):
        return (self.length * self.width)

    def wall_area(self):
        # Perimeter * height (if height provided)
        if not self.height:
            return None
        perimeter = (self.length + self.width) * Decimal('2')
        return perimeter * self.height


class Window(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='windows')
    height = models.DecimalField(max_digits=6, decimal_places=2, help_text='Meters')
    width = models.DecimalField(max_digits=6, decimal_places=2, help_text='Meters')
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f"Window x{self.quantity} ({self.width}m x {self.height}m) in {self.room}"

    @property
    def area(self):
        return (self.width * self.height) * Decimal(self.quantity)
