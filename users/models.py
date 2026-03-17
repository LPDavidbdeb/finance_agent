from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
import uuid

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

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
    username = None
    email = models.EmailField('email address', unique=True)

    family = models.ForeignKey(
        Family, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='members',
        help_text="The primary tenant boundary for this user."
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email
