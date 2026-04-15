# Generated migration for External Normalization Engine (EPIC 3.2)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0007_add_projection_intervals_to_insightfact'),
    ]

    operations = [
        migrations.AddField(
            model_name='insightfact',
            name='benchmark_slope',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='The external baseline slope (e.g., CPI) used for comparison',
                max_digits=7,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='insightfact',
            name='benchmark_classification',
            field=models.CharField(
                blank=True,
                choices=[
                    ('REAL_GROWTH', 'Real Growth'),
                    ('INFLATION_TRACKED', 'Inflation Tracked'),
                    ('EFFICIENCY_GAIN', 'Efficiency Gain'),
                ],
                help_text='Classification: REAL_GROWTH, INFLATION_TRACKED, or EFFICIENCY_GAIN',
                max_length=50,
                null=True,
            ),
        ),
    ]

