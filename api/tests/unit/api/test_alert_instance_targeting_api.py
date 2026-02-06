"""
API tests for AlertInstance targeting fields (target_group vs target_keys).
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from app.models.alerts import AlertInstance
from tests.factories import UserFactory, AlertTemplateFactory
from tests.factories.group_factories import WalletGroupFactory


pytestmark = pytest.mark.django_db


class TestAlertInstanceTargeting:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_create_alert_with_targets_sets_target_keys_normalized(self):
        template = AlertTemplateFactory(created_by=self.user, alert_type='wallet')
        template_version = template.versions.order_by("-template_version").first().template_version

        url = reverse('alerts:alert-list')
        response = self.client.post(
            url,
            {
                "template_id": str(template.id),
                "template_version": int(template_version),
                "name": "My Alert",
                "trigger_type": "event_driven",
                "target_selector": {
                    "mode": "keys",
                    "keys": ["eth:MainNet:0xAbCdEf000000000000000000000000000000000000"],
                },
                "variable_values": {"threshold": 1234.0},
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        alert = AlertInstance.objects.get(id=response.data['id'])
        assert alert.target_group_id is None
        assert alert.target_keys == ['ETH:mainnet:0xabcdef000000000000000000000000000000000000']

    def test_create_alert_with_target_group_sets_target_group(self):
        template = AlertTemplateFactory(created_by=self.user, alert_type='wallet')
        template_version = template.versions.order_by("-template_version").first().template_version
        wallet_group = WalletGroupFactory(owner=self.user)

        url = reverse('alerts:alert-list')
        response = self.client.post(
            url,
            {
                "template_id": str(template.id),
                "template_version": int(template_version),
                "name": "Group Alert",
                "trigger_type": "event_driven",
                "target_selector": {"mode": "group", "group_id": str(wallet_group.id)},
                "variable_values": {"threshold": 100.0},
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        alert = AlertInstance.objects.get(id=response.data['id'])
        assert str(alert.target_group_id) == str(wallet_group.id)
        assert alert.target_keys == []

    def test_create_alert_rejects_keys_and_group_id_simultaneously(self):
        template = AlertTemplateFactory(created_by=self.user, alert_type='wallet')
        template_version = template.versions.order_by("-template_version").first().template_version
        wallet_group = WalletGroupFactory(owner=self.user)

        url = reverse('alerts:alert-list')
        response = self.client.post(
            url,
            {
                "template_id": str(template.id),
                "template_version": int(template_version),
                "name": "Bad Alert",
                "trigger_type": "event_driven",
                "target_selector": {
                    "mode": "keys",
                    "keys": ["ETH:mainnet:0xabcdef000000000000000000000000000000000000"],
                    "group_id": str(wallet_group.id),
                },
                "variable_values": {"threshold": 1.0},
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "target_selector" in response.data
