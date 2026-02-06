from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings

from app.services.nlp.compiler import ProposedSpecCompilationError, compile_to_proposed_spec
from app.services.nlp.eval.evaluator import evaluate_compiler_output
from app.services.nlp.eval.seed_prompts import seed_prompt_cases
from app.services.nlp.pipelines import PLAN_PIPELINE_ID


class Command(BaseCommand):
    help = "Run offline evaluation of the NLP compiler against a seed prompt set."

    def add_arguments(self, parser):
        parser.add_argument(
            "--in",
            dest="in_path",
            default="",
            help="Optional JSON input path (output of nlp_seed_prompts). If omitted, uses built-in seed prompts.",
        )
        parser.add_argument(
            "--out",
            default="test-results/nlp_eval_report.json",
            help="Write report JSON here (default: test-results/nlp_eval_report.json).",
        )
        parser.add_argument(
            "--pipeline-id",
            default=PLAN_PIPELINE_ID,
            help=f"NLP pipeline id to run (default: {PLAN_PIPELINE_ID})",
        )
        parser.add_argument(
            "--model",
            default="",
            help="Override settings.GEMINI_MODEL for this run (useful for local LLMs via LiteLLM).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Only run the first N cases (0 = all).",
        )

    def _load_cases(self, in_path: str) -> List[Dict[str, Any]]:
        if not in_path:
            return [
                {
                    "case_id": c.case_id,
                    "nl_description": c.nl_description,
                    "context": dict(c.context),
                    "expected_catalog_ids_any_of": list(c.expected_catalog_ids_any_of or []),
                    "expected_no_catalog_ids": bool(c.expected_no_catalog_ids),
                    "expected_trigger_modes_any_of": list(c.expected_trigger_modes_any_of or []),
                    "expected_missing_info_codes_any_of": list(c.expected_missing_info_codes_any_of or []),
                    "expected_variable_ids_all": list(c.expected_variable_ids_all or []),
                }
                for c in seed_prompt_cases()
            ]

        path = Path(in_path).expanduser()
        if not path.exists():
            raise CommandError(f"Input file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise CommandError("Input JSON must be a list")
        return payload

    def handle(self, *args, **options):
        out_path = Path(str(options["out"])).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        pipeline_id = str(options["pipeline_id"]).strip() or PLAN_PIPELINE_ID
        model_override = str(options["model"]).strip()
        if model_override:
            # Django settings module attributes are writable; this is only for offline eval.
            setattr(settings, "GEMINI_MODEL", model_override)
            # Offline eval should match production: use DSPy (prompt optimization), not a direct-LiteLLM fallback.
            if model_override.lower().startswith("ollama/"):
                setattr(settings, "NLP_TIMEOUT", 120)
                setattr(settings, "LLM_MAX_RETRIES", 2)
            setattr(settings, "NLP_REQUIRE_DSPY", True)
            setattr(settings, "NLP_FALLBACK_ON_DSPY_FAILURE", False)

        cases = self._load_cases(str(options["in_path"]).strip())
        limit = int(options["limit"] or 0)
        if limit > 0:
            cases = cases[:limit]

        started_at = timezone.now().isoformat()
        results: List[Dict[str, Any]] = []
        passed = 0

        for case in cases:
            case_id = str(case.get("case_id") or "").strip() or str(uuid.uuid4())
            nl_description = str(case.get("nl_description") or "").strip()
            if not nl_description:
                results.append({"case_id": case_id, "ok": False, "errors": ["missing nl_description"]})
                continue

            context = case.get("context") if isinstance(case.get("context"), dict) else {}
            expected_any_of = case.get("expected_catalog_ids_any_of")
            expected_any_of = expected_any_of if isinstance(expected_any_of, list) else []
            expected_no_catalog_ids = bool(case.get("expected_no_catalog_ids"))
            expected_trigger_modes = case.get("expected_trigger_modes_any_of")
            expected_trigger_modes = expected_trigger_modes if isinstance(expected_trigger_modes, list) else []
            expected_missing_codes = case.get("expected_missing_info_codes_any_of")
            expected_missing_codes = expected_missing_codes if isinstance(expected_missing_codes, list) else []
            expected_variable_ids_all = case.get("expected_variable_ids_all")
            expected_variable_ids_all = expected_variable_ids_all if isinstance(expected_variable_ids_all, list) else []

            job_id = str(uuid.uuid4())
            try:
                proposed = compile_to_proposed_spec(
                    nl_description=nl_description,
                    job_id=job_id,
                    client_request_id=None,
                    context=context,
                    pipeline_id=pipeline_id,
                )
            except ProposedSpecCompilationError as exc:
                results.append(
                    {
                        "case_id": case_id,
                        "ok": False,
                        "errors": [str(exc)],
                        "selected_catalog_ids": [],
                        "template_trigger_mode": None,
                        "raw_response": (exc.raw_response or "")[:2000],
                    }
                )
                status = self.style.ERROR("FAIL")
                self.stdout.write(f"[{status}] {case_id} -> []")
                self.stdout.write(f"  - {exc}")
                continue
            eval_result = evaluate_compiler_output(
                case_id=case_id,
                proposed_spec=proposed,
                expected_catalog_ids_any_of=expected_any_of,
                expected_no_catalog_ids=expected_no_catalog_ids,
                expected_trigger_modes_any_of=expected_trigger_modes,
                expected_missing_info_codes_any_of=expected_missing_codes,
                expected_variable_ids_all=expected_variable_ids_all,
            )
            missing_codes = []
            missing = proposed.get("missing_info")
            if isinstance(missing, list):
                for item in missing:
                    if isinstance(item, dict) and isinstance(item.get("code"), str) and item.get("code").strip():
                        missing_codes.append(item.get("code").strip())

            compile_report = proposed.get("compile_report") if isinstance(proposed.get("compile_report"), dict) else {}
            compile_errors = compile_report.get("errors") if isinstance(compile_report.get("errors"), list) else []

            template = proposed.get("template") if isinstance(proposed.get("template"), dict) else {}
            trigger = template.get("trigger") if isinstance(template.get("trigger"), dict) else {}

            results.append(
                {
                    "case_id": eval_result.case_id,
                    "ok": eval_result.ok,
                    "errors": eval_result.errors,
                    "selected_catalog_ids": eval_result.selected_catalog_ids,
                    "template_trigger_mode": eval_result.template_trigger_mode,
                    "missing_info_codes": missing_codes,
                    "compile_errors": compile_errors,
                    "template_condition_ast": trigger.get("condition_ast"),
                }
            )
            if eval_result.ok:
                passed += 1

            status = self.style.SUCCESS("PASS") if eval_result.ok else self.style.ERROR("FAIL")
            self.stdout.write(f"[{status}] {case_id} -> {eval_result.selected_catalog_ids}")
            if eval_result.errors:
                for err in eval_result.errors:
                    self.stdout.write(f"  - {err}")

        report = {
            "started_at": started_at,
            "model": getattr(settings, "GEMINI_MODEL", ""),
            "pipeline_id": pipeline_id,
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "results": results,
        }
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote report to {out_path}"))
