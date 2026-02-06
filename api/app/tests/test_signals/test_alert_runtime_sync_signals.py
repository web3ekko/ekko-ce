from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from app.signals.alert_runtime_sync_signals import (
    project_alert_instance_to_redis,
    project_alert_template_bundle_to_redis,
    remove_alert_instance_from_redis,
)


class TestAlertRuntimeSyncSignals(TestCase):
    def test_signals_noop_when_runtime_sync_disabled(self):
        inst = MagicMock()
        inst.id = "i1"
        tmpl_ver = MagicMock()
        tmpl_ver.template_id = "t1"
        tmpl_ver.template_version = 1

        with override_settings(ALERT_RUNTIME_REDIS_SYNC_ENABLED=False):
            with patch("app.services.alert_runtime_projection.AlertRuntimeProjection") as proj:
                project_alert_instance_to_redis(sender=None, instance=inst)
                project_alert_template_bundle_to_redis(sender=None, instance=tmpl_ver)
                remove_alert_instance_from_redis(sender=None, instance=inst)
                proj.assert_not_called()

    def test_signals_invoke_projection_when_enabled(self):
        inst = MagicMock()
        inst.id = "i1"
        tmpl_ver = MagicMock()
        tmpl_ver.template_id = "t1"
        tmpl_ver.template_version = 1

        with override_settings(ALERT_RUNTIME_REDIS_SYNC_ENABLED=True):
            with patch("app.services.alert_runtime_projection.AlertRuntimeProjection") as proj:
                project_alert_instance_to_redis(sender=None, instance=inst)
                project_alert_template_bundle_to_redis(sender=None, instance=tmpl_ver)
                remove_alert_instance_from_redis(sender=None, instance=inst)
                assert proj.called is True
