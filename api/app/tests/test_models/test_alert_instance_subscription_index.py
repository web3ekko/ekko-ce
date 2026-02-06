import pytest

from app.models.alerts import AlertInstance


pytestmark = pytest.mark.django_db


def test_template_subscribers_follow_enabled_state(monkeypatch, user, sample_alert_template):
    calls: list[tuple[str, str, str]] = []

    class FakeNotificationCacheManager:
        def __init__(self, *args, **kwargs):
            pass

        def add_subscriber_to_template(self, template_id: str, user_id: str) -> None:
            calls.append(("add", template_id, user_id))

        def remove_subscriber_from_template(self, template_id: str, user_id: str) -> None:
            calls.append(("remove", template_id, user_id))

    import app.services.notification_cache as notification_cache

    monkeypatch.setattr(notification_cache, "NotificationCacheManager", FakeNotificationCacheManager)

    latest = sample_alert_template.versions.order_by("-template_version").first()
    template_version = int(getattr(latest, "template_version", 1) or 1)
    instance = AlertInstance.objects.create(
        name="Test Alert",
        nl_description="Test",
        template=sample_alert_template,
        template_version=template_version,
        template_params={},
        event_type="ACCOUNT_EVENT",
        sub_event="CUSTOM",
        user=user,
        enabled=True,
    )

    assert calls == [("add", str(sample_alert_template.id), str(user.id))]

    calls.clear()
    instance.enabled = False
    instance.save(update_fields=["enabled", "updated_at"])
    assert calls == [("remove", str(sample_alert_template.id), str(user.id))]
