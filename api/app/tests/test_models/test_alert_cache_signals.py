from __future__ import annotations

import pytest

from app.models.alerts import AlertInstance


pytestmark = pytest.mark.django_db


def _patch_signal_dependencies(monkeypatch, calls):
    class FakeAlertCacheManager:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def sync_alert_to_redis(self, instance) -> None:
            calls.append(("sync", str(instance.id)))

        def remove_alert_from_redis(self, alert_id: str) -> None:
            calls.append(("remove", str(alert_id)))

    class FakeNotificationCacheManager:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def add_subscriber_to_template(self, template_id: str, user_id: str) -> None:
            return None

        def remove_subscriber_from_template(self, template_id: str, user_id: str) -> None:
            return None

    class FakeAlertRuntimeProjection:
        def project_template(self, template) -> None:
            return None

        def project_instance(self, instance) -> None:
            return None

        def remove_instance(self, instance_id: str) -> None:
            return None

    class FakeGroupService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def sync_alert_targets_to_redis(self, instance) -> None:
            calls.append(("group_sync", str(instance.id)))

        @classmethod
        def remove_alert_targets_from_redis(cls, alert_id: str, user_id: str | None = None) -> None:
            calls.append(("group_remove", str(alert_id)))

    import app.services.alert_cache as alert_cache
    import app.services.notification_cache as notification_cache
    import app.services.alert_runtime_projection as alert_runtime_projection
    import app.services.group_service as group_service

    monkeypatch.setattr(alert_cache, "AlertCacheManager", FakeAlertCacheManager)
    monkeypatch.setattr(notification_cache, "NotificationCacheManager", FakeNotificationCacheManager)
    monkeypatch.setattr(alert_runtime_projection, "AlertRuntimeProjection", FakeAlertRuntimeProjection)
    monkeypatch.setattr(group_service, "GroupService", FakeGroupService)


def _create_instance(user, sample_alert_template, target_keys=None, enabled=True):
    latest = sample_alert_template.versions.order_by("-template_version").first()
    template_version = int(getattr(latest, "template_version", 1) or 1)
    event_type_map = {
        "wallet": "ACCOUNT_EVENT",
        "token": "ASSET_EVENT",
        "contract": "CONTRACT_INTERACTION",
        "network": "PROTOCOL_EVENT",
        "protocol": "DEFI_EVENT",
        "nft": "ASSET_EVENT",
    }
    return AlertInstance.objects.create(
        name="Signal Test Alert",
        nl_description="Signal test alert",
        template=sample_alert_template,
        template_version=template_version,
        template_params={},
        event_type=event_type_map.get("wallet", "ACCOUNT_EVENT"),
        sub_event="CUSTOM",
        sub_event_confidence=1.0,
        user=user,
        enabled=enabled,
        alert_type="wallet",
        target_keys=target_keys or ["ETH:mainnet:0x742d35cc6634c0532925a3b8d4c9db96c4b4d8b"],
        trigger_type="event_driven",
        trigger_config={"chains": ["ethereum"], "event_types": ["transfer"]},
        processing_status="skipped",
    )


def test_alert_cache_signal_syncs_on_create(monkeypatch, user, sample_alert_template):
    calls: list[tuple[str, str]] = []
    _patch_signal_dependencies(monkeypatch, calls)

    instance = _create_instance(user, sample_alert_template)

    assert calls == [("sync", str(instance.id)), ("group_sync", str(instance.id))]


def test_alert_cache_signal_removes_on_disable(monkeypatch, user, sample_alert_template):
    calls: list[tuple[str, str]] = []
    _patch_signal_dependencies(monkeypatch, calls)

    instance = _create_instance(user, sample_alert_template)
    calls.clear()

    instance.enabled = False
    instance.save(update_fields=["enabled", "updated_at"])

    assert calls == [("remove", str(instance.id)), ("group_remove", str(instance.id))]


def test_alert_cache_signal_refreshes_on_update(monkeypatch, user, sample_alert_template):
    calls: list[tuple[str, str]] = []
    _patch_signal_dependencies(monkeypatch, calls)

    instance = _create_instance(user, sample_alert_template)
    calls.clear()

    instance.target_keys = ["ETH:mainnet:0x1111111111111111111111111111111111111111"]
    instance.save(update_fields=["target_keys", "updated_at"])

    assert calls == [("remove", str(instance.id)), ("sync", str(instance.id)), ("group_sync", str(instance.id))]


def test_alert_cache_signal_removes_on_delete(monkeypatch, user, sample_alert_template):
    calls: list[tuple[str, str]] = []
    _patch_signal_dependencies(monkeypatch, calls)

    instance = _create_instance(user, sample_alert_template)
    instance_id = str(instance.id)
    calls.clear()

    instance.delete()

    assert calls == [("remove", instance_id), ("group_remove", instance_id)]
