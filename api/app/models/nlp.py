from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models


class NLPPipeline(models.Model):
    pipeline_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    active_version = models.ForeignKey(
        "NLPPipelineVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self) -> None:
        if self.active_version and self.pk and self.active_version.pipeline_id != self.pk:
            raise ValidationError("Active version must belong to the same pipeline.")

    def __str__(self) -> str:
        return f"{self.pipeline_id} ({self.name})"


class NLPPipelineVersion(models.Model):
    pipeline = models.ForeignKey(
        NLPPipeline,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.CharField(max_length=64)
    system_prompt_suffix = models.TextField(blank=True, default="")
    user_prompt_context = models.TextField(blank=True, default="")
    examples = models.JSONField(blank=True, default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("pipeline", "version")
        ordering = ["-created_at"]

    def clean(self) -> None:
        if not isinstance(self.examples, list):
            raise ValidationError("Examples must be a list of objects.")
        for idx, example in enumerate(self.examples):
            if not isinstance(example, dict):
                raise ValidationError(f"Examples[{idx}] must be an object.")
            nl_description = example.get("nl_description")
            if not isinstance(nl_description, str) or not nl_description.strip():
                raise ValidationError(f"Examples[{idx}].nl_description is required.")
            if "output_json" not in example:
                raise ValidationError(f"Examples[{idx}].output_json is required.")

    def __str__(self) -> str:
        return f"{self.pipeline.pipeline_id}@{self.version}"
