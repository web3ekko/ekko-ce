"""
Django model factories for alert system models.

These factories reflect the current "template v2 + pinned executable" architecture:
- Persisted template identity: app.models.alert_templates.AlertTemplate
- Version bundle: app.models.alert_templates.AlertTemplateVersion (template_spec + executable)
- User subscription: app.models.alerts.AlertInstance (pinned to template + template_version)

Legacy AlertTemplate v1 no longer exists as a Django model.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import factory
from faker import Faker
from django.utils import timezone

from app.models.alert_templates import AlertTemplate, AlertTemplateVersion
from app.models.alerts import AlertInstance, AlertExecution, AlertChangeLog
from tests.factories.auth_factories import UserFactory

fake = Faker()


def _sha256_hex() -> str:
    # Faker.sha256() returns a 64-hex string.
    return f"sha256:{fake.sha256()}"


def _minimal_template_v2_spec(
    *,
    template_id: uuid.UUID,
    template_version: int,
    fingerprint: str,
    name: str,
    description: str,
    target_kind: str,
    variables: list[dict] | None = None,
) -> dict:
    vars_list = variables or [
        {
            "id": "threshold",
            "type": "decimal",
            "label": "Threshold",
            "description": "Threshold value for the condition",
            "required": True,
            "validation": {"min": 0},
        }
    ]
    return {
        "schema_version": "alert_template_v2",
        "template_id": str(template_id),
        "template_version": int(template_version),
        "fingerprint": fingerprint,
        "spec_hash": "",  # filled by the factory
        "name": name,
        "description": description,
        "target_kind": target_kind,
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": vars_list,
        "signals": {"principals": [], "factors": []},
        "derivations": [],
        "trigger": {
            "evaluation_mode": "periodic",
            "condition_ast": {"op": "gt", "left": "balance_latest", "right": "{{threshold}}"},
            "cron_cadence_seconds": 300,
            "dedupe": {"cooldown_seconds": 300, "key_template": "{{instance_id}}:{{target.key}}"},
            "pruning_hints": {"evm": {"tx_type": "any"}},
        },
        "notification": {
            "title_template": "Alert: {{instance.name}}",
            "body_template": "Condition matched for {{target.key}}",
        },
        "fallbacks": [],
        "assumptions": [],
    }


def _minimal_executable_v1(
    *,
    executable_id: uuid.UUID,
    template_id: uuid.UUID,
    template_version: int,
    fingerprint: str,
    target_kind: str,
    variables: list[dict],
    registry_snapshot_hash: str,
) -> dict:
    return {
        "schema_version": "alert_executable_v1",
        "executable_id": str(executable_id),
        "template": {
            "schema_version": "alert_template_v2",
            "template_id": str(template_id),
            "fingerprint": fingerprint,
            "version": int(template_version),
        },
        "registry_snapshot": {"kind": "datasource_catalog", "version": "v1", "hash": registry_snapshot_hash},
        "target_kind": target_kind,
        "variables": variables,
        "trigger_pruning": {
            "evm": {
                "chain_ids": [1],
                "tx_type": "any",
                "from": {"any_of": [], "labels": [], "not": []},
                "to": {"any_of": [], "labels": [], "not": []},
                "method": {"selector_any_of": [], "name_any_of": [], "required": False},
                "event": {"topic0_any_of": [], "name_any_of": [], "required": False},
            }
        },
        "datasources": [],
        "enrichments": [],
        "conditions": {"all": [], "any": [], "not": []},
        "notification_template": {"title": "Test", "body": "Test"},
        "action": {
            "notification_policy": "per_matched_target",
            "cooldown_secs": 0,
            "cooldown_key_template": "{{instance_id}}:{{target.key}}",
            "dedupe_key_template": "{{run_id}}:{{instance_id}}:{{target.key}}",
        },
        "warnings": [],
    }


class AlertTemplateFactory(factory.django.DjangoModelFactory):
    """
    Factory for AlertTemplate v2 identity + a pinned version bundle.

    Params supported by downstream tests:
    - alert_type: alias for target_kind (wallet/token/network/protocol/contract/nft)
    - template_spec: explicit AlertTemplate v2 JSON (will be augmented with ids/hashes)
    - variables: override template_spec.variables
    - pinned_template_version: integer (default 1)
    """

    class Meta:
        model = AlertTemplate

    id = factory.LazyFunction(uuid.uuid4)
    fingerprint = factory.LazyFunction(_sha256_hex)
    name = factory.Sequence(lambda n: f"Alert Template {n}")
    description = factory.Faker("sentence")
    # Default; tests may override via `alert_type=` or `event_type=` hooks below.
    target_kind = "wallet"
    is_public = False
    is_verified = False
    created_by = factory.SubFactory(UserFactory)

    @factory.post_generation
    def pinned_bundle(self, create, extracted, **kwargs):
        if not create:
            return

        template_version = 1
        template_id = self.id
        fingerprint = str(self.fingerprint)
        target_kind = str(self.target_kind or "wallet")

        spec = _minimal_template_v2_spec(
            template_id=template_id,
            template_version=template_version,
            fingerprint=fingerprint,
            name=str(self.name),
            description=str(self.description),
            target_kind=target_kind,
            variables=None,
        )

        spec["template_id"] = str(template_id)
        spec["template_version"] = template_version
        spec["fingerprint"] = fingerprint
        spec["spec_hash"] = _sha256_hex()

        registry_snapshot_hash = _sha256_hex()
        exec_id = uuid.uuid4()
        executable = _minimal_executable_v1(
            executable_id=exec_id,
            template_id=template_id,
            template_version=template_version,
            fingerprint=fingerprint,
            target_kind=target_kind,
            variables=list(spec.get("variables") or []),
            registry_snapshot_hash=registry_snapshot_hash,
        )

        AlertTemplateVersion.objects.create(
            template=self,
            template_version=template_version,
            template_spec=spec,
            spec_hash=str(spec["spec_hash"]),
            executable_id=exec_id,
            executable=executable,
            registry_snapshot_kind="datasource_catalog",
            registry_snapshot_version="v1",
            registry_snapshot_hash=registry_snapshot_hash,
        )

    @factory.post_generation
    def variables(self, create, extracted, **kwargs):
        """
        Override the pinned template_spec.variables for tests that need custom variable sets.
        """
        if not create or extracted is None:
            return

        latest = self.versions.order_by("-template_version").first()
        if latest is None:
            return

        spec = dict(latest.template_spec or {})
        spec["variables"] = extracted
        spec["spec_hash"] = _sha256_hex()

        executable = dict(latest.executable or {})
        executable["variables"] = extracted

        latest.template_spec = spec
        latest.spec_hash = str(spec["spec_hash"])
        latest.executable = executable
        latest.save(update_fields=["template_spec", "spec_hash", "executable"])

    @factory.post_generation
    def alert_type(self, create, extracted, **kwargs):
        """
        Back-compat hook: allow tests to pass `alert_type=` and have it set both the
        template identity field (target_kind) and the pinned template_spec bundle.
        """
        if not create or not extracted:
            return

        kind = str(extracted).strip().lower() or "wallet"
        if self.target_kind != kind:
            self.target_kind = kind
            self.save(update_fields=["target_kind", "updated_at"])

        latest = self.versions.order_by("-template_version").first()
        if latest is None:
            return

        spec = dict(latest.template_spec or {})
        spec["target_kind"] = kind
        metadata = spec.get("metadata") if isinstance(spec.get("metadata"), dict) else {}
        metadata["target_kind_source"] = "alert_type"
        spec["metadata"] = metadata
        spec["spec_hash"] = _sha256_hex()

        executable = dict(latest.executable or {})
        executable["target_kind"] = kind

        latest.template_spec = spec
        latest.spec_hash = str(spec["spec_hash"])
        latest.executable = executable
        latest.save(update_fields=["template_spec", "spec_hash", "executable"])

    @factory.post_generation
    def event_type(self, create, extracted, **kwargs):
        """
        Back-compat hook: some older tests still pass an event_type and expect it to
        influence the UI-facing template_type (wallet/network/etc).

        We store it in template_spec.metadata.event_type so production code can ignore it
        while legacy UI/Group APIs can still surface it deterministically.
        """
        if not create or not extracted:
            return

        latest = self.versions.order_by("-template_version").first()
        if latest is None:
            return

        spec = dict(latest.template_spec or {})
        metadata = spec.get("metadata") if isinstance(spec.get("metadata"), dict) else {}
        metadata["event_type"] = str(extracted)

        # If the caller didn't explicitly set alert_type, let event_type drive target_kind.
        source = str(metadata.get("target_kind_source") or "").strip().lower()
        if source != "alert_type":
            mapping = {
                "ACCOUNT_EVENT": "wallet",
                "ASSET_EVENT": "token",
                "PROTOCOL_EVENT": "network",
                "DEFI_EVENT": "protocol",
                "CONTRACT_INTERACTION": "contract",
                "ANOMALY_EVENT": "network",
            }
            mapped = mapping.get(str(extracted).strip().upper())
            if mapped and self.target_kind != mapped:
                self.target_kind = mapped
                self.save(update_fields=["target_kind", "updated_at"])
                spec["target_kind"] = mapped

                executable = dict(latest.executable or {})
                executable["target_kind"] = mapped
                latest.executable = executable

        spec["metadata"] = metadata
        spec["spec_hash"] = _sha256_hex()

        latest.template_spec = spec
        latest.spec_hash = str(spec["spec_hash"])
        latest.save(update_fields=["template_spec", "spec_hash", "executable"])


class PublicAlertTemplateFactory(AlertTemplateFactory):
    """Factory for marketplace templates."""

    is_public = True
    is_verified = True


class AlertInstanceFactory(factory.django.DjangoModelFactory):
    """Factory for AlertInstance model - user's subscription to a pinned template."""

    class Meta:
        model = AlertInstance

    name = factory.Sequence(lambda n: f"Alert Instance {n}")
    nl_description = factory.Faker("sentence")
    user = factory.SubFactory(UserFactory)
    enabled = True
    version = 1

    # Template-based alert (default)
    template = factory.SubFactory(AlertTemplateFactory)
    template_version = factory.LazyAttribute(lambda o: int(o.template.versions.order_by("-template_version").first().template_version))
    template_params = factory.LazyAttribute(lambda _o: {"threshold": 100.0})
    _standalone_spec = None

    # Event classification (denormalized)
    event_type = "ACCOUNT_EVENT"
    sub_event = "CUSTOM"
    sub_event_confidence = factory.Faker("pyfloat", min_value=0.7, max_value=1.0)

    # Trigger configuration for AlertJob creation
    trigger_type = "event_driven"
    trigger_config = factory.LazyAttribute(
        lambda o: {
            "event_driven": {"chains": ["ethereum"], "event_types": ["transfer", "swap"]},
            "one_time": {"reset_allowed": True},
            "periodic": {"interval_seconds": 300, "schedule": "*/5 * * * *"},
        }.get(o.trigger_type, {})
    )
    last_job_created_at = None
    job_creation_count = 0

    # Targeting (defaults to explicit keys)
    alert_type = factory.LazyAttribute(lambda o: str(getattr(o.template, "target_kind", "wallet") or "wallet"))
    target_group = None
    target_keys = factory.LazyFunction(lambda: ["ETH:mainnet:0xabcdef000000000000000000000000000000000000"])

    author = ""


