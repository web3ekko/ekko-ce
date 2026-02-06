from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from app.models.nlp import NLPPipeline, NLPPipelineVersion
from django.db.utils import OperationalError, ProgrammingError

# The platform is plan-first: when callers omit pipeline_id, we run the plan compiler.
PLAN_PIPELINE_ID = "dspy_plan_compiler_v1"
TEMPLATE_PIPELINE_ID = "dspy_compiler_v1"
DEFAULT_PIPELINE_ID = PLAN_PIPELINE_ID


class PipelineConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class PipelineConfig:
    pipeline_id: str
    version: str
    system_prompt_suffix: str
    user_prompt_context: str
    examples: List[Dict[str, Any]]


def _normalize_examples(examples: Any) -> List[Dict[str, Any]]:
    if not isinstance(examples, list):
        return []

    cleaned: List[Dict[str, Any]] = []
    for example in examples:
        if not isinstance(example, dict):
            continue
        nl_description = example.get("nl_description")
        output_json = example.get("output_json")
        if not isinstance(nl_description, str) or not nl_description.strip():
            continue
        if output_json is None:
            continue
        context = example.get("context") if isinstance(example.get("context"), dict) else {}
        cleaned.append(
            {
                "nl_description": nl_description.strip(),
                "context": context,
                "output_json": output_json,
            }
        )

    return cleaned


def get_pipeline_config(pipeline_id: str) -> PipelineConfig:
    try:
        pipeline = NLPPipeline.objects.select_related("active_version").get(
            pipeline_id=pipeline_id
        )
    except (NLPPipeline.DoesNotExist, OperationalError, ProgrammingError) as exc:
        # Development fallback: allow a small set of built-in pipelines if the DB
        # registry is not yet populated (or migrations haven't been applied).
        if pipeline_id in {PLAN_PIPELINE_ID, TEMPLATE_PIPELINE_ID}:
            return PipelineConfig(
                pipeline_id=pipeline_id,
                version="v1",
                system_prompt_suffix="",
                user_prompt_context="",
                examples=[],
            )
        raise PipelineConfigError(f"NLP pipeline {pipeline_id!r} is not configured") from exc

    version: NLPPipelineVersion | None = pipeline.active_version
    if version is None:
        version = pipeline.versions.order_by("-created_at").first()
    if version is None:
        raise PipelineConfigError(
            f"NLP pipeline {pipeline_id!r} has no configured versions"
        )

    return PipelineConfig(
        pipeline_id=pipeline.pipeline_id,
        version=version.version,
        system_prompt_suffix=str(version.system_prompt_suffix or "").strip(),
        user_prompt_context=str(version.user_prompt_context or "").strip(),
        examples=_normalize_examples(version.examples),
    )
