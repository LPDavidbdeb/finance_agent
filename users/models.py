from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class Family(models.Model):
    """
    The foundational multi-tenant boundary. All operational data is scoped to a Family.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Residence(models.Model):
    """
    Physical addresses associated with a family tenant.
    """
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='residences')
    address = models.TextField()
    is_apartment = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.address} ({self.family.name})"

class CustomUser(AbstractUser):
    """
    Extended user model. Belongs to a single primary family for isolation.
    """
    family = models.ForeignKey(
        Family, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='members',
        help_text="The primary tenant boundary for this user."
    )

    def __str__(self):
        return self.username
