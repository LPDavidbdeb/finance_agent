# Generated migration for InsightFact model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0003_seed_statcan_master'),
    ]

    operations = [
        migrations.CreateModel(
            name='InsightFact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('computed_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Timestamp when this insight was computed (append-only)')),
                ('insight_score', models.FloatField(help_text='Materiality-weighted severity score (base_severity × materiality_multiplier)')),
                ('materiality_pct', models.FloatField(help_text='Percentage of total household spend (0-100)')),
                ('process_type', models.CharField(choices=[('DETERMINISTIC', 'Deterministic'), ('STOCHASTIC', 'Stochastic'), ('EPISODIC', 'Episodic')], help_text='Classification of the underlying process', max_length=20)),
                ('slope', models.FloatField(blank=True, help_text='Log-linear regression slope (EPIC 2.1)', null=True)),
                ('has_structural_break', models.BooleanField(default=False, help_text='Whether a structural break was detected (EPIC 2.2)')),
                ('causal_volume_pct', models.FloatField(blank=True, help_text='Volume effect % change (EPIC 3)', null=True)),
                ('causal_price_pct', models.FloatField(blank=True, help_text='Price effect % change (EPIC 3)', null=True)),
                ('projected_value', models.FloatField(blank=True, help_text='12-month projected spend (EPIC 4.1)', null=True)),
                ('expert_summary', models.TextField(help_text='Expert-grade natural language summary of the insight (EPIC 4.2)')),
                ('category', models.ForeignKey(help_text='The spending category this insight describes', on_delete=django.db.models.deletion.CASCADE, related_name='insight_facts', to='accounting.account')),
            ],
            options={
                'verbose_name': 'Insight Fact',
                'verbose_name_plural': 'Insight Facts',
                'ordering': ['-computed_at'],
            },
        ),
        migrations.AddIndex(
            model_name='insightfact',
            index=models.Index(fields=['category', '-computed_at'], name='accounting_i_categor_idx'),
        ),
        migrations.AddIndex(
            model_name='insightfact',
            index=models.Index(fields=['computed_at'], name='accounting_i_compute_idx'),
        ),
    ]