class StandaloneAlertInstanceFactory(AlertInstanceFactory):
    """Factory for standalone alert instances (not template-based)."""

    template = None
    template_version = None
    template_params = None
    _standalone_spec = factory.LazyAttribute(
        lambda _o: {
            "version": "v1",
            "name": "Standalone Alert",
            "description": "Standalone alert spec",
            "variables": [
                {"id": "threshold", "type": "decimal", "label": "Threshold", "required": True, "default": 100.0}
            ],
            "trigger": {
                "chain_id": 1,
                "tx_type": {"primary": ["any"], "subtypes": []},
                "from": {"any_of": [], "labels": [], "groups": [], "not": []},
                "to": {"any_of": [], "labels": [], "groups": [], "not": []},
                "method": {"selector_any_of": [], "name_any_of": [], "required": False},
            },
            "datasources": [],
            "enrichments": [],
            "conditions": {"all": [{"op": "gt", "left": "$.tx.value_native", "right": "{{threshold}}"}], "any": [], "not": []},
            "action": {"cooldown_secs": 0},
            "warnings": [],
        }
    )


class EventDrivenAlertInstanceFactory(AlertInstanceFactory):
    trigger_type = "event_driven"
    trigger_config = factory.LazyAttribute(lambda _o: {"chains": ["ethereum", "polygon"], "event_types": ["transfer", "swap"]})


