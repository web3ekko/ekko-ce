from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


INSTANCE_KEY_PREFIX = "alerts:instance:"
TEMPLATE_KEY_PREFIX = "alerts:template:"
EXECUTABLE_KEY_PREFIX = "alerts:executable:"
NOTIFICATION_OVERRIDE_KEY = "__notification_overrides"

SCHEDULE_PERIODIC_ZSET = "alerts:schedule:periodic"
SCHEDULE_ONE_TIME_ZSET = "alerts:schedule:one_time"

EVENT_IDX_TARGET_INSTANCES_PREFIX = "alerts:event_idx:target_instances:"
EVENT_IDX_GROUP_INSTANCES_PREFIX = "alerts:event_idx:group_instances:"


def _redis_client() -> redis.Redis:
    cache_location = settings.CACHES.get("default", {}).get("LOCATION")
    redis_url = (
        cache_location
        if isinstance(cache_location, str) and cache_location.startswith(("redis://", "rediss://", "unix://"))
        else getattr(settings, "REDIS_URL", cache_location)
    )
    return redis.from_url(redis_url, decode_responses=True)


def _instance_key(instance_id: str) -> str:
    return f"{INSTANCE_KEY_PREFIX}{instance_id}"


def _template_key(template_id: str, template_version: int) -> str:
    return f"{TEMPLATE_KEY_PREFIX}{template_id}:{template_version}"

def _executable_key(template_id: str, template_version: int) -> str:
    return f"{EXECUTABLE_KEY_PREFIX}{template_id}:{template_version}"


def _event_idx_target_instances_key(target_key: str) -> str:
    return f"{EVENT_IDX_TARGET_INSTANCES_PREFIX}{target_key}"


def _event_idx_group_instances_key(group_id: str) -> str:
    return f"{EVENT_IDX_GROUP_INSTANCES_PREFIX}{group_id}"


def _normalize_notification_template(notification_template: dict) -> dict:
    title = str(notification_template.get("title") or "").strip()
    body = str(notification_template.get("body") or "").strip()

    default_title = "Alert triggered: {{target.short}}"
    default_body = "Condition met for {{target.short}}."

    if not title:
        title = default_title
    if not body:
        body = default_body or title

    return {"title": title, "body": body}


def _apply_notification_overrides(notification_template: dict, overrides: dict) -> dict:
    if not isinstance(overrides, dict):
        return notification_template

    title_override = overrides.get("title_template")
    if isinstance(title_override, str) and title_override.strip():
        notification_template["title"] = title_override.strip()

    body_override = overrides.get("body_template")
    if isinstance(body_override, str) and body_override.strip():
        notification_template["body"] = body_override.strip()

    return notification_template


@dataclass(frozen=True)
class ExistingInstanceIndexState:
    mode: str
    group_id: Optional[str]
    keys: list[str]


def _parse_existing_index_state(snapshot: dict) -> ExistingInstanceIndexState:
    selector = snapshot.get("target_selector") if isinstance(snapshot, dict) else None
    if not isinstance(selector, dict):
        return ExistingInstanceIndexState(mode="keys", group_id=None, keys=[])

    mode = selector.get("mode")
    if mode == "group":
        group_id = selector.get("group_id")
        return ExistingInstanceIndexState(
            mode="group",
            group_id=str(group_id) if group_id else None,
            keys=[],
        )

    keys = selector.get("keys")
    if isinstance(keys, list):
        normalized = [str(k) for k in keys if isinstance(k, str) and k.strip()]
        return ExistingInstanceIndexState(mode="keys", group_id=None, keys=normalized)

    return ExistingInstanceIndexState(mode="keys", group_id=None, keys=[])


