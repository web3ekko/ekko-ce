import pytest

from app.services.nlp import compiler
from app.services.nlp.pipelines import PLAN_PIPELINE_ID

pytestmark = pytest.mark.django_db


def _template_stub() -> dict:
    return {
        "schema_version": "alert_template_v2",
        "name": "Test Template",
        "description": "Test description",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [],
        "signals": {"principals": [], "factors": [{"name": "balance_latest", "unit": "WEI", "update_sources": [{"ref": "ducklake.wallet_balance_window"}]}]},
        "derivations": [],
        "trigger": {
            "evaluation_mode": "periodic",
            "condition_ast": {"op": "gt", "left": "balance_latest", "right": 0},
            "cron_cadence_seconds": 300,
            "dedupe": {"cooldown_seconds": 0, "key_template": "{{instance_id}}:{{target.key}}"},
            "pruning_hints": {"evm": {"tx_type": "any"}},
        },
        "notification": {"title_template": "t", "body_template": "b"},
        "fallbacks": [],
        "assumptions": [],
    }


def test_compile_to_proposed_spec_falls_back_on_dspy_failure(monkeypatch):
    def raise_dspy_error(**_kwargs):
        raise compiler.ProposedSpecCompilationError("DSPy failure")

    def stub_llm(**_kwargs):
        return compiler.LLMParseResult(
            parsed={"template": _template_stub(), "warnings": []},
            raw_response="stub-llm-output",
        )

    monkeypatch.setattr(compiler, "_compile_with_dspy", raise_dspy_error)
    monkeypatch.setattr(compiler, "_compile_with_llm", stub_llm)
    monkeypatch.setattr(compiler.settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(compiler.settings, "NLP_FALLBACK_ON_DSPY_FAILURE", True, raising=False)
    monkeypatch.setattr(compiler.settings, "NLP_REQUIRE_DSPY", False, raising=False)

    result = compiler.compile_to_proposed_spec(
        nl_description="Alert me when balance changes",
        job_id="job-1",
        client_request_id=None,
        context={},
        pipeline_id=PLAN_PIPELINE_ID,
    )

    assert result["schema_version"] == "proposed_spec_v2"
    assert result["template"]["name"] == "Test Template"

