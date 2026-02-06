"""
Unit tests for AlertInstanceCreateRequestSerializer (vNext template bundles).
"""

import uuid
from unittest.mock import Mock

import pytest

from app.models.alert_templates import AlertTemplate, AlertTemplateVersion
from app.models.groups import GenericGroup, GroupType
from app.serializers import AlertInstanceCreateRequestSerializer


pytestmark = pytest.mark.django_db


def _minimal_template_spec(*, template_id: uuid.UUID, template_version: int) -> dict:
    return {
        "schema_version": "alert_template_v2",
        "template_id": str(template_id),
        "template_version": template_version,
        "name": "Test Template",
        "description": "Test Template",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [{"id": "threshold", "type": "decimal", "label": "Threshold", "required": True}],
        "signals": {"principals": [], "factors": [{"name": "balance_latest", "unit": "WEI", "update_sources": [{"ref": "ducklake.wallet_balance_window"}]}]},
        "derivations": [],
        "trigger": {
            "evaluation_mode": "periodic",
            "condition_ast": {"op": "gt", "left": "balance_latest", "right": "{{threshold}}"},
            "cron_cadence_seconds": 300,
            "dedupe": {"cooldown_seconds": 0, "key_template": "{{instance_id}}:{{target.key}}"},
            "pruning_hints": {"evm": {"tx_type": "any"}},
        },
        "notification": {"title_template": "Test", "body_template": "Test"},
        "fallbacks": [],
        "assumptions": [],
        "fingerprint": "sha256:" + "0" * 64,
        "spec_hash": "sha256:" + "1" * 64,
    }


class TestAlertInstanceCreateRequestSerializer:
    def test_missing_required_variable_is_rejected(self, user):
        template_id = uuid.uuid4()
        template = AlertTemplate.objects.create(
            id=template_id,
            fingerprint="sha256:" + "a" * 64,
            name="Param Template",
            description="Param template",
            target_kind="wallet",
            created_by=user,
        )
        spec = _minimal_template_spec(template_id=template_id, template_version=1)
        AlertTemplateVersion.objects.create(
            template=template,
            template_version=1,
            template_spec=spec,
            spec_hash=spec["spec_hash"],
            executable_id=uuid.uuid4(),
            executable={},
            registry_snapshot_kind="datasource_catalog",
            registry_snapshot_version="v1",
            registry_snapshot_hash="sha256:" + "2" * 64,
        )

        serializer = AlertInstanceCreateRequestSerializer(
            data={
                "template_id": str(template.id),
                "template_version": 1,
                "trigger_type": "periodic",
                "trigger_config": {"cron": "*/5 * * * *", "timezone": "UTC"},
                "target_selector": {"mode": "keys", "keys": ["ETH:mainnet:0x742d35cc6634c0532925a3b844bc9e7595f12345"]},
                "variable_values": {},
            },
            context={"request": Mock(user=user)},
        )
        assert not serializer.is_valid()
        assert "variable_values" in serializer.errors

    def test_group_targeting_validates_group_type(self, user):
        template_id = uuid.uuid4()
        template = AlertTemplate.objects.create(
            id=template_id,
            fingerprint="sha256:" + "b" * 64,
            name="Wallet template",
            description="Wallet template",
            target_kind="wallet",
            created_by=user,
        )
        spec = _minimal_template_spec(template_id=template_id, template_version=1)
        AlertTemplateVersion.objects.create(
            template=template,
            template_version=1,
            template_spec=spec,
            spec_hash=spec["spec_hash"],
            executable_id=uuid.uuid4(),
            executable={},
            registry_snapshot_kind="datasource_catalog",
            registry_snapshot_version="v1",
            registry_snapshot_hash="sha256:" + "3" * 64,
        )

        wrong_group = GenericGroup.objects.create(
            name="Network Group",
            group_type=GroupType.NETWORK,
            owner=user,
            member_data={"members": {"ETH:mainnet": {"enabled": True}}},
            member_count=1,
        )

        serializer = AlertInstanceCreateRequestSerializer(
            data={
                "template_id": str(template.id),
                "template_version": 1,
                "trigger_type": "periodic",
                "trigger_config": {"cron": "*/5 * * * *", "timezone": "UTC"},
                "target_selector": {"mode": "group", "group_id": str(wrong_group.id)},
                "variable_values": {"threshold": 1.0},
            },
            context={"request": Mock(user=user)},
        )
        assert not serializer.is_valid()
        assert "target_selector" in serializer.errors

    def test_notification_overrides_are_accepted(self, user):
        template_id = uuid.uuid4()
        template = AlertTemplate.objects.create(
            id=template_id,
            fingerprint="sha256:" + "c" * 64,
            name="Notification Template",
            description="Notification template",
            target_kind="wallet",
            created_by=user,
        )
        spec = _minimal_template_spec(template_id=template_id, template_version=1)
        AlertTemplateVersion.objects.create(
            template=template,
            template_version=1,
            template_spec=spec,
            spec_hash=spec["spec_hash"],
            executable_id=uuid.uuid4(),
            executable={},
            registry_snapshot_kind="datasource_catalog",
            registry_snapshot_version="v1",
            registry_snapshot_hash="sha256:" + "4" * 64,
        )

        serializer = AlertInstanceCreateRequestSerializer(
            data={
                "template_id": str(template.id),
                "template_version": 1,
                "trigger_type": "event_driven",
                "trigger_config": {"networks": ["ETH:mainnet"]},
                "target_selector": {"mode": "keys", "keys": ["ETH:mainnet:0x742d35cc6634c0532925a3b844bc9e7595f12345"]},
                "variable_values": {"threshold": 1.0},
                "notification_overrides": {"title_template": "Custom title", "body_template": "Custom body"},
            },
            context={"request": Mock(user=user)},
        )
        assert serializer.is_valid()
        assert serializer.validated_data.get("_notification_overrides") == {
            "title_template": "Custom title",
            "body_template": "Custom body",
        }