class OneTimeAlertInstanceFactory(AlertInstanceFactory):
    trigger_type = "one_time"
    trigger_config = factory.LazyAttribute(lambda _o: {"reset_allowed": True})


class PeriodicAlertInstanceFactory(AlertInstanceFactory):
    trigger_type = "periodic"
    trigger_config = factory.LazyAttribute(
        lambda _o: {"interval_seconds": fake.random_element(elements=[60, 300, 900, 3600]), "schedule": "*/5 * * * *"}
    )


class AlertExecutionFactory(factory.django.DjangoModelFactory):
    """Factory for AlertExecution model - consolidated execution and retry tracking."""

    class Meta:
        model = AlertExecution

    alert_instance = factory.SubFactory(AlertInstanceFactory)
    alert_version = factory.LazyAttribute(lambda o: o.alert_instance.version if o.alert_instance else 1)
    trigger_mode = "event"
    attempt_number = 1
    max_retries = 3

    started_at = factory.LazyFunction(timezone.now)
    completed_at = factory.LazyAttribute(lambda o: o.started_at + timedelta(milliseconds=fake.random_int(10, 5000)))
    execution_time_ms = factory.LazyAttribute(lambda o: int((o.completed_at - o.started_at).total_seconds() * 1000))

    frozen_spec = factory.LazyAttribute(lambda o: o.alert_instance.spec if o.alert_instance else {})

    status = factory.Iterator(["completed", "failed", "timeout"])
    result = factory.LazyAttribute(lambda o: True if o.status == "completed" else False)


class AlertChangeLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AlertChangeLog

    alert_instance = factory.SubFactory(AlertInstanceFactory)
    from_version = factory.LazyAttribute(lambda o: o.to_version - 1 if o.to_version > 1 else None)
    to_version = factory.Sequence(lambda n: n + 1)
    change_type = factory.Iterator(["created", "updated", "enabled", "disabled"])
    changed_fields = factory.LazyAttribute(lambda o: ["name", "nl_description"] if o.change_type == "updated" else ["enabled"])
    old_values = factory.LazyAttribute(lambda o: {"name": fake.word(), "nl_description": fake.sentence()} if o.change_type == "updated" else {"enabled": False})
    new_values = factory.LazyAttribute(lambda o: {"name": o.alert_instance.name, "nl_description": o.alert_instance.nl_description} if o.change_type == "updated" else {"enabled": True})
    changed_by = factory.SubFactory(UserFactory)
    change_reason = factory.Faker("sentence")


def create_alert_instance_with_history(user=None, **alert_kwargs):
    """Create an alert instance with execution history and change logs."""
    if user is None:
        user = UserFactory()

    alert_instance = AlertInstanceFactory(user=user, **alert_kwargs)

    AlertChangeLogFactory(alert_instance=alert_instance, from_version=None, to_version=1, change_type="created", changed_by=user)

    for i in range(5):
        AlertExecutionFactory(alert_instance=alert_instance, attempt_number=1, status="completed" if i % 2 == 0 else "failed")

    return alert_instance


def create_template_with_instances(template_kwargs=None, instance_count=3):
    """Create a template with multiple alert instances using it."""
    template_kwargs = template_kwargs or {}
    template = PublicAlertTemplateFactory(**template_kwargs)

    instances = [AlertInstanceFactory(template=template) for _ in range(instance_count)]
    return template, instances


def create_complete_alert_workflow(user=None):
    """Create a complete alert workflow with template, instance, executions, and logs."""
    if user is None:
        user = UserFactory()

    template = AlertTemplateFactory(created_by=user, is_public=True)
    instance = AlertInstanceFactory(user=user, template=template, enabled=True)

    AlertChangeLogFactory(alert_instance=instance, from_version=None, to_version=1, change_type="created", changed_by=user)

    execution1 = AlertExecutionFactory(alert_instance=instance, attempt_number=1, status="failed")
    execution2 = AlertExecutionFactory(alert_instance=instance, attempt_number=2, status="completed", result=True)

    return {"template": template, "instance": instance, "executions": [execution1, execution2], "user": user}
