"""
PRD-driven unit tests for the vNext template compiler (NL -> ProposedSpec v2).

Authoritative PRDs:
- /docs/prd/apps/api/PRD-NLP-Service-USDT.md
- /docs/prd/schemas/SCHEMA-ProposedSpec.md
- /docs/prd/schemas/SCHEMA-AlertTemplate-v2.md
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings

from app.services.datasource_catalog import list_compiler_catalog_entries
from app.services.nlp.compiler import LLMParseResult, compile_to_proposed_spec
from app.services.nlp.pipelines import PLAN_PIPELINE_ID


def _minimal_plan_spec(*, catalog_id: str) -> dict:
    return {
        "schema_version": "alert_template_v2",
        "name": "Balance alert (template)",
        "description": "Alert when balance drops below threshold",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [
            {"id": "threshold", "type": "decimal", "label": "Threshold", "required": True, "default": 0.5},
            {"id": "window_duration", "type": "duration", "label": "Window", "required": True, "default": "24h"},
        ],
        "signals": {
            "principals": [
                {
                    "name": "balance_latest",
                    "unit": "native",
                    "update_sources": [
                        {
                            "source_type": "observation",
                            "ref": catalog_id,
                            "how_to_ingest": "rpc_call",
                            "polling": {"enabled": False, "cadence_seconds": 0},
                        }
                    ],
                }
            ],
            "factors": [],
        },
        "derivations": [],
        "trigger": {
            "evaluation_mode": "periodic",
            "condition_ast": {"op": "lt", "left": "balance_latest", "right": "{{threshold}}"},
            "cron_cadence_seconds": 3600,
            "dedupe": {"cooldown_seconds": 300, "key_template": "{{instance_id}}:{{target.key}}"},
        },
        "notification": {"title_template": "Balance alert: {{target.short}}", "body_template": "Balance: {{balance_latest}}"},
        "fallbacks": [],
        "assumptions": [],
    }


@override_settings(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    GEMINI_API_KEY="test",
    NLP_ENABLED=True,
    NLP_PROPOSED_SPEC_TTL_SECS=3600,
)
class TestNLPPlanCompiler(TestCase):
    def test_compile_to_proposed_spec_v2_builds_plan_and_compiled_executable(self):
        catalog_id = list_compiler_catalog_entries()[0]["catalog_id"]

        def stub_dspy(**_kwargs):
            return LLMParseResult(
                parsed={
                    "template": _minimal_plan_spec(catalog_id=catalog_id),
                    "required_user_inputs": {},
                    "human_preview": {},
                    "warnings": [],
                },
                raw_response="stub-dspy-output",
            )

        with patch("app.services.nlp.compiler._compile_with_dspy", stub_dspy):
            result = compile_to_proposed_spec(
                nl_description="Alert when balance drops below 0.5 ETH",
                job_id="job-plan-1",
                client_request_id=None,
                context={"preferred_network": "ETH:mainnet"},
                pipeline_id=PLAN_PIPELINE_ID,
            )

        assert result["schema_version"] == "proposed_spec_v2"
        assert isinstance(result["template"], dict)
        assert result["template"]["schema_version"] == "alert_template_v2"
        assert result["template"]["target_kind"] == "wallet"
        assert "targets" not in result["template"]
        assert "target_selector" not in result["template"]

        compiled = result["compiled_executable"]
        assert isinstance(compiled, dict)
        assert compiled.get("schema_version") == "alert_executable_v1"
        assert "datasources" in compiled
        assert compiled["datasources"][0]["catalog_id"] == catalog_id

        required = result["required_user_inputs"]
        assert required["targets_required"] is True
        assert required["target_kind"] == "wallet"
        assert "threshold" in required["required_variables"]

        assert isinstance(result.get("pipeline_metadata"), dict)
        assert "latency_ms" in result["pipeline_metadata"]
        assert isinstance(result["pipeline_metadata"].get("stage_timings_ms"), dict)

    def test_compile_to_proposed_spec_v2_emits_progress_events(self):
        catalog_id = list_compiler_catalog_entries()[0]["catalog_id"]

        def stub_dspy(**_kwargs):
            return LLMParseResult(
                parsed={
                    "template": _minimal_plan_spec(catalog_id=catalog_id),
                    "required_user_inputs": {},
                    "human_preview": {},
                    "warnings": [],
                },
                raw_response="stub-dspy-output",
            )

        events: list[tuple[str, int, str]] = []

        def progress_cb(stage: str, progress: int, message: str) -> None:
            events.append((stage, progress, message))

        with patch("app.services.nlp.compiler._compile_with_dspy", stub_dspy):
            compile_to_proposed_spec(
                nl_description="Alert when balance drops below 0.5 ETH",
                job_id="job-plan-2",
                client_request_id=None,
                context={"preferred_network": "ETH:mainnet"},
                pipeline_id=PLAN_PIPELINE_ID,
                progress_callback=progress_cb,
            )

        assert any(e[0] == "classify" for e in events)
        assert any(e[0] == "resolve_scope" for e in events)
        assert any(e[0] == "draft_plan" for e in events)
        assert any(e[0] == "validate" for e in events)
        assert any(e[0] == "compile" for e in events)
        assert any(e[0] == "assemble_preview" for e in events)

    def test_compile_to_proposed_spec_v2_includes_context_patches_for_network_missing_info(self):
        catalog_id = list_compiler_catalog_entries()[0]["catalog_id"]

        def stub_dspy(**_kwargs):
            plan = _minimal_plan_spec(catalog_id=catalog_id)
            plan["scope"] = {"networks": [], "instrument_constraints": []}
            return LLMParseResult(
                parsed={
                    "template": plan,
                    "required_user_inputs": {},
                    "human_preview": {},
                    "warnings": [],
                },
                raw_response="stub-dspy-output",
            )

        with patch("app.services.nlp.compiler._compile_with_dspy", stub_dspy):
            result = compile_to_proposed_spec(
                nl_description="Alert when balance drops below 0.5 ETH",
                job_id="job-plan-3",
                client_request_id=None,
                context={},
                pipeline_id=PLAN_PIPELINE_ID,
            )

        missing = result.get("missing_info")
        assert isinstance(missing, list)
        network_item = next((m for m in missing if isinstance(m, dict) and m.get("code") == "network_required"), None)
        assert isinstance(network_item, dict)
        options = network_item.get("options")
        assert isinstance(options, list) and options
        assert all(isinstance(o, dict) and isinstance(o.get("context_patch"), dict) for o in options)
