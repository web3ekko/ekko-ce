import json
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.services.group_service import (
    ALERT_RUNTIME_GROUP_PARTITIONS_PREFIX,
    ALERT_RUNTIME_GROUP_TARGETS_PREFIX,
    ALERT_RUNTIME_TARGET_GROUPS_PREFIX,
    GroupService,
)


class MockPipeline:
    def __init__(self) -> None:
        self.commands: list[tuple] = []

    def delete(self, key):
        self.commands.append(("delete", key))
        return self

    def sadd(self, key, *values):
        self.commands.append(("sadd", key, list(values)))
        return self

    def srem(self, key, *values):
        self.commands.append(("srem", key, list(values)))
        return self

    def set(self, key, value):
        self.commands.append(("set", key, value))
        return self

    def execute(self):
        self.commands.append(("execute",))
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture()
def redis_mock():
    mock = MagicMock()
    mock.pipeline.return_value = MockPipeline()
    return mock


def _partition_set_key(group_id: UUID, network: str, subnet: str) -> str:
    return f"{ALERT_RUNTIME_GROUP_TARGETS_PREFIX}{group_id}:{network}:{subnet}"


def _partitions_index_key(group_id: UUID) -> str:
    return f"{ALERT_RUNTIME_GROUP_PARTITIONS_PREFIX}{group_id}"


def test_rebuild_group_cache_updates_alert_runtime_indices(redis_mock):
    group_id = uuid4()
    removed = "ETH:mainnet:0xold"
    kept = "ETH:mainnet:0xkeep"
    added = "ETH:mainnet:0xnew"

    group = MagicMock()
    group.id = group_id
    group.group_type = "wallet"
    group.owner_id = 123
    group.member_data = {"members": {kept: {}, added: {}}}

    existing_partition_key = _partition_set_key(group_id, "ETH", "mainnet")

    def smembers_side_effect(key: str):
        if key == f"group:{group_id}:members":
            return {removed, kept}
        if key == _partitions_index_key(group_id):
            return {existing_partition_key}
        return set()

    redis_mock.smembers.side_effect = smembers_side_effect

    with (
        patch("app.services.group_service.redis.from_url", return_value=redis_mock),
        patch("app.services.group_service.settings.CACHES", {"default": {"LOCATION": "redis://test"}}),
        patch("app.models.groups.GenericGroup.objects.get", return_value=group),
    ):
        service = GroupService()
        service.rebuild_group_redis_cache(group_id)

    pipeline: MockPipeline = redis_mock.pipeline.return_value

    assert ("srem", f"member:{removed}:groups", [str(group_id)]) in pipeline.commands
    assert ("srem", f"{ALERT_RUNTIME_TARGET_GROUPS_PREFIX}{removed}", [str(group_id)]) in pipeline.commands

    assert ("sadd", f"member:{kept}:groups", [str(group_id)]) in pipeline.commands
    assert ("sadd", f"{ALERT_RUNTIME_TARGET_GROUPS_PREFIX}{kept}", [str(group_id)]) in pipeline.commands

    assert ("delete", existing_partition_key) in pipeline.commands
    assert ("delete", _partitions_index_key(group_id)) in pipeline.commands

    partition_cmd = ("sadd", _partition_set_key(group_id, "ETH", "mainnet"), [kept])
    assert partition_cmd in pipeline.commands or (
        "sadd",
        _partition_set_key(group_id, "ETH", "mainnet"),
        [added],
    ) in pipeline.commands

    index_set_cmd = next(
        cmd
        for cmd in pipeline.commands
        if cmd[0] == "sadd" and cmd[1] == _partitions_index_key(group_id)
    )
    assert existing_partition_key in index_set_cmd[2] or _partition_set_key(group_id, "ETH", "mainnet") in index_set_cmd[2]
