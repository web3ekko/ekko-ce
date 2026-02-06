"""
End-to-end tests for alert creation validation (template-v2-first).
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from app.models.alerts import AlertInstance
from app.models.groups import GenericGroup, GroupType
from tests.factories import AlertTemplateFactory

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="testuser@example.com",
        first_name="Test",
        last_name="User",
        password="testpass123",
    )


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def wallet_group(user):
    return GenericGroup.objects.create(
        group_type=GroupType.WALLET,
        name="My Wallets",
        owner=user,
        member_data={"members": {}},
        member_count=0,
    )


@pytest.fixture
def threshold_template(user):
    return AlertTemplateFactory(
        created_by=user,
        is_public=True,
        alert_type="wallet",
        variables=[
            {
                "id": "threshold",
                "type": "decimal",
                "label": "Threshold",
                "required": True,
                "validation": {"min": 0, "max": 1000000},
            }
        ],
    )


@pytest.fixture
def enum_template(user):
    return AlertTemplateFactory(
        created_by=user,
        is_public=True,
        alert_type="wallet",
        variables=[
            {
                "id": "priority",
                "type": "enum",
                "label": "Priority",
                "required": True,
                "validation": {"options": ["low", "normal", "high"]},
            }
        ],
    )


pytestmark = pytest.mark.django_db


class TestAlertCreationE2E:
    def test_create_wallet_alert_defaults_type(self, authenticated_client, threshold_template):
        template_version = threshold_template.versions.order_by("-template_version").first().template_version
        response = authenticated_client.post(
            "/api/alerts/",
            data={
                "template_id": str(threshold_template.id),
                "template_version": int(template_version),
                "name": "Default Type Alert",
                "trigger_type": "event_driven",
                "target_selector": {
                    "mode": "keys",
                    "keys": ["eth:MainNet:0xAbCdEf000000000000000000000000000000000000"],
                },
                "variable_values": {"threshold": 10},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        alert = AlertInstance.objects.get(id=response.data["id"])
        assert alert.alert_type == "wallet"
        assert alert.target_keys == ["ETH:mainnet:0xabcdef000000000000000000000000000000000000"]

    def test_rejects_target_group_and_targets(self, authenticated_client, wallet_group, threshold_template):
        template_version = threshold_template.versions.order_by("-template_version").first().template_version
        response = authenticated_client.post(
            "/api/alerts/",
            data={
                "template_id": str(threshold_template.id),
                "template_version": int(template_version),
                "name": "Bad Targeting",
                "trigger_type": "event_driven",
                "target_selector": {
                    "mode": "keys",
                    "keys": ["ETH:mainnet:0xabcdef000000000000000000000000000000000000"],
                    "group_id": str(wallet_group.id),
                },
                "variable_values": {"threshold": 10},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "target_selector" in response.data

    def test_template_required_param_enforced(self, authenticated_client, threshold_template):
        template_version = threshold_template.versions.order_by("-template_version").first().template_version
        response = authenticated_client.post(
            "/api/alerts/",
            data={
                "template_id": str(threshold_template.id),
                "template_version": int(template_version),
                "name": "Missing Param",
                "trigger_type": "event_driven",
                "target_selector": {
                    "mode": "keys",
                    "keys": ["ETH:mainnet:0xabcdef000000000000000000000000000000000000"],
                },
                "variable_values": {},
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "variable_values" in response.data

        ok = authenticated_client.post(
            "/api/alerts/",
            data={
                "template_id": str(threshold_template.id),
                "template_version": int(template_version),
                "name": "Ok Param",
                "trigger_type": "event_driven",
                "target_selector": {
                    "mode": "keys",
                    "keys": ["ETH:mainnet:0xabcdef000000000000000000000000000000000000"],
                },
                "variable_values": {"threshold": 10},
            },
            format="json",
        )
        assert ok.status_code == status.HTTP_201_CREATED, ok.data

    def test_enum_param_validation(self, authenticated_client, enum_template):
        template_version = enum_template.versions.order_by("-template_version").first().template_version
        bad = authenticated_client.post(
            "/api/alerts/",
            data={
                "template_id": str(enum_template.id),
                "template_version": int(template_version),
                "name": "Bad Enum",
                "trigger_type": "event_driven",
                "target_selector": {
                    "mode": "keys",
                    "keys": ["ETH:mainnet:0xabcdef000000000000000000000000000000000000"],
                },
                "variable_values": {"priority": "urgent"},
            },
            format="json",
        )
        assert bad.status_code == status.HTTP_400_BAD_REQUEST
        assert "variable_values" in bad.data

        ok = authenticated_client.post(
            "/api/alerts/",
            data={
                "template_id": str(enum_template.id),
                "template_version": int(template_version),
                "name": "Ok Enum",
                "trigger_type": "event_driven",
                "target_selector": {
                    "mode": "keys",
                    "keys": ["ETH:mainnet:0xabcdef000000000000000000000000000000000000"],
                },
                "variable_values": {"priority": "high"},
            },
            format="json",
        )
        assert ok.status_code == status.HTTP_201_CREATED, ok.data

    def test_template_validation_schema_endpoint(self, authenticated_client, threshold_template):
        response = authenticated_client.get(f"/api/alert-templates/{threshold_template.id}/latest/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data.get("success") is True
        assert response.data.get("template", {}).get("id") == str(threshold_template.id)
        assert isinstance(response.data.get("bundle"), dict)
        bundle = response.data.get("bundle") or {}
        assert "template_spec" in bundle
        assert "executable" in bundle
