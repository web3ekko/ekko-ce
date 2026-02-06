# Notification Router Actor

The notification router actor consumes **alert match batches** from the alert runtime pipeline and produces **notification delivery requests**.

## Overview

This actor sits downstream of **Alerts Processor** + **Polars Eval**.

On each `alerts.triggered.*` message it:
1. Loads the pinned instance snapshot from Redis (`alerts:instance:{instance_id}`), including the pinned `notification_template` and `action` policies.
2. Renders the notification message per matched `target_key` using a deterministic `{{...}}` placeholder engine (supports dotted paths like `{{target.key}}`).
3. Enforces per-subscriber dedupe/cooldown (v1 uses `wasi:keyvalue/store` + `wasi:keyvalue/atomics`).
4. Publishes delivery requests (v1: webhook) to `notifications.send.immediate.webhook`.

## NATS Contracts

**Subscribe**
- `alerts.triggered.>`

**Publish (v1)**
- `notifications.send.immediate.webhook`

## Authoritative Specs

See:
- `docs/prd/wasmcloud/actors/PRD-Notification-Router-Actor-USDT.md`
- `docs/prd/schemas/SCHEMA-EvaluationContext.md`

## Notes
- The actor intentionally does **not** fetch datasource data or evaluate conditions; it only renders and routes notifications based on upstream match results.
