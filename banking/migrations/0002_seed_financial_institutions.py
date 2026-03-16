from django.db import migrations

def create_financial_institutions(apps, schema_editor):
    FinancialInstitution = apps.get_model('banking', 'FinancialInstitution')

    institutions = [
        'RBC',
        'TD',
        'Scotiabank',
        'BMO',
        'CIBC',
        'National Bank',
        'Desjardins',
        'Tangerine',
    ]

    for name in institutions:
        FinancialInstitution.objects.create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ('banking', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_financial_institutions),
    ]
