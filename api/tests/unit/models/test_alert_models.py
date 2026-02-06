"""
Unit tests for core alert models (AlertTemplate v2, AlertInstance, AlertExecution).
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from app.models.alerts import AlertExecution, AlertInstance
from app.models.groups import GenericGroup, GroupType
from app.models.alert_templates import AlertTemplate
from tests.factories import AlertTemplateFactory, UserFactory


pytestmark = pytest.mark.django_db


def test_alert_template_requires_fingerprint():
    user = UserFactory()
    template = AlertTemplate(
        fingerprint="",
        name="Missing Fingerprint",
        description="",
        target_kind="wallet",
        created_by=user,
    )
    with pytest.raises(ValidationError):
        template.full_clean()


def test_alert_template_variable_names_from_latest_spec():
    user = UserFactory()
    template = AlertTemplateFactory(
        created_by=user,
        variables=[
            {"id": "threshold", "type": "decimal", "required": True, "validation": {"min": 0}},
            {"id": "window_duration", "type": "duration", "required": True, "default": "24h"},
        ],
    )
    assert template.get_variable_names() == ["threshold", "window_duration"]


def test_instance_requires_template_or_standalone():
    user = UserFactory()
    instance = AlertInstance(
        name="Bad Instance",
        nl_description="Bad",
        template=None,
        template_version=None,
        template_params=None,
        _standalone_spec=None,
        event_type="ACCOUNT_EVENT",
        sub_event="CUSTOM",
        user=user,
    )

    with pytest.raises(ValidationError):
        instance.full_clean()


def test_instance_rejects_template_and_standalone():
    user = UserFactory()
    template = AlertTemplateFactory(created_by=user)
    instance = AlertInstance(
        name="Bad Instance",
        nl_description="Bad",
        template=template,
        template_version=1,
        template_params={},
        _standalone_spec={"version": "v1", "trigger": {}, "conditions": {}, "action": {}},
        event_type="ACCOUNT_EVENT",
        sub_event="CUSTOM",
        user=user,
    )

    with pytest.raises(ValidationError):
        instance.full_clean()


def test_instance_rejects_target_group_and_keys():
    user = UserFactory()
    template = AlertTemplateFactory(created_by=user)
    group = GenericGroup.objects.create(
        name="Wallet Group",
        group_type=GroupType.WALLET,
        owner=user,
        member_data={"members": {}},
        member_count=0,
    )

    instance = AlertInstance(
        name="Bad Targeting",
        nl_description="Bad",
        template=template,
        template_version=1,
        template_params={},
        event_type="ACCOUNT_EVENT",
        sub_event="CUSTOM",
        user=user,
        target_group=group,
        target_keys=["ETH:mainnet:0xabcdef000000000000000000000000000000000000"],
    )

    with pytest.raises(ValidationError):
        instance.full_clean()


def test_execution_mark_started_and_completed():
    user = UserFactory()
    template = AlertTemplateFactory(created_by=user)
    instance = AlertInstance.objects.create(
        name="Instance",
        nl_description="Test",
        template=template,
        template_version=1,
        template_params={},
        event_type="ACCOUNT_EVENT",
        sub_event="CUSTOM",
        user=user,
        enabled=True,
    )

    execution = AlertExecution.objects.create(
        alert_instance=instance,
        alert_version=instance.version,
        trigger_mode="event",
        frozen_spec={},
    )

    execution.mark_started()
    execution.refresh_from_db()
    assert execution.status == "running"
    assert execution.started_at is not None

    execution.mark_completed(result_data={"result": True, "result_value": "ok", "metadata": {"k": "v"}})
    execution.refresh_from_db()
    assert execution.status == "completed"
    assert execution.result is True
    assert execution.result_value == "ok"

