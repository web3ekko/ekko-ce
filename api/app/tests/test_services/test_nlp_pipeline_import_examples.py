from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from app.models.nlp import NLPPipeline, NLPPipelineVersion


class TestNLPPipelineImportExamples(TestCase):
    def test_import_creates_pipeline_and_version_and_can_set_active(self):
        examples = [
            {
                "nl_description": "Alert me when a monitored wallet has more than 5 transactions in the last 24 hours.",
                "context": {"preferred_network": "ETH:mainnet"},
                "output_json": {"schema_version": "alert_template_v2", "target_kind": "wallet", "scope": {"networks": ["ETH:mainnet"]}, "signals": {}, "trigger": {}, "notification": {}},
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "examples.json"
            path.write_text(json.dumps(examples), encoding="utf-8")

            call_command(
                "nlp_pipeline_import_examples",
                "--pipeline-id",
                "dspy_plan_compiler_v2",
                "--pipeline-version",
                "v2",
                "--file",
                str(path),
                "--set-active",
            )

        pipeline = NLPPipeline.objects.get(pipeline_id="dspy_plan_compiler_v2")
        version = NLPPipelineVersion.objects.get(pipeline=pipeline, version="v2")
        assert pipeline.active_version_id == version.id
        assert isinstance(version.examples, list)
        assert version.examples[0]["nl_description"].startswith("Alert me when")
