from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.alert_runtime_projection import (
    AlertRuntimeProjection,
    EVENT_IDX_GROUP_INSTANCES_PREFIX,
    EVENT_IDX_TARGET_INSTANCES_PREFIX,
    EXECUTABLE_KEY_PREFIX,
    INSTANCE_KEY_PREFIX,
    NOTIFICATION_OVERRIDE_KEY,
)


class MockPipeline:
    def __init__(self) -> None:
        self.commands: list[tuple] = []

    def sadd(self, key, *values):
        self.commands.append(("sadd", key, list(values)))
        return self

    def srem(self, key, *values):
        self.commands.append(("srem", key, list(values)))
        return self

    def set(self, key, value):
        self.commands.append(("set", key, value))
        return self

    def delete(self, key):
        self.commands.append(("delete", key))
        return self

    def zrem(self, key, *values):
        self.commands.append(("zrem", key, list(values)))
        return self

    def execute(self):
        self.commands.append(("execute",))
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _make_instance(
    *,
    instance_id: str,
    enabled: bool,
    user_id: int,
    template_id: str,
    template_version: int,
    name: str = "Alert Name",
    nl_description: str = "Alert description",
    trigger_type: str = "event_driven",
    trigger_config: dict | None = None,
    target_keys: list[str] | None = None,
    target_group_id: str | None = None,
    template_params: dict | None = None,
    priority: str = "normal",
) -> MagicMock:
    inst = MagicMock()
    inst.id = instance_id
    inst.enabled = enabled
    inst.user_id = user_id
    inst.template_id = template_id
    inst.template_version = template_version
    inst.name = name
    inst.nl_description = nl_description
    inst.trigger_type = trigger_type
    inst.trigger_config = trigger_config or {}
    inst.target_keys = target_keys or []
    inst.target_group_id = target_group_id
    inst.template_params = template_params or {}
    inst.get_priority.return_value = priority
    return inst


@pytest.fixture()
def redis_mock():
    mock = MagicMock()
    mock.pipeline.return_value = MockPipeline()
    return mock


def test_project_instance_keys_mode_updates_target_instance_sets(redis_mock):
    template_id = str(uuid4())
    instance_id = str(uuid4())
    template_version = 1

    executable_spec = {
        "schema_version": "alert_executable_v1",
        "notification_template": {"title": "hello", "body": "world"},
        "action": {"cooldown_secs": 60, "dedupe_key_template": "{{run_id}}"},
    }

    instance = _make_instance(
        instance_id=instance_id,
        enabled=True,
        user_id=123,
        template_id=template_id,
        template_version=template_version,
        target_keys=["ETH:mainnet:0xabc", "ETH:mainnet:0xdef"],
    )

    def redis_get_side_effect(key: str):
        if key == f"{EXECUTABLE_KEY_PREFIX}{template_id}:{template_version}":
            return json.dumps(executable_spec)
        if key == f"{INSTANCE_KEY_PREFIX}{instance_id}":
            return None
        return None

    redis_mock.get.side_effect = redis_get_side_effect

    with patch("app.services.alert_runtime_projection._redis_client", return_value=redis_mock):
        proj = AlertRuntimeProjection()
        proj.project_instance(instance)

    pipeline: MockPipeline = redis_mock.pipeline.return_value
    assert ("sadd", f"{EVENT_IDX_TARGET_INSTANCES_PREFIX}ETH:mainnet:0xabc", [instance_id]) in pipeline.commands
    assert ("sadd", f"{EVENT_IDX_TARGET_INSTANCES_PREFIX}ETH:mainnet:0xdef", [instance_id]) in pipeline.commands

    set_cmd = next(cmd for cmd in pipeline.commands if cmd[0] == "set" and cmd[1] == f"{INSTANCE_KEY_PREFIX}{instance_id}")
    snapshot = json.loads(set_cmd[2])
    assert snapshot["template_id"] == template_id
    assert snapshot["template_version"] == template_version
    assert snapshot["alert_name"] == "Alert Name"
    assert snapshot["target_selector"]["mode"] == "keys"
    assert snapshot["target_selector"]["keys"] == ["ETH:mainnet:0xabc", "ETH:mainnet:0xdef"]
    assert snapshot["notification_template"] == executable_spec["notification_template"]


