#!/usr/bin/env python3
"""NATS smoke injector for wasmCloud providers.

Publishes sample messages to NATS subjects for providers that consume NATS
messages directly. Intended for quick provider functionality checks.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import importlib.util
import json
import os
import sys
from datetime import date
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class IdBundle:
    notification_id: str
    alert_id: str
    user_id: str
    request_id: str
    instance_id: str
    job_id: str
    run_id: str
    template_id: str


@dataclass(frozen=True)
class Probe:
    name: str
    subject: str
    payload: Dict[str, Any]
    expect_reply: bool = False


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    description: str
    probes: List[Probe]


DEFAULT_PROVIDER_KEYS = [
    "alert-scheduler",
    "ducklake-write",
    "ducklake-read",
    "polars-eval",
    "slack-notification",
    "telegram-notification",
    "webhook-notification",
    "websocket-notification",
]

POLARS_EVAL_ARROW_B64 = (
    "/////8AAAAAQAAAAAAAKAAwABgAFAAgACgAAAAABBAAMAAAACAAIAAAABAAIAAAABAAAAAIAAABgAAAABAAAALj///8AAAEDEAAAADQAAAAEAAAAAAAAABoAAABkc19iYWxhbmNlX19iYWxhbmNlX2xhdGVzdAAAAAAGAAgABgAGAAAAAAACABAAFAAIAAYABwAMAAAAEAAQAAAAAAABBRAAAAAgAAAABAAAAAAAAAAKAAAAdGFyZ2V0X2tleQAABAAEAAQAAAD/////yAAAABQAAAAAAAAADAAWAAYABQAIAAwADAAAAAADBAAYAAAAKAAAAAAAAAAAAAoAGAAMAAQACAAKAAAAbAAAABAAAAABAAAAAAAAAAAAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAIAAAAAAAAABEAAAAAAAAAIAAAAAAAAAAAAAAAAAAAACAAAAAAAAAACAAAAAAAAAAAAAAAAgAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAABEAAABFVEg6bWFpbm5ldDoweGFiYwAAAAAAAADhehSuR+HaP/////8AAAAA"
)


def _rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_nats_url() -> str:
    return (
        os.getenv("E2E_NATS_URL")
        or os.getenv("NATS_URL")
        or "nats://localhost:4222"
    )


def _build_webhook_payload(now: datetime, ids: IdBundle) -> Dict[str, Any]:
    return {
        "notification_id": ids.notification_id,
        "user_id": ids.user_id,
        "alert_id": ids.alert_id,
        "alert_name": "Smoke Test: Webhook",
        "priority": "normal",
        "payload": {
            "triggered_value": "42",
            "threshold": "10",
            "chain": "ethereum",
            "wallet": "0xabc",
        },
        "timestamp": int(now.timestamp()),
    }


def _build_slack_payload(now: datetime, ids: IdBundle) -> Dict[str, Any]:
    return {
        "user_id": ids.user_id,
        "alert_id": ids.alert_id,
        "alert_name": "Smoke Test: Slack",
        "notification_type": "threshold",
        "priority": "normal",
        "payload": {
            "triggered_value": "42",
            "threshold": "10",
            "transaction_hash": None,
            "chain": "ethereum",
            "wallet": "0xabc",
            "block_number": 123,
        },
        "timestamp": _rfc3339(now),
    }


def _build_telegram_payload(now: datetime, ids: IdBundle) -> Dict[str, Any]:
    return {
        "user_id": ids.user_id,
        "alert_id": ids.alert_id,
        "alert_name": "Smoke Test: Telegram",
        "priority": "normal",
        "message": "Smoke test Telegram delivery",
        "chain": "ethereum",
        "transaction_hash": None,
        "wallet_address": "0xabc",
        "block_number": 123,
        "timestamp": _rfc3339(now),
    }


def _build_websocket_delivery_payload(now: datetime, ids: IdBundle) -> Dict[str, Any]:
    return {
        "user_id": ids.user_id,
        "alert_id": ids.alert_id,
        "subject": "Smoke Test: WebSocket",
        "message": "WebSocket smoke notification",
        "template": None,
        "variables": {},
        "priority": "normal",
        "channel": "websocket",
        "channel_config": {},
        "timestamp": _rfc3339(now),
    }


def _build_websocket_event_payload(now: datetime, ids: IdBundle) -> Dict[str, Any]:
    return {
        "user_id": ids.user_id,
        "event_type": "smoke_test",
        "job_id": ids.job_id,
        "payload": {"status": "ok"},
        "timestamp": _rfc3339(now),
    }


def _build_ducklake_write_payload(now: datetime) -> Dict[str, Any]:
    block_date = now.date().isoformat()
    return {
        "chain_id": "ethereum_mainnet",
        "block_date": block_date,
        "network": "ethereum",
        "subnet": "mainnet",
        "vm_type": "evm",
        "block_number": 123,
        "block_timestamp": int(now.timestamp()),
        "transaction_hash": "0xsmoke",
        "transaction_index": 0,
        "from_address": "0xabc",
        "to_address": "0xdef",
        "value": 0.42,
        "status": "SUCCESS",
        "transaction_type": "TRANSFER",
    }


def _build_ducklake_schema_list_payload() -> Dict[str, Any]:
    return {"table_filter": None, "include_columns": False}


def _build_ducklake_schema_get_payload() -> Dict[str, Any]:
    return {"table_name": "transactions"}


def _build_ducklake_query_payload(write_payload: Dict[str, Any]) -> Dict[str, Any]:
    tx_hash = write_payload["transaction_hash"]
    chain_id = write_payload["chain_id"]
    block_number = write_payload["block_number"]
    query = (
        "SELECT transaction_hash, status FROM transactions "
        f"WHERE transaction_hash = '{tx_hash}' "
        f"AND chain_id = '{chain_id}' "
        f"AND block_number = {block_number} "
        "LIMIT 1"
    )
    return {"query": query, "limit": 1, "timeout_seconds": 5}


def _build_polars_eval_payload(now: datetime, ids: IdBundle) -> Dict[str, Any]:
    return {
        "schema_version": "polars_eval_request_v1",
        "request_id": ids.request_id,
        "job_id": ids.job_id,
        "run_id": ids.run_id,
        "template": {
            "version": "v1",
            "name": "Smoke Test Template",
            "description": "Polars eval smoke test",
            "alert_type": "wallet",
            "variables": [],
            "trigger": {
                "tx_type": "any",
                "from": {"any_of": [], "labels": [], "not": []},
                "to": {"any_of": [], "labels": [], "not": []},
                "method": {"selector_any_of": [], "name_any_of": [], "required": False},
            },
            "datasources": [
                {
                    "id": "ds_balance",
                    "catalog_id": "ducklake.wallet_balance_latest",
                    "bindings": {},
                    "cache_ttl_secs": 30,
                    "timeout_ms": 1500,
                }
            ],
            "enrichments": [],
            "conditions": {
                "all": [
                    {
                        "op": "gt",
                        "left": "$.datasources.ds_balance.balance_latest",
                        "right": 0,
                    }
                ],
                "any": [],
                "not": [],
            },
            "notification_template": {"title": "Smoke", "body": "Smoke"},
            "action": {
                "notification_policy": "per_matched_target",
                "cooldown_secs": 0,
                "cooldown_key_template": "x",
                "dedupe_key_template": "y",
            },
            "performance": {},
            "warnings": [],
        },
        "evaluation_context": {
            "schema_version": "evaluation_context_v1",
            "run": {
                "run_id": ids.run_id,
                "attempt": 1,
                "trigger_type": "periodic",
                "enqueued_at": _rfc3339(now),
                "started_at": _rfc3339(now),
            },
            "instance": {
                "instance_id": ids.instance_id,
                "user_id": ids.user_id,
                "template_id": ids.template_id,
                "template_version": 1,
            },
            "partition": {"network": "ETH", "subnet": "mainnet", "chain_id": 1},
            "targets": {
                "mode": "keys",
                "group_id": None,
                "keys": ["ETH:mainnet:0xabc"],
            },
            "variables": {},
        },
        "frame": {"format": "arrow_ipc_stream_base64", "data": POLARS_EVAL_ARROW_B64},
        "output_fields": [
            {"ref": "$.datasources.ds_balance.balance_latest", "alias": "balance_latest"}
        ],
    }


def _build_alert_schedule_periodic(now: datetime, ids: IdBundle) -> Dict[str, Any]:
    scheduled_for = now + timedelta(minutes=1)
    return {
        "schema_version": "alert_schedule_periodic_v1",
        "request_id": ids.request_id,
        "instance_id": ids.instance_id,
        "scheduled_for": _rfc3339(scheduled_for),
        "requested_at": _rfc3339(now),
        "source": "smoke_test",
    }


def _build_alert_schedule_one_time(now: datetime, ids: IdBundle) -> Dict[str, Any]:
    scheduled_for = now + timedelta(minutes=2)
    return {
        "schema_version": "alert_schedule_one_time_v1",
        "request_id": ids.request_id,
        "instance_id": ids.instance_id,
        "scheduled_for": _rfc3339(scheduled_for),
        "requested_at": _rfc3339(now),
        "source": "smoke_test",
    }


def _build_alert_schedule_event_driven(now: datetime, ids: IdBundle) -> Dict[str, Any]:
    return {
        "schema_version": "alert_schedule_event_driven_v1",
        "vm": "evm",
        "partition": {"network": "ETH", "subnet": "mainnet", "chain_id": 1},
        "candidate_target_keys": ["ETH:mainnet:0xabc"],
        "event": {
            "kind": "tx",
            "evm_tx": {
                "hash": "0xsmoke",
                "from": "0xabc",
                "to": "0xdef",
                "input": "0x",
                "method_selector": "0x00000000",
                "value_wei": "123",
                "value_native": 0.0,
                "block_number": 123,
                "block_timestamp": _rfc3339(now),
            },
        },
        "requested_at": _rfc3339(now),
        "source": "smoke_test",
    }


def build_provider_specs(now: datetime, ids: IdBundle) -> Dict[str, ProviderSpec]:
    ducklake_write_payload = _build_ducklake_write_payload(now)
    ducklake_query_payload = _build_ducklake_query_payload(ducklake_write_payload)
    return {
        "webhook-notification": ProviderSpec(
            name="webhook-notification",
            description="Webhook notification provider (notifications.send.immediate.webhook)",
            probes=[
                Probe(
                    name="webhook-immediate",
                    subject="notifications.send.immediate.webhook",
                    payload=_build_webhook_payload(now, ids),
                )
            ],
        ),
        "slack-notification": ProviderSpec(
            name="slack-notification",
            description="Slack notification provider (notifications.slack)",
            probes=[
                Probe(
                    name="slack",
                    subject="notifications.slack",
                    payload=_build_slack_payload(now, ids),
                )
            ],
        ),
        "telegram-notification": ProviderSpec(
            name="telegram-notification",
            description="Telegram notification provider (notifications.send.immediate.telegram)",
            probes=[
                Probe(
                    name="telegram-immediate",
                    subject="notifications.send.immediate.telegram",
                    payload=_build_telegram_payload(now, ids),
                )
            ],
        ),
        "websocket-notification": ProviderSpec(
            name="websocket-notification",
            description="WebSocket notification provider (notifications.send.immediate.websocket + ws.events)",
            probes=[
                Probe(
                    name="websocket-immediate",
                    subject="notifications.send.immediate.websocket",
                    payload=_build_websocket_delivery_payload(now, ids),
                ),
                Probe(
                    name="websocket-event",
                    subject="ws.events",
                    payload=_build_websocket_event_payload(now, ids),
                ),
            ],
        ),
        "ducklake-write": ProviderSpec(
            name="ducklake-write",
            description="DuckLake write provider (ducklake.*.*.*.write)",
            probes=[
                Probe(
                    name="ducklake-write",
                    subject="ducklake.transactions.ethereum.mainnet.write",
                    payload=ducklake_write_payload,
                )
            ],
        ),
        "ducklake-read": ProviderSpec(
            name="ducklake-read",
            description="DuckLake read provider (ducklake.*.*.*.query + ducklake.schema.*)",
            probes=[
                Probe(
                    name="ducklake-schema-list",
                    subject="ducklake.schema.list",
                    payload=_build_ducklake_schema_list_payload(),
                    expect_reply=True,
                ),
                Probe(
                    name="ducklake-schema-get",
                    subject="ducklake.schema.get",
                    payload=_build_ducklake_schema_get_payload(),
                    expect_reply=True,
                ),
                Probe(
                    name="ducklake-query",
                    subject="ducklake.transactions.ethereum.mainnet.query",
                    payload=ducklake_query_payload,
                    expect_reply=True,
                ),
            ],
        ),
        "polars-eval": ProviderSpec(
            name="polars-eval",
            description="Polars eval provider (alerts.eval.request.*)",
            probes=[
                Probe(
                    name="polars-eval",
                    subject="alerts.eval.request.smoke",
                    payload=_build_polars_eval_payload(now, ids),
                    expect_reply=True,
                )
            ],
        ),
        "alert-scheduler": ProviderSpec(
            name="alert-scheduler",
            description="Alert scheduler provider (alerts.schedule.*)",
            probes=[
                Probe(
                    name="schedule-periodic",
                    subject="alerts.schedule.periodic",
                    payload=_build_alert_schedule_periodic(now, ids),
                ),
                Probe(
                    name="schedule-one-time",
                    subject="alerts.schedule.one_time",
                    payload=_build_alert_schedule_one_time(now, ids),
                ),
                Probe(
                    name="schedule-event-driven",
                    subject="alerts.schedule.event_driven",
                    payload=_build_alert_schedule_event_driven(now, ids),
                ),
            ],
        ),
    }


def _parse_provider_list(raw: str) -> List[str]:
    if not raw:
        return []
    items: List[str] = []
    for chunk in raw.split(","):
        items.extend([part.strip() for part in chunk.split() if part.strip()])
    return items


def _select_providers(
    specs: Dict[str, ProviderSpec],
    requested: Iterable[str],
) -> List[ProviderSpec]:
    if not requested:
        return [specs[key] for key in DEFAULT_PROVIDER_KEYS]
    missing = [name for name in requested if name not in specs]
    if missing:
        raise ValueError(f"Unknown provider keys: {', '.join(missing)}")
    return [specs[name] for name in requested]


def _print_providers(specs: Dict[str, ProviderSpec]) -> None:
    for key in DEFAULT_PROVIDER_KEYS:
        spec = specs[key]
        print(f"{spec.name}: {spec.description}")
        for probe in spec.probes:
            reply = " (reply)" if probe.expect_reply else ""
            print(f"  - {probe.name}: {probe.subject}{reply}")


def _format_payload(payload: Dict[str, Any], pretty: bool) -> str:
    if pretty:
        return json.dumps(payload, indent=2, sort_keys=True)
    return json.dumps(payload)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("utf-8")
    return value


def _try_decode_arrow_ipc(payload: bytes) -> Dict[str, Any] | None:
    if importlib.util.find_spec("pyarrow") is None:
        return None

    try:
        import pyarrow.ipc as ipc
    except Exception:
        return None

    try:
        reader = ipc.open_stream(payload)
        table = reader.read_all()
        rows = table.to_pylist()
    except Exception:
        return None

    return {
        "row_count": len(rows),
        "columns": table.schema.names,
        "rows": _json_safe(rows),
    }


async def _run_probes(
    nats_url: str,
    specs: List[ProviderSpec],
    timeout: float,
    dry_run: bool,
    pretty: bool,
) -> int:
    if dry_run:
        for spec in specs:
            print(f"[{spec.name}]")
            for probe in spec.probes:
                payload_str = _format_payload(probe.payload, pretty)
                print(f"{probe.subject}: {payload_str}")
        return 0

    try:
        import nats
    except ImportError as exc:
        raise RuntimeError("nats-py is required (pip install nats-py)") from exc

    nc = await nats.connect(nats_url)
    wrote_ducklake = False
    try:
        for spec in specs:
            print(f"[{spec.name}]")
            if spec.name == "ducklake-read" and wrote_ducklake:
                await asyncio.sleep(0.5)
            for probe in spec.probes:
                payload_bytes = json.dumps(probe.payload).encode("utf-8")
                if probe.expect_reply:
                    msg = await nc.request(probe.subject, payload_bytes, timeout=timeout)
                    response = msg.data.decode("utf-8", errors="replace")
                    try:
                        response_json = json.loads(response)
                        print(
                            f"{probe.name} -> {probe.subject} reply: {json.dumps(response_json, indent=2, sort_keys=True)}"
                        )
                    except json.JSONDecodeError:
                        decoded = _try_decode_arrow_ipc(msg.data)
                        if decoded is not None:
                            print(
                                f"{probe.name} -> {probe.subject} reply: {json.dumps(decoded, indent=2, sort_keys=True)}"
                            )
                        else:
                            b64 = base64.b64encode(msg.data).decode("utf-8")
                            print(
                                f"{probe.name} -> {probe.subject} reply (base64): {b64}"
                            )
                else:
                    await nc.publish(probe.subject, payload_bytes)
                    print(f"{probe.name} -> {probe.subject} published")
            if spec.name == "ducklake-write":
                wrote_ducklake = True
        await nc.flush()
    finally:
        await nc.close()
    return 0


def _build_ids() -> IdBundle:
    import uuid

    return IdBundle(
        notification_id=str(uuid.uuid4()),
        alert_id=str(uuid.uuid4()),
        user_id="user-smoke-test",
        request_id=str(uuid.uuid4()),
        instance_id=str(uuid.uuid4()),
        job_id=str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),
        template_id=str(uuid.uuid4()),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inject NATS messages for wasmCloud provider smoke tests",
    )
    parser.add_argument(
        "--nats-url",
        default=_default_nats_url(),
        help="NATS server URL",
    )
    parser.add_argument(
        "--providers",
        default="",
        help="Comma- or space-separated provider keys (default: all)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available providers and subjects",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without sending to NATS",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Request-reply timeout in seconds",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON payloads",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    now = datetime.now(timezone.utc)
    ids = _build_ids()
    specs = build_provider_specs(now, ids)

    if args.list:
        _print_providers(specs)
        return 0

    requested = _parse_provider_list(args.providers)
    try:
        selected = _select_providers(specs, requested)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        return asyncio.run(
            _run_probes(
                args.nats_url,
                selected,
                args.timeout,
                args.dry_run,
                args.pretty,
            )
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
