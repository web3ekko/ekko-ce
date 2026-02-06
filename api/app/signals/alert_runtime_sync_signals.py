"""
Django signals for projecting alert runtime state into Redis.

This module is authoritative for the Redis projection consumed by the wasmCloud
alert runtime (scheduler/processor/router).
"""

import logging

from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="app.AlertTemplateVersion")
def project_alert_template_bundle_to_redis(sender, instance, **kwargs):
    """
    Project the pinned template bundle (template_spec + executable) into Redis.

    vNext runtime consumes `AlertExecutable` pinned to `(template_id, template_version)`.
    """

    if not getattr(settings, "ALERT_RUNTIME_REDIS_SYNC_ENABLED", True):
        return
    try:
        from app.services.alert_runtime_projection import AlertRuntimeProjection

        AlertRuntimeProjection().project_template_bundle(
            template_id=str(instance.template_id),
            template_version=int(instance.template_version),
        )
    except Exception as exc:
        logger.error(
            "Error projecting AlertTemplateVersion %s@%s to Redis: %s",
            getattr(instance, "template_id", None),
            getattr(instance, "template_version", None),
            exc,
        )


@receiver(post_save, sender="app.AlertInstance")
def project_alert_instance_to_redis(sender, instance, **kwargs):
    if not getattr(settings, "ALERT_RUNTIME_REDIS_SYNC_ENABLED", True):
        return
    try:
        from app.services.alert_runtime_projection import AlertRuntimeProjection

        AlertRuntimeProjection().project_instance(instance)
    except Exception as exc:
        logger.error("Error projecting AlertInstance %s to Redis: %s", instance.id, exc)


@receiver(post_delete, sender="app.AlertInstance")
def remove_alert_instance_from_redis(sender, instance, **kwargs):
    if not getattr(settings, "ALERT_RUNTIME_REDIS_SYNC_ENABLED", True):
        return
    try:
        from app.services.alert_runtime_projection import AlertRuntimeProjection

        AlertRuntimeProjection().remove_instance(str(instance.id))
    except Exception as exc:
        logger.error("Error removing AlertInstance %s from Redis: %s", instance.id, exc)