class AlertRuntimeProjection:
    """
    Project alert runtime state (templates, instances, routing indices) into Redis.

    This is the Django-owned source of truth for the Redis keys consumed by:
    - alert-scheduler provider
    - alerts-processor actor
    - notification-router actor
    """

    def __init__(self) -> None:
        self._redis = _redis_client()

    def get_template_spec(self, template_id: str, template_version: int) -> Optional[dict]:
        raw = self._redis.get(_template_key(template_id, template_version))
        if not raw:
            return None
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    def get_executable_spec(self, template_id: str, template_version: int) -> Optional[dict]:
        raw = self._redis.get(_executable_key(template_id, template_version))
        if not raw:
            return None
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    def project_template_bundle(self, *, template_id: str, template_version: int) -> Optional[dict]:
        """
        Project a pinned AlertTemplateVersion bundle (template_spec + executable) into Redis.

        Keys:
        - alerts:template:{template_id}:{template_version}
        - alerts:executable:{template_id}:{template_version}
        """

        try:
            from app.models.alert_templates import AlertTemplateVersion
        except Exception:
            logger.warning("Skipping template bundle Redis projection: AlertTemplate models unavailable")
            return None

        tmpl_ver = AlertTemplateVersion.objects.filter(
            template_id=template_id, template_version=int(template_version)
        ).first()
        if tmpl_ver is None:
            logger.warning(
                "Skipping template bundle Redis projection for %s v%s: missing template version",
                template_id,
                template_version,
            )
            return None

        template_spec = tmpl_ver.template_spec if isinstance(tmpl_ver.template_spec, dict) else None
        executable = tmpl_ver.executable if isinstance(tmpl_ver.executable, dict) else None
        if not template_spec or not executable:
            logger.warning(
                "Skipping template bundle Redis projection for %s v%s: missing artifacts",
                template_id,
                template_version,
            )
            return None

        self._redis.set(
            _template_key(template_id, int(template_version)),
            json.dumps(template_spec, separators=(",", ":"), sort_keys=True),
        )
        self._redis.set(
            _executable_key(template_id, int(template_version)),
            json.dumps(executable, separators=(",", ":"), sort_keys=True),
        )
        return executable

    def remove_instance(self, instance_id: str) -> None:
        instance_key = _instance_key(instance_id)
        raw = self._redis.get(instance_key)
        existing_snapshot: dict = {}
        if raw:
            try:
                decoded = json.loads(raw)
                if isinstance(decoded, dict):
                    existing_snapshot = decoded
            except json.JSONDecodeError:
                existing_snapshot = {}

        existing = _parse_existing_index_state(existing_snapshot)

        with self._redis.pipeline() as pipe:
            if existing.mode == "group" and existing.group_id:
                pipe.srem(_event_idx_group_instances_key(existing.group_id), instance_id)
            if existing.mode == "keys":
                for key in existing.keys:
                    pipe.srem(_event_idx_target_instances_key(key), instance_id)

            pipe.delete(instance_key)
            pipe.zrem(SCHEDULE_PERIODIC_ZSET, instance_id)
            pipe.zrem(SCHEDULE_ONE_TIME_ZSET, instance_id)
            pipe.execute()

    def project_instance(self, instance) -> None:
        instance_id = str(getattr(instance, "id"))
        enabled = bool(getattr(instance, "enabled", False))
        if not enabled:
            self.remove_instance(instance_id)
            return

        template_id_raw = getattr(instance, "template_id", None)
        template_version_raw = getattr(instance, "template_version", None)
        if not template_id_raw or not template_version_raw:
            logger.warning("Skipping instance Redis projection for %s: missing template reference", instance_id)
            return

        template_id = str(template_id_raw)
        template_version = int(template_version_raw)
        executable_spec = self.get_executable_spec(template_id, template_version)
        if executable_spec is None:
            self.project_template_bundle(template_id=template_id, template_version=template_version)
            executable_spec = self.get_executable_spec(template_id, template_version)
        if executable_spec is None:
            logger.warning(
                "Skipping instance Redis projection for %s: missing executable (%s v%s)",
                instance_id,
                template_id,
                template_version,
            )
            return

        existing_snapshot = self._get_existing_instance_snapshot(instance_id)
        existing_index = _parse_existing_index_state(existing_snapshot)

        target_selector = self._build_target_selector(instance)
        priority = self._resolve_priority(instance)
        alert_name = str(getattr(instance, "name", "") or "").strip()
        if not alert_name:
            alert_name = str(getattr(instance, "nl_description", "") or "").strip()
        alert_description = str(getattr(instance, "nl_description", "") or "").strip()

        notification_template_raw = executable_spec.get("notification_template")
        if not isinstance(notification_template_raw, dict):
            notification_template_raw = {}
        template_params = getattr(instance, "template_params") or {}
        notification_overrides = {}
        if isinstance(template_params, dict):
            overrides = template_params.get(NOTIFICATION_OVERRIDE_KEY)
            if isinstance(overrides, dict):
                notification_overrides = overrides
        if notification_overrides:
            notification_template_raw = _apply_notification_overrides(
                dict(notification_template_raw),
                notification_overrides,
            )
        notification_template = _normalize_notification_template(notification_template_raw)

        action = executable_spec.get("action")
        if not isinstance(action, dict):
            action = {}

        variable_values = template_params if isinstance(template_params, dict) else {}
        if isinstance(template_params, dict) and NOTIFICATION_OVERRIDE_KEY in template_params:
            variable_values = {k: v for k, v in template_params.items() if k != NOTIFICATION_OVERRIDE_KEY}

        snapshot = {
            "instance_id": instance_id,
            "alert_name": alert_name,
            "alert_description": alert_description,
            "user_id": str(getattr(instance, "user_id")) if getattr(instance, "user_id", None) else None,
            "enabled": True,
            "priority": priority,
            "template_id": template_id,
            "template_version": template_version,
            "trigger_type": getattr(instance, "trigger_type"),
            "trigger_config": getattr(instance, "trigger_config") or {},
            "target_selector": target_selector,
            "variable_values": variable_values,
            "notification_template": notification_template,
            "action": action,
        }

        with self._redis.pipeline() as pipe:
            self._apply_instance_index_updates(
                pipe=pipe,
                instance_id=instance_id,
                existing=existing_index,
                desired=target_selector,
            )
            pipe.set(_instance_key(instance_id), json.dumps(snapshot, separators=(",", ":"), sort_keys=True))
            pipe.execute()

    def _get_existing_instance_snapshot(self, instance_id: str) -> dict:
        raw = self._redis.get(_instance_key(instance_id))
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}

    def _resolve_priority(self, instance) -> str:
        get_priority = getattr(instance, "get_priority", None)
        if callable(get_priority):
            value = get_priority()
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        return "normal"

    def _resolve_pinned_template_version(self, instance) -> int:
        raw = getattr(instance, "template_version", None)
        if isinstance(raw, int) and raw > 0:
            return raw
        return 1

    def _build_target_selector(self, instance) -> dict:
        target_keys = getattr(instance, "target_keys", None)
        if isinstance(target_keys, list) and target_keys:
            keys = [str(k) for k in target_keys if isinstance(k, str) and k.strip()]
            return {"mode": "keys", "keys": keys}

        group_id = getattr(instance, "target_group_id", None)
        if group_id:
            return {"mode": "group", "group_id": str(group_id), "keys": []}

        return {"mode": "keys", "keys": []}

    def _apply_instance_index_updates(
        self,
        *,
        pipe,
        instance_id: str,
        existing: ExistingInstanceIndexState,
        desired: dict,
    ) -> None:
        desired_mode = desired.get("mode")
        if desired_mode == "group":
            desired_group = desired.get("group_id")
            if existing.mode == "group" and existing.group_id and existing.group_id != desired_group:
                pipe.srem(_event_idx_group_instances_key(existing.group_id), instance_id)
            if existing.mode == "keys":
                for key in existing.keys:
                    pipe.srem(_event_idx_target_instances_key(key), instance_id)
            if desired_group:
                pipe.sadd(_event_idx_group_instances_key(str(desired_group)), instance_id)
            return

        desired_keys_raw = desired.get("keys")
        desired_keys = (
            [str(k) for k in desired_keys_raw if isinstance(k, str) and k.strip()]
            if isinstance(desired_keys_raw, list)
            else []
        )

        if existing.mode == "group" and existing.group_id:
            pipe.srem(_event_idx_group_instances_key(existing.group_id), instance_id)
        if existing.mode == "keys":
            for key in existing.keys:
                if key not in desired_keys:
                    pipe.srem(_event_idx_target_instances_key(key), instance_id)

        for key in desired_keys:
            pipe.sadd(_event_idx_target_instances_key(key), instance_id)
