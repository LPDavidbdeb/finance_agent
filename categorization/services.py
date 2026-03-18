from typing import Optional
from django.db.models import Q, Value, CharField
from django.db.models.functions import Lower
from .models import TransactionMappingRule

def find_matching_rule(raw_description: str, institution_id: int) -> Optional[TransactionMappingRule]:
    if not raw_description:
        return None

    description = raw_description.strip().lower()
    if not description:
        return None

    # We want to find rules where search_text is a substring of description.
    # Since search_text is a field, we use an annotation to reverse the icontains logic.
    institution_match = (
        TransactionMappingRule.objects.filter(
            institution_id=institution_id,
        )
        .annotate(desc=Value(description, output_field=CharField()))
        .filter(desc__icontains=Lower('search_text'))
        .order_by('-search_text') # Prefer longer matches
        .first()
    )
    if institution_match:
        return institution_match

    return (
        TransactionMappingRule.objects.filter(institution__isnull=True)
        .annotate(desc=Value(description, output_field=CharField()))
        .filter(desc__icontains=Lower('search_text'))
        .order_by('-search_text') # Prefer longer matches
        .first()
    )

