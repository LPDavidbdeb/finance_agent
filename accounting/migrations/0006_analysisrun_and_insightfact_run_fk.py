from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_alter_customuser_family_familymember"),
        ("accounting", "0005_create_materialized_view"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalysisRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("RUNNING", "Running"), ("SUCCEEDED", "Succeeded"), ("FAILED", "Failed")], default="RUNNING", max_length=20)),
                ("version", models.CharField(default="v1", max_length=32)),
                ("started_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("completed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("source_refreshed_at", models.DateTimeField(blank=True, null=True)),
                ("insights_created", models.IntegerField(default=0)),
                ("error_message", models.TextField(blank=True, default="")),
                ("family", models.ForeignKey(help_text="Tenant boundary for this analytical run", on_delete=django.db.models.deletion.CASCADE, related_name="analysis_runs", to="users.family")),
            ],
            options={
                "ordering": ["-started_at"],
            },
        ),
        migrations.AddField(
            model_name="insightfact",
            name="analysis_run",
            field=models.ForeignKey(blank=True, help_text="Pipeline execution that produced this insight", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="insight_facts", to="accounting.analysisrun"),
        ),
        migrations.AddIndex(
            model_name="analysisrun",
            index=models.Index(fields=["family", "-started_at"], name="accounting_a_family__idx"),
        ),
        migrations.AddIndex(
            model_name="analysisrun",
            index=models.Index(fields=["status", "-started_at"], name="accounting_a_status__idx"),
        ),
    ]