def test_project_instance_group_mode_updates_group_instance_set(redis_mock):
    template_id = str(uuid4())
    instance_id = str(uuid4())
    group_id = str(uuid4())
    template_version = 1

    executable_spec = {"schema_version": "alert_executable_v1", "notification_template": {"title": "t", "body": "b"}, "action": {}}
    instance = _make_instance(
        instance_id=instance_id,
        enabled=True,
        user_id=123,
        template_id=template_id,
        template_version=template_version,
        target_group_id=group_id,
    )

    def redis_get_side_effect(key: str):
        if key == f"{EXECUTABLE_KEY_PREFIX}{template_id}:{template_version}":
            return json.dumps(executable_spec)
        if key == f"{INSTANCE_KEY_PREFIX}{instance_id}":
            return None
        return None

    redis_mock.get.side_effect = redis_get_side_effect

    with patch("app.services.alert_runtime_projection._redis_client", return_value=redis_mock):
        proj = AlertRuntimeProjection()
        proj.project_instance(instance)

    pipeline: MockPipeline = redis_mock.pipeline.return_value
    assert ("sadd", f"{EVENT_IDX_GROUP_INSTANCES_PREFIX}{group_id}", [instance_id]) in pipeline.commands


def test_project_instance_normalizes_notification_template(redis_mock):
    template_id = str(uuid4())
    instance_id = str(uuid4())
    template_version = 1

    executable_spec = {"schema_version": "alert_executable_v1", "notification_template": {"title": "", "body": ""}, "action": {}}
    instance = _make_instance(
        instance_id=instance_id,
        enabled=True,
        user_id=123,
        template_id=template_id,
        template_version=template_version,
        name="",
        nl_description="Alert me when my wallet has more than 2 transactions in the last 24 hours on Ethereum",
        target_keys=["ETH:mainnet:0xabc"],
    )

    def redis_get_side_effect(key: str):
        if key == f"{EXECUTABLE_KEY_PREFIX}{template_id}:{template_version}":
            return json.dumps(executable_spec)
        if key == f"{INSTANCE_KEY_PREFIX}{instance_id}":
            return None
        return None

    redis_mock.get.side_effect = redis_get_side_effect

    with patch("app.services.alert_runtime_projection._redis_client", return_value=redis_mock):
        proj = AlertRuntimeProjection()
        proj.project_instance(instance)

    pipeline: MockPipeline = redis_mock.pipeline.return_value
    set_cmd = next(cmd for cmd in pipeline.commands if cmd[0] == "set" and cmd[1] == f"{INSTANCE_KEY_PREFIX}{instance_id}")
    snapshot = json.loads(set_cmd[2])
    assert snapshot["notification_template"]["title"] == "Alert triggered: {{target.short}}"
    assert snapshot["notification_template"]["body"] == "Condition met for {{target.short}}."


def test_project_instance_applies_notification_overrides(redis_mock):
    template_id = str(uuid4())
    instance_id = str(uuid4())
    template_version = 1

    executable_spec = {
        "schema_version": "alert_executable_v1",
        "notification_template": {"title": "Default title", "body": "Default body"},
        "action": {},
    }
    instance = _make_instance(
        instance_id=instance_id,
        enabled=True,
        user_id=123,
        template_id=template_id,
        template_version=template_version,
        template_params={
            NOTIFICATION_OVERRIDE_KEY: {
                "title_template": "Custom title",
                "body_template": "Custom body",
            }
        },
        target_keys=["ETH:mainnet:0xabc"],
    )

    def redis_get_side_effect(key: str):
        if key == f"{EXECUTABLE_KEY_PREFIX}{template_id}:{template_version}":
            return json.dumps(executable_spec)
        if key == f"{INSTANCE_KEY_PREFIX}{instance_id}":
            return None
        return None

    redis_mock.get.side_effect = redis_get_side_effect

    with patch("app.services.alert_runtime_projection._redis_client", return_value=redis_mock):
        proj = AlertRuntimeProjection()
        proj.project_instance(instance)

    pipeline: MockPipeline = redis_mock.pipeline.return_value
    set_cmd = next(cmd for cmd in pipeline.commands if cmd[0] == "set" and cmd[1] == f"{INSTANCE_KEY_PREFIX}{instance_id}")
    snapshot = json.loads(set_cmd[2])
    assert snapshot["notification_template"]["title"] == "Custom title"
    assert snapshot["notification_template"]["body"] == "Custom body"
