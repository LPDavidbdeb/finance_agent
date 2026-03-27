from django.db import migrations, models
import django.db.models.deletion


def backfill_institution_from_product(apps, schema_editor):
    """
    For every existing BankStatementImport that has a financial_product,
    populate the new institution FK from financial_product.institution.
    This is a lossless backfill — no data is dropped or modified.
    """
    BankStatementImport = apps.get_model('banking', 'BankStatementImport')
    to_update = []
    for stmt in BankStatementImport.objects.select_related('financial_product__institution').filter(
        financial_product__isnull=False,
        institution__isnull=True,
    ):
        stmt.institution_id = stmt.financial_product.institution_id
        to_update.append(stmt)
    if to_update:
        BankStatementImport.objects.bulk_update(to_update, ['institution_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('banking', '0016_add_processing_log'),
    ]

    operations = [
        # 1. Add institution FK to BankStatementImport (nullable for safe migration)
        migrations.AddField(
            model_name='bankstatementimport',
            name='institution',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='statement_imports',
                to='banking.financialinstitution',
            ),
        ),
        # 2. Make financial_product nullable on BankStatementImport
        migrations.AlterField(
            model_name='bankstatementimport',
            name='financial_product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='statement_imports',
                to='banking.financialproduct',
            ),
        ),
        # 3. Add per-row financial_product FK to StagedTransaction (nullable)
        migrations.AddField(
            model_name='stagedtransaction',
            name='financial_product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='staged_transactions',
                to='banking.financialproduct',
            ),
        ),
        # 4. Backfill institution from existing financial_product.institution
        migrations.RunPython(
            backfill_institution_from_product,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
