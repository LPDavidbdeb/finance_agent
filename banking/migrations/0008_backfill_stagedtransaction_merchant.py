from django.db import migrations
from django.db.models.functions import Lower, Trim


def backfill_merchant_fk(apps, schema_editor):
    StagedTransaction = apps.get_model('banking', 'StagedTransaction')
    Merchant = apps.get_model('categorization', 'Merchant')

    staged_qs = StagedTransaction.objects.exclude(clean_description__isnull=True).exclude(clean_description='')

    for tx in staged_qs.iterator(chunk_size=2000):
        normalized_clean = (tx.clean_description or '').strip().lower()
        if not normalized_clean:
            continue

        merchant = (
            Merchant.objects.annotate(norm_name=Lower(Trim('name')))
            .filter(norm_name=normalized_clean)
            .order_by('id')
            .first()
        )
        if merchant:
            tx.merchant_id = merchant.id
            tx.save(update_fields=['merchant'])


def reverse_backfill_merchant_fk(apps, schema_editor):
    StagedTransaction = apps.get_model('banking', 'StagedTransaction')
    StagedTransaction.objects.update(merchant_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('banking', '0007_stagedtransaction_merchant'),
    ]

    operations = [
        migrations.RunPython(backfill_merchant_fk, reverse_backfill_merchant_fk),
    ]

