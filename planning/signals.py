from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from .models import AnnuitySchedule
from categorization.models import Merchant, TransactionMappingRule

@receiver(post_save, sender=AnnuitySchedule)
def create_loan_mapping_rule(sender, instance, created, **kwargs):
    """
    Observer Pattern: Automatically generate a smart categorization rule 
    whenever a new financing schedule is created.
    """
    if not created:
        return

    # 1. Ensure a placeholder merchant exists for this loan
    merchant_name = f"[LOAN] {instance.name}"
    merchant, _ = Merchant.objects.get_or_create(
        family=instance.family,
        name=merchant_name,
        defaults={
            'is_unique_provider': True
        }
    )

    # 2. Create the interceptor rule
    # Success Criteria: min/max bounds set to computed_payment +/- $5.00
    variance = Decimal("5.00")
    
    TransactionMappingRule.objects.create(
        merchant=merchant,
        search_text=instance.name,
        min_amount=instance.computed_payment - variance,
        max_amount=instance.computed_payment + variance,
        linked_schedule=instance
    )
