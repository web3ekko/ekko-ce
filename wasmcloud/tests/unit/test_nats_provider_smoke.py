from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import nats_provider_smoke as smoke  # noqa: E402


def _fixed_now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _fixed_ids() -> smoke.IdBundle:
    return smoke.IdBundle(
        notification_id="notif-1",
        alert_id="alert-1",
        user_id="user-1",
        request_id="request-1",
        instance_id="instance-1",
        job_id="job-1",
        run_id="run-1",
        template_id="template-1",
    )


def test_provider_registry_contains_expected_providers() -> None:
    specs = smoke.build_provider_specs(_fixed_now(), _fixed_ids())
    assert set(specs.keys()) == set(smoke.DEFAULT_PROVIDER_KEYS)


def test_webhook_and_slack_payload_shapes() -> None:
    specs = smoke.build_provider_specs(_fixed_now(), _fixed_ids())

    webhook = specs["webhook-notification"].probes[0]
    assert webhook.subject == "notifications.send.immediate.webhook"
    assert webhook.payload["notification_id"] == "notif-1"
    assert "payload" in webhook.payload

    slack = specs["slack-notification"].probes[0]
    assert slack.subject == "notifications.slack"
    assert slack.payload["priority"] == "normal"
    assert "timestamp" in slack.payload


def test_ducklake_read_probes_include_request_reply() -> None:
    specs = smoke.build_provider_specs(_fixed_now(), _fixed_ids())
    probes = {probe.name: probe for probe in specs["ducklake-read"].probes}

    schema_list = probes["ducklake-schema-list"]
    assert schema_list.expect_reply is True
    assert schema_list.payload == {"table_filter": None, "include_columns": False}

    schema_get = probes["ducklake-schema-get"]
    assert schema_get.expect_reply is True
    assert schema_get.payload["table_name"] == "transactions"

    query = probes["ducklake-query"]
    assert query.expect_reply is True
    assert "query" in query.payload
    assert "0xsmoke" in query.payload["query"]
    assert "ethereum_mainnet" in query.payload["query"]


def test_ducklake_write_payload_includes_required_fields() -> None:
    specs = smoke.build_provider_specs(_fixed_now(), _fixed_ids())
    payload = specs["ducklake-write"].probes[0].payload

    assert payload["chain_id"] == "ethereum_mainnet"
    assert payload["network"] == "ethereum"
    assert payload["subnet"] == "mainnet"
    assert payload["vm_type"] == "evm"
    assert payload["transaction_hash"] == "0xsmoke"
    assert payload["status"] == "SUCCESS"
    assert payload["transaction_type"] == "TRANSFER"
    assert payload["transaction_index"] == 0


def test_polars_eval_payload_contract() -> None:
    specs = smoke.build_provider_specs(_fixed_now(), _fixed_ids())
    probe = specs["polars-eval"].probes[0]
    payload = probe.payload

    assert payload["schema_version"] == "polars_eval_request_v1"
    assert payload["frame"]["format"] == "arrow_ipc_stream_base64"
    assert payload["frame"]["data"] == smoke.POLARS_EVAL_ARROW_B64
    assert payload["evaluation_context"]["schema_version"] == "evaluation_context_v1"
    assert payload["template"]["version"] == "v1"


def test_try_decode_arrow_ipc_returns_none_without_pyarrow(monkeypatch) -> None:
    monkeypatch.setattr(smoke.importlib.util, "find_spec", lambda _: None)
    assert smoke._try_decode_arrow_ipc(b"not-arrow") is None


def test_json_safe_serializes_common_types() -> None:
    payload = {
        "time": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "items": [b"bytes"],
    }
    safe = smoke._json_safe(payload)
    assert safe["time"] == "2026-01-01T00:00:00+00:00"
    assert safe["items"][0] == "Ynl0ZXM="


def test_alert_scheduler_payload_versions() -> None:
    specs = smoke.build_provider_specs(_fixed_now(), _fixed_ids())
    probes = {probe.name: probe for probe in specs["alert-scheduler"].probes}

    periodic = probes["schedule-periodic"].payload
    one_time = probes["schedule-one-time"].payload
    event_driven = probes["schedule-event-driven"].payload

    assert periodic["schema_version"] == "alert_schedule_periodic_v1"
    assert one_time["schema_version"] == "alert_schedule_one_time_v1"
    assert event_driven["schema_version"] == "alert_schedule_event_driven_v1"
