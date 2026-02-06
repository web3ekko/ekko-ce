from django.db import migrations, models
import django.db.models.deletion


def create_default_pipeline(apps, schema_editor) -> None:
    NLPPipeline = apps.get_model("app", "NLPPipeline")
    NLPPipelineVersion = apps.get_model("app", "NLPPipelineVersion")

    pipeline, created = NLPPipeline.objects.get_or_create(
        pipeline_id="dspy_compiler_v1",
        defaults={"name": "Default DSPy Compiler Pipeline"},
    )
    if not created:
        return

    version = NLPPipelineVersion.objects.create(
        pipeline=pipeline,
        version="v1",
        system_prompt_suffix="",
        user_prompt_context="",
        examples=[],
    )
    pipeline.active_version = version
    pipeline.save(update_fields=["active_version"])


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0018_remove_deprecated_alerttemplate_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="NLPPipeline",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("pipeline_id", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="NLPPipelineVersion",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("version", models.CharField(max_length=64)),
                ("system_prompt_suffix", models.TextField(blank=True, default="")),
                ("user_prompt_context", models.TextField(blank=True, default="")),
                ("examples", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "pipeline",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="app.nlppipeline",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("pipeline", "version")},
            },
        ),
        migrations.AddField(
            model_name="nlppipeline",
            name="active_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="app.nlppipelineversion",
            ),
        ),
        migrations.RunPython(create_default_pipeline, migrations.RunPython.noop),
    ]
