from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from app.services.nlp.eval.seed_prompts import NLPEvalCase


class TestNLPGenerateExamplesFromSeed(TestCase):
    def test_writes_only_passing_examples_by_default(self):
        # Minimal ProposedSpec envelope shape the command expects.
        proposed_ok = {
            "schema_version": "proposed_spec_v2",
            "template": {"schema_version": "alert_template_v2", "trigger": {"evaluation_mode": "event_driven"}, "signals": {"principals": [], "factors": []}, "scope": {"networks": ["ETH:mainnet"]}, "notification": {}},
            "compiled_executable": {"schema_version": "alert_executable_v1", "datasources": []},
            "compile_report": {"errors": [], "selected_catalog_ids": []},
            "missing_info": [],
        }
        proposed_bad = {
            **proposed_ok,
            "compile_report": {"errors": ["boom"], "selected_catalog_ids": []},
        }

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "examples.json"

            # Two seed cases -> first passes, second fails.
            with patch(
                "app.management.commands.nlp_generate_examples_from_seed.seed_prompt_cases",
                return_value=[
                    NLPEvalCase(case_id="a", nl_description="x", context={}, expected_no_catalog_ids=True),
                    NLPEvalCase(case_id="b", nl_description="y", context={}, expected_no_catalog_ids=True),
                ],
            ):
                with patch(
                    "app.management.commands.nlp_generate_examples_from_seed.compile_to_proposed_spec",
                    side_effect=[proposed_ok, proposed_bad],
                ):
                    with patch(
                        "app.management.commands.nlp_generate_examples_from_seed.evaluate_compiler_output",
                        side_effect=[
                            type("R", (), {"ok": True, "errors": []})(),
                            type("R", (), {"ok": False, "errors": ["compile failed"]})(),
                        ],
                    ):
                        call_command("nlp_generate_examples_from_seed", "--out", str(out))

            payload = json.loads(out.read_text(encoding="utf-8"))
            assert isinstance(payload, list)
            assert len(payload) == 1
            assert payload[0]["nl_description"] == "x"

    def test_writes_failing_when_flag_set(self):
        proposed = {
            "schema_version": "proposed_spec_v2",
            "template": {"schema_version": "alert_template_v2", "trigger": {"evaluation_mode": "event_driven"}, "signals": {"principals": [], "factors": []}, "scope": {"networks": []}, "notification": {}},
            "compiled_executable": {"schema_version": "alert_executable_v1", "datasources": []},
            "compile_report": {"errors": ["boom"], "selected_catalog_ids": []},
            "missing_info": [{"code": "network_required"}],
        }

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "examples.json"
            with patch(
                "app.management.commands.nlp_generate_examples_from_seed.seed_prompt_cases",
                return_value=[NLPEvalCase(case_id="a", nl_description="x", context={}, expected_no_catalog_ids=True)],
            ):
                with patch(
                    "app.management.commands.nlp_generate_examples_from_seed.compile_to_proposed_spec",
                    return_value=proposed,
                ):
                    with patch(
                        "app.management.commands.nlp_generate_examples_from_seed.evaluate_compiler_output",
                        return_value=type("R", (), {"ok": False, "errors": ["compile failed"]})(),
                    ):
                        call_command("nlp_generate_examples_from_seed", "--out", str(out), "--include-failing")

            payload = json.loads(out.read_text(encoding="utf-8"))
            assert len(payload) == 1
            assert payload[0]["_eval"]["ok"] is False
