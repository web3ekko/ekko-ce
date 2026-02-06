from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

from django.conf import settings
from django.core.management.base import BaseCommand

from app.services.nlp.compiler import ProposedSpecCompilationError, compile_to_proposed_spec
from app.services.nlp.eval.evaluator import evaluate_compiler_output
from app.services.nlp.eval.seed_prompts import seed_prompt_cases
from app.services.nlp.pipelines import PLAN_PIPELINE_ID


class Command(BaseCommand):
    help = (
        "Generate training examples from the seed prompt set by running the compiler and\n"
        "writing passing (or all) cases as NLPPipelineVersion.examples-compatible JSON."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default="test-results/nlp_training_examples.json",
            help="Write examples JSON here (default: test-results/nlp_training_examples.json).",
        )
        parser.add_argument(
            "--pipeline-id",
            default=PLAN_PIPELINE_ID,
            help=f"NLP pipeline id to run (default: {PLAN_PIPELINE_ID})",
        )
        parser.add_argument(
            "--model",
            default="",
            help="Override settings.GEMINI_MODEL for this run (LiteLLM; e.g. ollama/gemma:4b).",
        )
        parser.add_argument(
            "--include-failing",
            action="store_true",
            help="Include failing cases in the output (with errors). Default: only passing cases are written.",
        )
        parser.add_argument(
            "--include-incomplete",
            action="store_true",
            help="Include passing cases that still have missing_info (e.g. network_required). Default: incomplete cases are skipped.",
        )

    def handle(self, *args, **options):
        out_path = Path(str(options["out"])).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        pipeline_id = str(options["pipeline_id"]).strip() or PLAN_PIPELINE_ID
        model_override = str(options["model"]).strip()
        if model_override:
            setattr(settings, "GEMINI_MODEL", model_override)
            if model_override.lower().startswith("ollama/"):
                setattr(settings, "NLP_TIMEOUT", 120)
                setattr(settings, "LLM_MAX_RETRIES", 2)
            setattr(settings, "NLP_REQUIRE_DSPY", True)
            setattr(settings, "NLP_FALLBACK_ON_DSPY_FAILURE", False)

        include_failing = bool(options.get("include_failing"))
        include_incomplete = bool(options.get("include_incomplete"))

        examples: List[Dict[str, Any]] = []
        for case in seed_prompt_cases():
            job_id = str(uuid.uuid4())
            try:
                proposed = compile_to_proposed_spec(
                    nl_description=case.nl_description,
                    job_id=job_id,
                    client_request_id=None,
                    context=dict(case.context),
                    pipeline_id=pipeline_id,
                )
            except ProposedSpecCompilationError as exc:
                status = self.style.ERROR("FAIL")
                self.stdout.write(f"[{status}] {case.case_id}")
                self.stdout.write(f"  - {exc}")
                if include_failing:
                    examples.append(
                        {
                            "nl_description": case.nl_description,
                            "context": dict(case.context),
                            "output_json": None,
                            "_eval": {"ok": False, "errors": [str(exc)], "raw_response": (exc.raw_response or "")[:2000]},
                        }
                    )
                continue

            eval_result = evaluate_compiler_output(
                case_id=case.case_id,
                proposed_spec=proposed,
                expected_catalog_ids_any_of=list(case.expected_catalog_ids_any_of or []),
                expected_no_catalog_ids=bool(case.expected_no_catalog_ids),
                expected_trigger_modes_any_of=list(case.expected_trigger_modes_any_of or []),
                expected_missing_info_codes_any_of=list(case.expected_missing_info_codes_any_of or []),
                expected_variable_ids_all=list(case.expected_variable_ids_all or []),
            )

            missing_info = proposed.get("missing_info")
            is_incomplete = isinstance(missing_info, list) and len(missing_info) > 0

            if eval_result.ok and (include_incomplete or not is_incomplete):
                # Store the *template draft* as output_json; the API wraps it into ProposedSpec deterministically.
                examples.append(
                    {
                        "nl_description": case.nl_description,
                        "context": dict(case.context),
                        "output_json": proposed.get("template"),
                    }
                )
            elif include_failing:
                examples.append(
                    {
                        "nl_description": case.nl_description,
                        "context": dict(case.context),
                        "output_json": proposed.get("template"),
                        "_eval": {"ok": False, "errors": eval_result.errors},
                    }
                )

            status = self.style.SUCCESS("PASS") if eval_result.ok else self.style.ERROR("FAIL")
            if eval_result.ok and is_incomplete and not include_incomplete:
                self.stdout.write(f"[SKIP] {case.case_id} (missing_info present)")
            else:
                self.stdout.write(f"[{status}] {case.case_id}")
            for err in eval_result.errors:
                self.stdout.write(f"  - {err}")

        out_path.write_text(json.dumps(examples, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(examples)} examples to {out_path}"))
