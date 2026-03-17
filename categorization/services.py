from typing import Optional

from django.db.models import Q

from .models import TransactionMappingRule


def find_matching_rule(raw_description: str, institution_id: int) -> Optional[TransactionMappingRule]:
    if not raw_description:
        return None

    description = raw_description.strip()
    if not description:
        return None

    institution_match = (
        TransactionMappingRule.objects.filter(
            institution_id=institution_id,
        )
        .filter(Q(search_text__iexact=description) | Q(search_text__icontains=description) | Q(search_text__istartswith=description))
        .order_by('id')
        .first()
    )
    if institution_match:
        return institution_match

    return (
        TransactionMappingRule.objects.filter(institution__isnull=True)
        .filter(Q(search_text__iexact=description) | Q(search_text__icontains=description) | Q(search_text__istartswith=description))
        .order_by('id')
        .first()
    )

