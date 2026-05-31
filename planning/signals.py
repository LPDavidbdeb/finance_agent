from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AnnuityRateHistory

@receiver(post_save, sender=AnnuityRateHistory)
def trigger_reamortization(sender, instance, created, **kwargs):
    """
    Phase 5: Dynamic Re-Amortization Trigger.
    Trigger recalculation whenever a new rate is added to history.
    """
    if created:
        from .services import AnnuityService
        AnnuityService.recalculate_schedule(
            instance.annuity_schedule,
            instance.effective_date,
            instance.annual_rate
        )
