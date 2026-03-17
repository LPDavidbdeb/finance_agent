from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.conf import settings
import uuid
from datetime import date
from dateutil.relativedelta import relativedelta

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
        related_name='users',
        help_text="The primary tenant boundary for this user."
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email

class FamilyMember(models.Model):
    """
    The core demographic model for financial planning.
    Separates the physical person from the login credentials (CustomUser).
    """
    class Sex(models.TextChoices):
        MALE = 'M', 'Male'
        FEMALE = 'F', 'Female'
        OTHER = 'O', 'Other'

    class Role(models.TextChoices):
        PARENT = 'PARENT', 'Parent'
        CHILD = 'CHILD', 'Child'
        OTHER = 'OTHER', 'Other'

    STATUTORY_AGES = {
        'RESP_DEADLINE': 15,
        'DRIVING_PERMIT': 16,
        'CEGEP_START': 17,
        'MAJORITY_TFSA': 18,
        'QPP_EARLY': 60,
        'RRSP_CONVERSION': 71,
    }

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='members')
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    sex = models.CharField(max_length=1, choices=Sex.choices)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CHILD)
    
    # Optional link to a login account if they are a manager
    user_account = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='demographic_profile'
    )

    expected_age_at_retirement = models.IntegerField(default=65)
    expected_age_at_death = models.IntegerField(default=99)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"

    @property
    def current_age(self) -> int:
        today = date.today()
        # Subtract 1 year if they haven't had their birthday yet this year
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def get_date_for_age(self, target_age: int) -> date:
        """Returns the exact date they will turn the target age."""
        return self.date_of_birth + relativedelta(years=target_age)

    @property
    def financial_milestones(self) -> dict:
        """
        Calculates universal financial milestones based on role and statutory ages.
        """
        milestones = {}
        
        if self.role == self.Role.CHILD:
            # RESP Deadline: Dec 31 of the year they turn 15
            age_15_date = self.get_date_for_age(self.STATUTORY_AGES['RESP_DEADLINE'])
            milestones['resp_grant_deadline'] = date(age_15_date.year, 12, 31)
            
            # CEGEP Start: roughly September of the year they turn 17
            age_17_date = self.get_date_for_age(self.STATUTORY_AGES['CEGEP_START'])
            milestones['cegep_start_estimate'] = date(age_17_date.year, 9, 1)
            
            # TFSA Eligibility: Their exact 18th birthday
            milestones['tfsa_eligibility'] = self.get_date_for_age(self.STATUTORY_AGES['MAJORITY_TFSA'])
            
        elif self.role in [self.Role.PARENT, self.Role.OTHER]:
            # RRSP Conversion to RRIF: Dec 31 of the year they turn 71
            age_71_date = self.get_date_for_age(self.STATUTORY_AGES['RRSP_CONVERSION'])
            milestones['rrsp_to_rrif_deadline'] = date(age_71_date.year, 12, 31)
            
            # Early QPP Eligibility: Exact 60th birthday
            milestones['early_qpp_eligibility'] = self.get_date_for_age(self.STATUTORY_AGES['QPP_EARLY'])
            
            # User-defined milestones
            milestones['planned_retirement'] = self.get_date_for_age(self.expected_age_at_retirement)
            milestones['statistical_end_of_plan'] = self.get_date_for_age(self.expected_age_at_death)

        return milestones
