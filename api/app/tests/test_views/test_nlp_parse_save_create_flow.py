"""
PRD-driven tests for the NLP Parse -> Save Template -> Create Instance flow (vNext).
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from app.models.alert_templates import AlertTemplate, AlertTemplateVersion
from app.models.alerts import AlertInstance
from app.services.alert_templates.hashing import compute_template_fingerprint
from app.services.nlp.pipelines import DEFAULT_PIPELINE_ID

User = get_user_model()


def _minimal_alert_template_v2() -> dict:
    return {
        "schema_version": "alert_template_v2",
        "name": "Balance alert (window)",
        "description": "Alert when balance drops below threshold",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [
            {
                "id": "threshold",
                "type": "decimal",
                "label": "Threshold",
                "description": "Threshold value",
                "required": True,
                "default": 0.5,
                "validation": {"min": 0},
            }
        ],
        "signals": {
            "principals": [],
            "factors": [
                {
                    "name": "balance_latest",
                    "unit": "WEI",
                    "update_sources": [{"ref": "ducklake.wallet_balance_window"}],
                }
            ],
        },
        "derivations": [],
        "trigger": {
            "evaluation_mode": "periodic",
            "condition_ast": {"op": "lt", "left": "balance_latest", "right": "{{threshold}}"},
            "cron_cadence_seconds": 300,
            "dedupe": {"cooldown_seconds": 300, "key_template": "{{instance_id}}:{{target.key}}"},
            "pruning_hints": {"evm": {"tx_type": "any"}},
        },
        "notification": {"title_template": "Balance alert: {{target.short}}", "body_template": "Balance: {{balance_latest}}"},
        "fallbacks": [],
        "assumptions": [],
    }


def _proposed_spec_v2(job_id: str) -> dict:
    template = _minimal_alert_template_v2()
    fingerprint = compute_template_fingerprint(template)
    return {
        "schema_version": "proposed_spec_v2",
        "job_id": job_id,
        "expires_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        "pipeline_id": DEFAULT_PIPELINE_ID,
        "pipeline_version": "v1",
        "template": template,
        "compiled_executable": {},
        "compile_report": {"registry_snapshot": {}, "selected_catalog_ids": [], "fallbacks_used": [], "errors": []},
        "required_user_inputs": {
            "targets_required": True,
            "target_kind": "wallet",
            "required_variables": ["threshold"],
            "suggested_defaults": {"threshold": 0.5},
            "supported_trigger_types": ["periodic"],
        },
        "human_preview": {"summary": "Alert when balance drops below threshold", "segments": []},
        "fingerprint_candidate": fingerprint,
        "warnings": [],
    }


@override_settings(
    GEMINI_API_KEY="test",
    NLP_ENABLED=True,
    NLP_PROPOSED_SPEC_TTL_SECS=3600,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestNLPParseSaveCreateFlow(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("app.tasks.nlp_tasks.parse_nl_description")
    def test_parse_enqueues_and_does_not_persist(self, mock_task):
        response = self.client.post(
            "/api/alerts/parse/",
            {"nl_description": "Alert when any wallet balance drops below 0.5 ETH"},
            format="json",
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        payload = response.json()
        assert payload["success"] is True
        assert payload["status"] == "queued"
        assert "job_id" in payload
        assert "expires_at" in payload

        mock_task.enqueue.assert_called_once()
        enqueue_kwargs = mock_task.enqueue.call_args.kwargs
        assert enqueue_kwargs["user_id"] == str(self.user.id)
        assert enqueue_kwargs["job_id"] == payload["job_id"]
        assert len(enqueue_kwargs["nl_description"]) <= 500
        assert enqueue_kwargs["pipeline_id"] == DEFAULT_PIPELINE_ID

        assert AlertTemplate.objects.count() == 0
        assert AlertInstance.objects.count() == 0

    def test_save_template_returns_expired_when_cache_missing(self):
        response = self.client.post(
            "/api/alert-templates/",
            {"job_id": str(uuid.uuid4())},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["code"] == "proposed_spec_expired"

    def test_save_template_is_idempotent_by_fingerprint(self):
        job_id = str(uuid.uuid4())
        cache_key = f"nlp:proposed_spec:{self.user.id}:{job_id}"
        cache.set(cache_key, _proposed_spec_v2(job_id), timeout=3600)

        first = self.client.post("/api/alert-templates/", {"job_id": job_id}, format="json")
        assert first.status_code == status.HTTP_201_CREATED
        first_payload = first.json()
        assert first_payload["success"] is True
        assert AlertTemplate.objects.count() == 1
        assert AlertTemplateVersion.objects.count() == 1

        second = self.client.post("/api/alert-templates/", {"job_id": job_id}, format="json")
        assert second.status_code == status.HTTP_200_OK
        second_payload = second.json()
        assert second_payload["template_id"] == first_payload["template_id"]
        assert AlertTemplate.objects.count() == 1
        assert AlertTemplateVersion.objects.count() == 1

    def test_save_template_detects_marketplace_duplicate(self):
        other = User.objects.create_user(email="other@example.com", password="testpass123")

        template_spec = _minimal_alert_template_v2()
        fp = compute_template_fingerprint(template_spec)
        marketplace = AlertTemplate.objects.create(
            fingerprint=fp,
            name="Marketplace version",
            description="Same semantics",
            target_kind="wallet",
            is_public=True,
            is_verified=False,
            created_by=other,
        )
        AlertTemplateVersion.objects.create(
            template=marketplace,
            template_version=1,
            template_spec={"schema_version": "alert_template_v2"},
            spec_hash="sha256:" + "0" * 64,
            executable_id=uuid.uuid4(),
            executable={},
            registry_snapshot_kind="datasource_catalog",
            registry_snapshot_version="v1",
            registry_snapshot_hash="sha256:" + "1" * 64,
        )

        job_id = str(uuid.uuid4())
        cache_key = f"nlp:proposed_spec:{self.user.id}:{job_id}"
        cache.set(cache_key, _proposed_spec_v2(job_id), timeout=3600)

        response = self.client.post("/api/alert-templates/", {"job_id": job_id}, format="json")
        assert response.status_code == status.HTTP_409_CONFLICT
        body = response.json()
        assert body["code"] == "marketplace_template_exists"
        assert AlertTemplate.objects.count() == 1

    def test_create_instance_from_saved_template(self):
        job_id = str(uuid.uuid4())
        cache_key = f"nlp:proposed_spec:{self.user.id}:{job_id}"
        cache.set(cache_key, _proposed_spec_v2(job_id), timeout=3600)

        saved = self.client.post("/api/alert-templates/", {"job_id": job_id}, format="json")
        assert saved.status_code == status.HTTP_201_CREATED
        saved_payload = saved.json()

        template_id = saved_payload["template_id"]
        template_version = saved_payload["template_version"]

        created = self.client.post(
            "/api/alert-instances/",
            {
                "template_id": template_id,
                "template_version": template_version,
                "name": "Customer wallets: balance drop",
                "enabled": True,
                "trigger_type": "periodic",
                "trigger_config": {"cron": "*/5 * * * *", "timezone": "UTC", "data_lag_secs": 120},
                "target_selector": {"mode": "keys", "keys": ["ETH:mainnet:0x742d35cc6634c0532925a3b8d4c9db96c4b4d8b"]},
                "variable_values": {"threshold": 0.5},
            },
            format="json",
        )
        assert created.status_code == status.HTTP_201_CREATED
        assert AlertInstance.objects.count() == 1
        instance = AlertInstance.objects.first()
        assert str(instance.template_id) == template_id
        assert int(instance.template_version) == int(template_version)

