"""
Unit tests for the DSPy-backed NLP compiler (NL -> ProposedSpec v2).
"""

import json
import sys
import types
from types import ModuleType
from unittest.mock import patch

from django.test import TestCase, override_settings

from app.services.nlp.compiler import _build_system_prompt_v2, compile_to_proposed_spec
from app.services.nlp.pipelines import PLAN_PIPELINE_ID, PipelineConfig


def _minimal_template_v2() -> dict:
    return {
        "schema_version": "alert_template_v2",
        "name": "Balance alert (window)",
        "description": "Alert when balance drops below threshold",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [{"id": "threshold", "type": "decimal", "label": "Threshold", "required": True, "default": 0.5}],
        "signals": {"principals": [], "factors": [{"name": "balance_latest", "unit": "WEI", "update_sources": [{"ref": "ducklake.wallet_balance_window"}]}]},
        "derivations": [],
        "trigger": {
            "evaluation_mode": "periodic",
            "condition_ast": {"op": "lt", "left": "balance_latest", "right": "{{threshold}}"},
            "cron_cadence_seconds": 300,
            "dedupe": {"cooldown_seconds": 300, "key_template": "{{instance_id}}:{{target.key}}"},
            "pruning_hints": {"evm": {"tx_type": "any"}},
        },
        "notification": {"title_template": "Balance alert", "body_template": "Balance: {{balance_latest}}"},
        "fallbacks": [],
        "assumptions": [],
    }


