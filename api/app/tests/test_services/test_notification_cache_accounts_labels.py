import json

import pytest

from app.models.groups import GenericGroup, GroupType, SYSTEM_GROUP_ACCOUNTS
from app.services.notification_cache import NotificationCacheManager


pytestmark = pytest.mark.django_db


class _FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self._store[key] = value

    def get(self, key: str):
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


def test_cache_accounts_wallet_labels_builds_address_map(user):
    accounts = GenericGroup.objects.create(
        group_type=GroupType.WALLET,
        name="Accounts",
        owner=user,
        settings={"system_key": SYSTEM_GROUP_ACCOUNTS, "visibility": "private"},
        member_data={
            "members": {
                "ETH:mainnet:0xabcdef000000000000000000000000000000000000": {"label": "Treasury"},
                "ETH:mainnet:0x1111111111111111111111111111111111111111": {"label": ""},
            }
        },
    )
    assert accounts.settings["system_key"] == SYSTEM_GROUP_ACCOUNTS

    fake_redis = _FakeRedis()
    cache = NotificationCacheManager(redis_client=fake_redis)

    labels = cache.cache_accounts_wallet_labels(str(user.id))
    assert labels == {"ETH:mainnet:0xabcdef000000000000000000000000000000000000": "Treasury"}

    stored = fake_redis.get(f"user:wallet_labels:{user.id}")
    assert stored is not None
    assert json.loads(stored) == labels


def test_cache_accounts_wallet_labels_deletes_key_when_no_accounts_group(user):
    fake_redis = _FakeRedis()
    fake_redis.set(f"user:wallet_labels:{user.id}", json.dumps({"0xabc": "Old"}))

    cache = NotificationCacheManager(redis_client=fake_redis)
    labels = cache.cache_accounts_wallet_labels(str(user.id))

    assert labels == {}
    assert fake_redis.get(f"user:wallet_labels:{user.id}") is None
