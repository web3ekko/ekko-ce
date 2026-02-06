"""
PRD-driven tests for AlertTemplate marketplace/listing/read views (vNext).

Authoritative PRDs:
- /docs/prd/apps/api/PRD-Alert-System-USDT.md
- /docs/prd/schemas/SCHEMA-AlertTemplate.md
"""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from app.models.alert_templates import AlertTemplate, AlertTemplateVersion
from app.services.alert_templates.compilation import CompileContext, compile_template_to_executable
from app.services.alert_templates.hashing import compute_template_fingerprint, compute_template_spec_hash
from app.services.alert_templates.registry_snapshot import get_registry_snapshot

User = get_user_model()


def _minimal_alert_template_spec() -> dict:
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
                            "ref": "ducklake.wallet_balance_window",
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
            "pruning_hints": {
                "evm": {
                    "tx_type": "any",
                }
            },
        },
        "notification": {"title_template": "Balance alert: {{target.short}}", "body_template": "Balance: {{balance_latest}}"},
        "fallbacks": [],
        "assumptions": [],
    }


@override_settings(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestAlertTemplateMarketplaceViews(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="user@example.com", password="testpass123")
        self.other = User.objects.create_user(email="other@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_templates_includes_public_marketplace_templates_with_summary_fields(self):
        template_spec = _minimal_alert_template_spec()
        fingerprint = compute_template_fingerprint(dict(template_spec))

        template_id = uuid.uuid4()
        template_version = 1
        to_persist = dict(template_spec)
        to_persist["template_id"] = str(template_id)
        to_persist["template_version"] = template_version
        to_persist["fingerprint"] = fingerprint
        to_persist["spec_hash"] = ""
        spec_hash = compute_template_spec_hash(to_persist)
        to_persist["spec_hash"] = spec_hash

        snapshot = get_registry_snapshot()
        executable = compile_template_to_executable(
            to_persist,
            ctx=CompileContext(template_id=template_id, template_version=template_version, registry_snapshot=snapshot),
        )

        template = AlertTemplate.objects.create(
            id=template_id,
            fingerprint=fingerprint,
            name="Marketplace template",
            description="Same semantics",
            target_kind="wallet",
            is_public=True,
            is_verified=False,
            created_by=self.other,
        )
        AlertTemplateVersion.objects.create(
            template=template,
            template_version=template_version,
            template_spec=to_persist,
            spec_hash=spec_hash,
            executable_id=uuid.UUID(executable["executable_id"]),
            executable=executable,
            registry_snapshot_kind=str(snapshot.get("kind") or "datasource_catalog"),
            registry_snapshot_version=str(snapshot.get("version") or "v1"),
            registry_snapshot_hash=str(snapshot.get("hash") or ""),
        )

        resp = self.client.get("/api/alert-templates/?is_public=true")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["count"] == 1
        item = payload["results"][0]
        assert item["id"] == str(template_id)
        assert item["latest_template_version"] == 1
        assert "threshold" in item["variable_names"]
        assert item["scope_networks"] == ["ETH:mainnet"]

    def test_latest_endpoint_returns_bundle(self):
        template_spec = _minimal_alert_template_spec()
        fingerprint = compute_template_fingerprint(dict(template_spec))

        template_id = uuid.uuid4()
        template_version = 1
        to_persist = dict(template_spec)
        to_persist["template_id"] = str(template_id)
        to_persist["template_version"] = template_version
        to_persist["fingerprint"] = fingerprint
        to_persist["spec_hash"] = ""
        spec_hash = compute_template_spec_hash(to_persist)
        to_persist["spec_hash"] = spec_hash

        snapshot = get_registry_snapshot()
        executable = compile_template_to_executable(
            to_persist,
            ctx=CompileContext(template_id=template_id, template_version=template_version, registry_snapshot=snapshot),
        )

        template = AlertTemplate.objects.create(
            id=template_id,
            fingerprint=fingerprint,
            name="Marketplace template",
            description="Same semantics",
            target_kind="wallet",
            is_public=True,
            is_verified=False,
            created_by=self.other,
        )
        AlertTemplateVersion.objects.create(
            template=template,
            template_version=template_version,
            template_spec=to_persist,
            spec_hash=spec_hash,
            executable_id=uuid.UUID(executable["executable_id"]),
            executable=executable,
            registry_snapshot_kind=str(snapshot.get("kind") or "datasource_catalog"),
            registry_snapshot_version=str(snapshot.get("version") or "v1"),
            registry_snapshot_hash=str(snapshot.get("hash") or ""),
        )

        resp = self.client.get(f"/api/alert-templates/{template_id}/latest/")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["success"] is True
        assert payload["template"]["id"] == str(template_id)
        assert payload["bundle"]["template_version"] == 1
        assert payload["bundle"]["template_spec"]["schema_version"] == "alert_template_v2"
        assert payload["bundle"]["executable"]["schema_version"] == "alert_executable_v1"