@override_settings(GEMINI_API_KEY="test", NLP_ENABLED=True, NLP_PROPOSED_SPEC_TTL_SECS=3600, NLP_REQUIRE_DSPY=True)
class TestNLPCompiler(TestCase):
    def test_dspy_does_not_require_global_configure(self):
        dspy_logic = types.SimpleNamespace(
            target_kind="wallet",
            combine_op="and",
            conditions=[{"left": "balance_latest", "op": "lt", "right": 0.5}],
            window_duration="",
            notes=[],
        )

        fake_dspy = ModuleType("dspy")

        class Signature:  # noqa: D401
            """Minimal DSPy Signature base class for tests."""

        def InputField(*_args, **_kwargs):  # noqa: N802
            return None

        def OutputField(*_args, **_kwargs):  # noqa: N802
            return None

        class _Settings:
            @staticmethod
            def configure(*_args, **_kwargs):
                raise RuntimeError("settings.configure should not be called per-request")

        class LM:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class _Predict:
            def __init__(self, *_args, **_kwargs):
                return None

            def __call__(self, *_args, **_kwargs):
                return dspy_logic

        def Predict(*_args, **_kwargs):  # noqa: N802
            return _Predict()

        def configure(*_args, **_kwargs):  # noqa: N802
            raise RuntimeError("dspy.configure should not be called per-request")

        fake_dspy.Signature = Signature
        fake_dspy.InputField = InputField
        fake_dspy.OutputField = OutputField
        fake_dspy.Predict = Predict
        fake_dspy.LM = LM
        fake_dspy.settings = _Settings()
        fake_dspy.configure = configure

        with patch.dict(sys.modules, {"dspy": fake_dspy}):
            proposed = compile_to_proposed_spec(
                nl_description="Alert when balance drops below threshold",
                job_id="b7bd2f2f-9eaf-42a5-a822-0799b89d0f2d",
                client_request_id=None,
                context={"preferred_network": "ETH:mainnet"},
                pipeline_id=PLAN_PIPELINE_ID,
            )

        assert proposed["schema_version"] == "proposed_spec_v2"

    def test_compile_uses_dspy_when_available(self):
        # The plan compiler is multistage: DSPy extracts a small logic spec, then we
        # deterministically assemble/compile an AlertTemplate v2.
        dspy_logic = types.SimpleNamespace(
            target_kind="wallet",
            combine_op="and",
            conditions=[{"left": "balance_latest", "op": "lt", "right": 0.5}],
            window_duration="",
            notes=[],
        )

        fake_dspy = ModuleType("dspy")

        class Signature:  # noqa: D401
            """Minimal DSPy Signature base class for tests."""

        def InputField(*_args, **_kwargs):  # noqa: N802
            return None

        def OutputField(*_args, **_kwargs):  # noqa: N802
            return None

        class _Settings:
            @staticmethod
            def configure(*_args, **_kwargs):
                return None

        class LM:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class LiteLLM:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class _Predict:
            def __init__(self, *_args, **_kwargs):
                return None

            def __call__(self, *_args, **_kwargs):
                return dspy_logic

        def Predict(*_args, **_kwargs):  # noqa: N802
            return _Predict()

        fake_dspy.Signature = Signature
        fake_dspy.InputField = InputField
        fake_dspy.OutputField = OutputField
        fake_dspy.Predict = Predict
        fake_dspy.LM = LM
        fake_dspy.LiteLLM = LiteLLM
        fake_dspy.settings = _Settings()

        nl_description = (
            "Alert me if my wallet has more than 2 transactions in the last 24 hours on Ethereum"
        )

        with patch.dict(sys.modules, {"dspy": fake_dspy}):
            job_id = "b7bd2f2f-9eaf-42a5-a822-0799b89d0f2d"
            proposed = compile_to_proposed_spec(
                nl_description=nl_description,
                job_id=job_id,
                client_request_id=None,
                context={"preferred_network": "ETH:mainnet"},
                pipeline_id=PLAN_PIPELINE_ID,
            )

        assert proposed["schema_version"] == "proposed_spec_v2"
        assert proposed["job_id"] == job_id
        assert proposed["pipeline_id"] == PLAN_PIPELINE_ID
        assert proposed["template"]["schema_version"] == "alert_template_v2"
        assert proposed["compiled_executable"]["schema_version"] == "alert_executable_v1"
        assert proposed["template"]["notification"]["title_template"] == "Balance alert: {{target.short}}"
        assert proposed["template"]["notification"]["body_template"] == (
            "Balance for {{target.short}} is {{balance_latest}} (below 0.5)"
        )

    def test_compile_normalizes_dotted_signal_refs_and_defaults_trigger_mode(self):
        # The compiler should infer a datasource-backed plan from extracted signal conditions and
        # default to "hybrid" when datasources are involved.
        dspy_logic = types.SimpleNamespace(
            target_kind="wallet",
            combine_op="and",
            conditions=[{"left": "tx_count_24h", "op": "gt", "right": 0}],
            window_duration="",
            notes=[],
        )

        fake_dspy = ModuleType("dspy")

        class Signature:  # noqa: D401
            """Minimal DSPy Signature base class for tests."""

        def InputField(*_args, **_kwargs):  # noqa: N802
            return None

        def OutputField(*_args, **_kwargs):  # noqa: N802
            return None

        class _Settings:
            @staticmethod
            def configure(*_args, **_kwargs):
                return None

        class LM:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class LiteLLM:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class _Predict:
            def __init__(self, *_args, **_kwargs):
                return None

            def __call__(self, *_args, **_kwargs):
                return dspy_logic

        def Predict(*_args, **_kwargs):  # noqa: N802
            return _Predict()

        fake_dspy.Signature = Signature
        fake_dspy.InputField = InputField
        fake_dspy.OutputField = OutputField
        fake_dspy.Predict = Predict
        fake_dspy.LM = LM
        fake_dspy.LiteLLM = LiteLLM
        fake_dspy.settings = _Settings()

        with patch.dict(sys.modules, {"dspy": fake_dspy}):
            job_id = "b7bd2f2f-9eaf-42a5-a822-0799b89d0f2d"
            proposed = compile_to_proposed_spec(
                nl_description="Alert when tx_count_24h > 0",
                job_id=job_id,
                client_request_id=None,
                context={"preferred_network": "ETH:mainnet"},
                pipeline_id=PLAN_PIPELINE_ID,
            )

        assert proposed["template"]["trigger"]["evaluation_mode"] == "hybrid"

    def test_system_prompt_v2_requires_notification_placeholders(self):
        pipeline = PipelineConfig(
            pipeline_id="dspy_plan_compiler_v1",
            version="v1",
            system_prompt_suffix="",
            user_prompt_context="",
            examples=[],
        )
        prompt = _build_system_prompt_v2(pipeline)
        assert "notification.title_template MUST be short" in prompt
        assert "notification.body_template MUST include at least one placeholder" in prompt
        assert "{{target.short}}" in prompt
        assert set(proposed["required_user_inputs"]["supported_trigger_types"]) == {"periodic", "event_driven"}

        exe = proposed["compiled_executable"]
        ds_ids = {d.get("id") for d in exe.get("datasources") or []}
        assert "ds_ducklake_address_transactions_count_24h" in ds_ids
        cond = exe["conditions"]["all"][0]
        assert cond["op"] == "gt"
        assert cond["left"] == "$.datasources.ds_ducklake_address_transactions_count_24h.tx_count_24h"
