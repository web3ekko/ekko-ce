"""
PRD-driven tests for template-based inline preview (Test Alert) using ProposedSpec v2 (job_id).

Authoritative PRDs:
- /docs/prd/apps/dashboard/UI-PRD-AlertCreation.md (template-based Test Alert)
- /docs/prd/apps/api/PRD-Alert-System-USDT.md
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

User = get_user_model()


def _template_spec() -> dict:
    return {
        "schema_version": "alert_template_v2",
        "name": "Balance alert (template)",
        "description": "Alert when balance drops below threshold",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [
            {"id": "threshold", "type": "decimal", "label": "Threshold", "required": True, "default": 0.5},
        ],
        "signals": {
            "principals": [
                {
                    "name": "balance_latest",
                    "unit": "native",
                    "update_sources": [
                        {
                            "ref": "ducklake.wallet_balance_latest",
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
        "notification": {"title_template": "Balance alert", "body_template": "Balance: {{balance_latest}}"},
        "fallbacks": [],
        "assumptions": [],
    }


class _FakePreviewService:
    def preview(self, input):  # type: ignore[no-untyped-def]
        keys = getattr(input, "target_keys", [])
        total = len(keys) if isinstance(keys, list) else 0
        would_have = 1 if total else 0
        return {
            "summary": {
                "total_events_evaluated": total,
                "would_have_triggered": would_have,
                "trigger_rate": (would_have / total) if total else 0.0,
                "estimated_daily_triggers": 0.0,
                "evaluation_time_ms": 0.0,
            },
            "sample_triggers": [{"timestamp": "2026-01-01T00:00:00Z", "data": {"target_key": keys[0] if total else ""}, "matched_condition": "lt"}] if total else [],
            "near_misses": [],
            "evaluation_mode": "aggregate",
            "requires_wasmcloud": False,
        }


@override_settings(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestAlertTemplateInlinePreview(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="user@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_preview_from_job_id_evaluates_compiled_executable_over_sample_targets(self):
        template_id = uuid.uuid4()
        template_version = 1

        template = _template_spec()
        template["template_id"] = str(template_id)
        template["template_version"] = template_version
        template["fingerprint"] = "sha256:test"
        template["spec_hash"] = "sha256:testspec"

        executable = {"schema_version": "alert_executable_v1", "template": {"template_id": str(template_id), "version": 1}}

        job_id = uuid.uuid4()
        cache_key = f"nlp:proposed_spec:{self.user.id}:{job_id}"
        cache.set(
            cache_key,
            {
                "schema_version": "proposed_spec_v2",
                "job_id": str(job_id),
                "pipeline_id": "dspy_plan_compiler_v1",
                "pipeline_version": "v1",
                "template": template,
                "compiled_executable": executable,
                "required_user_inputs": {"targets_required": True, "target_kind": "wallet", "required_variables": ["threshold"]},
                "human_preview": {"summary": "Balance alert"},
            },
            timeout=3600,
        )

        fake_service = _FakePreviewService()
        with patch("app.views.alert_template_views._get_preview_service", return_value=fake_service):
            resp = self.client.post(
                "/api/alert-templates/preview/",
                data={
                    "job_id": str(job_id),
                    "target_selector": {"mode": "keys", "keys": ["ETH:mainnet:0xaaa", "ETH:mainnet:0xbbb"]},
                    "variable_values": {"threshold": 0.5},
                    "sample_size": 50,
                },
                format="json",
            )

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["success"] is True
        assert payload["summary"]["total_events_evaluated"] == 2
        assert payload["summary"]["would_have_triggered"] == 1
        assert isinstance(payload["sample_triggers"], list)
