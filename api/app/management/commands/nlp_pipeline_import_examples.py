from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.models.nlp import NLPPipeline, NLPPipelineVersion


class Command(BaseCommand):
    help = "Import curated NLP pipeline examples into NLPPipelineVersion (no code deploy required)."

    def add_arguments(self, parser):
        parser.add_argument("--pipeline-id", required=True, help="Pipeline id (e.g., dspy_plan_compiler_v2)")
        parser.add_argument("--pipeline-version", required=True, help="Pipeline version label (e.g., v2)")
        parser.add_argument("--file", required=True, help="Path to JSON file containing examples list")
        parser.add_argument(
            "--set-active",
            action="store_true",
            help="Set this version as the pipeline's active_version",
        )
        parser.add_argument(
            "--name",
            default="",
            help="Optional pipeline display name (only used when creating a new pipeline)",
        )
        parser.add_argument(
            "--description",
            default="",
            help="Optional pipeline description (only used when creating a new pipeline)",
        )
        parser.add_argument(
            "--system-prompt-suffix",
            default="",
            help="Optional suffix appended to the base system prompt (stored on the pipeline version).",
        )
        parser.add_argument(
            "--user-prompt-context",
            default="",
            help="Optional additional context injected into the user prompt payload (stored on the pipeline version).",
        )

    def handle(self, *args, **options):
        pipeline_id = str(options["pipeline_id"]).strip()
        version = str(options["pipeline_version"]).strip()
        file_path = Path(str(options["file"])).expanduser()

        if not pipeline_id:
            raise CommandError("--pipeline-id is required")
        if not version:
            raise CommandError("--version is required")
        if not file_path.exists():
            raise CommandError(f"Examples file not found: {file_path}")

        payload = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise CommandError("Examples file must contain a JSON list")

        name = str(options.get("name") or "").strip() or pipeline_id
        description = str(options.get("description") or "").strip()
        system_prompt_suffix = str(options.get("system_prompt_suffix") or "").strip()
        user_prompt_context = str(options.get("user_prompt_context") or "").strip()

        with transaction.atomic():
            pipeline, created = NLPPipeline.objects.get_or_create(
                pipeline_id=pipeline_id,
                defaults={"name": name, "description": description},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created NLPPipeline {pipeline_id}"))

            ver, _ = NLPPipelineVersion.objects.update_or_create(
                pipeline=pipeline,
                version=version,
                defaults={
                    "examples": payload,
                    "system_prompt_suffix": system_prompt_suffix,
                    "user_prompt_context": user_prompt_context,
                },
            )

            # Validate JSON structure via model clean().
            ver.full_clean()
            ver.save()

            if bool(options.get("set_active")):
                pipeline.active_version = ver
                pipeline.full_clean()
                pipeline.save()

        self.stdout.write(self.style.SUCCESS(f"Imported {len(payload)} examples into {pipeline_id}@{version}"))
