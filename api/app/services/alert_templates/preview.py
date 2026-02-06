from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple

from django.conf import settings

from app.services.datasource_catalog import get_catalog_entry


class AlertTemplatePreviewError(RuntimeError):
    pass


class DuckLakeQueryExecutor(Protocol):
    def query(
        self,
        *,
        table: str,
        network: str,
        subnet: str,
        query: str,
        parameters: list[dict[str, Any]],
        limit: Optional[int],
        timeout_seconds: int,
    ) -> list[dict[str, Any]]:
        """
        Execute a DuckLake query and return rows as dictionaries.

        `parameters` MUST be a list in positional order matching `?` placeholders, encoded
        as ducklake-common SqlParam JSON (externally-tagged enum), e.g.:
          {"String": "ETH:mainnet:0x..."}
          {"Timestamp": 1737000000000}
          {"String": "a,b,c"}  # for list-like params (e.g. target_keys_csv)
        """


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_millis(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _parse_rfc3339_to_epoch_millis(value: str) -> int:
    try:
        # Python doesn't parse trailing "Z" with fromisoformat.
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    except Exception as e:
        raise AlertTemplatePreviewError(f"Invalid rfc3339 timestamp: {value!r}: {e}") from e
    return _epoch_millis(dt)


def _chain_for_network(network: str) -> str:
    mapping = {"ETH": "ethereum", "AVAX": "avalanche", "SOL": "solana", "BTC": "bitcoin"}
    chain = mapping.get(network.strip().upper())
    if not chain:
        raise AlertTemplatePreviewError(f"Unsupported network: {network!r}")
    return chain


def _jsonpath_get(root: dict[str, Any], path: str) -> Any:
    """
    Supported JSONPath surface is intentionally tiny:
    - dot-separated keys off an EvaluationContext-like dict.
    - Path passed in excludes the leading "$.".
    """

    current: Any = root
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise AlertTemplatePreviewError(f"binding JSONPath '$.{path}' not found")
        current = current[segment]
    return current


def _resolve_binding_expr(expr: Any, *, eval_ctx_json: dict[str, Any]) -> Any:
    if isinstance(expr, str):
        s = expr.strip()
        if s.startswith("$."):
            return _jsonpath_get(eval_ctx_json, s[2:])
        if s.startswith("{{") and s.endswith("}}"):
            var = s[2:-2].strip()
            vars_obj = eval_ctx_json.get("variables")
            if not isinstance(vars_obj, dict):
                raise AlertTemplatePreviewError("evaluation_context.variables must be an object")
            if var not in vars_obj:
                raise AlertTemplatePreviewError(f"variable {var!r} not found for binding")
            return vars_obj[var]
        return s
    return expr


def _to_sql_param(expected_type: str, value: Any) -> dict[str, Any]:
    t = expected_type.strip().lower()
    if t in {"string", "duration"}:
        return {"String": str(value)}
    if t == "integer":
        try:
            return {"Int64": int(value)}
        except Exception as e:
            raise AlertTemplatePreviewError(f"Invalid integer param: {value!r}: {e}") from e
    if t == "boolean":
        if isinstance(value, bool):
            return {"Bool": value}
        s = str(value).strip().lower()
        if s in {"true", "1"}:
            return {"Bool": True}
        if s in {"false", "0"}:
            return {"Bool": False}
        raise AlertTemplatePreviewError(f"Invalid boolean param: {value!r}")
    if t == "decimal":
        # Runtime treats decimal as string.
        return {"Decimal": str(value)}
    if t == "timestamp":
        if isinstance(value, (int, float)):
            return {"Timestamp": int(value)}
        if isinstance(value, str):
            return {"Timestamp": _parse_rfc3339_to_epoch_millis(value)}
        raise AlertTemplatePreviewError(f"Invalid timestamp param: {value!r}")
    if t == "target_keys_csv":
        if isinstance(value, list):
            return {"String": ",".join(str(v) for v in value)}
        return {"String": str(value)}
    raise AlertTemplatePreviewError(f"Unsupported datasource param type: {expected_type!r}")


def _build_ducklake_query_parameters(
    *,
    catalog_id: str,
    bindings: dict[str, Any],
    eval_ctx_json: dict[str, Any],
) -> list[dict[str, Any]]:
    entry = get_catalog_entry(catalog_id)
    if entry is None or entry.sql is None:
        raise AlertTemplatePreviewError(f"catalog entry {catalog_id!r} missing runtime SQL")

    param_types: dict[str, str] = {p.name: p.type for p in entry.params}
    params: list[dict[str, Any]] = []
    for name in entry.sql.param_order:
        expected = param_types.get(name, "string")
        if name in bindings:
            resolved = _resolve_binding_expr(bindings[name], eval_ctx_json=eval_ctx_json)
        else:
            # Conservative defaults (mirrors wasmCloud runtime behavior).
            if name == "target_keys":
                resolved = _jsonpath_get(eval_ctx_json, "targets.keys")
            elif name == "network":
                resolved = _jsonpath_get(eval_ctx_json, "partition.network")
            elif name == "subnet":
                resolved = _jsonpath_get(eval_ctx_json, "partition.subnet")
            elif name == "chain_id":
                resolved = _jsonpath_get(eval_ctx_json, "partition.chain_id")
            elif name == "as_of":
                resolved = _jsonpath_get(eval_ctx_json, "schedule.effective_as_of")
            elif name == "scheduled_for":
                resolved = _jsonpath_get(eval_ctx_json, "schedule.scheduled_for")
            else:
                raise AlertTemplatePreviewError(f"missing required datasource binding for {name!r}")

        params.append(_to_sql_param(expected, resolved))

    return params


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal))


def _coerce_numeric(a: Any, b: Any) -> Tuple[Any, Any]:
    if isinstance(a, Decimal) or isinstance(b, Decimal):
        return Decimal(str(a)), Decimal(str(b))
    return a, b


def _resolve_expr_operand(operand: Any, *, row: dict[str, Any], variables: dict[str, Any]) -> Any:
    if isinstance(operand, dict) and "op" in operand:
        return eval_expr_ast(operand, row=row, variables=variables)
    if isinstance(operand, str):
        s = operand.strip()
        if s.startswith("{{") and s.endswith("}}"):
            var = s[2:-2].strip()
            return variables.get(var)
        if s.startswith("$.datasources."):
            # $.datasources.<ds_id>.<col>
            parts = s.split(".")
            if len(parts) < 4:
                return None
            ds_id = parts[2]
            col = parts[3]
            return ((row.get("datasources") or {}).get(ds_id) or {}).get(col)
        if s.startswith("$.enrichment."):
            name = s.split(".", 2)[2]
            return (row.get("enrichment") or {}).get(name)
        if s.startswith("$.tx."):
            name = s.split(".", 2)[2]
            return (row.get("tx") or {}).get(name)
        # Treat as literal string.
        return s
    return operand


def eval_expr_ast(expr: dict[str, Any], *, row: dict[str, Any], variables: dict[str, Any]) -> Any:
    op = str(expr.get("op") or "").strip().lower()
    if not op:
        raise AlertTemplatePreviewError("Expression op must be a non-empty string")

    if op in {"and", "or"}:
        args = expr.get("values")
        if not isinstance(args, list):
            # allow left/right chaining too
            args = [expr.get("left"), expr.get("right")]
        values = [
            bool(eval_expr_ast(a, row=row, variables=variables))
            for a in args
            if a is not None
        ]
        if op == "and":
            return all(values) if values else False
        return any(values) if values else False

    if op == "not":
        inner = expr.get("left")
        return not bool(_resolve_expr_operand(inner, row=row, variables=variables))

    if op == "coalesce":
        values = expr.get("values")
        if not isinstance(values, list):
            values = [expr.get("left"), expr.get("right")]
        for v in values:
            resolved = _resolve_expr_operand(v, row=row, variables=variables)
            if resolved is not None:
                return resolved
        return None

    left = _resolve_expr_operand(expr.get("left"), row=row, variables=variables)
    right = _resolve_expr_operand(expr.get("right"), row=row, variables=variables)

    if op in {"eq", "neq", "lt", "lte", "gt", "gte"}:
        if left is None or right is None:
            return None
        if _is_number(left) and _is_number(right):
            left, right = _coerce_numeric(left, right)
        if op == "eq":
            return left == right
        if op == "neq":
            return left != right
        if op == "lt":
            return left < right
        if op == "lte":
            return left <= right
        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right

    if op in {"add", "sub", "mul", "div"}:
        if left is None or right is None:
            return None
        if _is_number(left) and _is_number(right):
            left, right = _coerce_numeric(left, right)
        if op == "add":
            return left + right
        if op == "sub":
            return left - right
        if op == "mul":
            return left * right
        if op == "div":
            return left / right

    raise AlertTemplatePreviewError(f"Unsupported expr op: {op!r}")


def _conditions_match(conditions: dict[str, Any], *, row: dict[str, Any], variables: dict[str, Any]) -> bool:
    all_exprs = conditions.get("all") if isinstance(conditions.get("all"), list) else []
    any_exprs = conditions.get("any") if isinstance(conditions.get("any"), list) else []
    not_exprs = conditions.get("not") if isinstance(conditions.get("not"), list) else []

    for expr in all_exprs:
        if not isinstance(expr, dict):
            continue
        v = eval_expr_ast(expr, row=row, variables=variables)
        if v is not True:
            return False

    if any_exprs:
        ok_any = False
        for expr in any_exprs:
            if not isinstance(expr, dict):
                continue
            v = eval_expr_ast(expr, row=row, variables=variables)
            if v is True:
                ok_any = True
                break
        if not ok_any:
            return False

    for expr in not_exprs:
        if not isinstance(expr, dict):
            continue
        v = eval_expr_ast(expr, row=row, variables=variables)
        if v is True:
            return False

    return True


@dataclass(frozen=True)
class TemplatePreviewInput:
    executable: dict[str, Any]
    network: str
    subnet: str
    chain_id: int
    target_keys: list[str]
    variables: dict[str, Any]
    effective_as_of_rfc3339: str
    sample_matches: int = 10


class TemplatePreviewService:
    def __init__(self, *, executor: DuckLakeQueryExecutor):
        self._executor = executor

    def preview(self, req: TemplatePreviewInput) -> dict[str, Any]:
        executable = req.executable
        if executable.get("schema_version") != "alert_executable_v1":
            raise AlertTemplatePreviewError("Unsupported executable schema_version")

        datasources = executable.get("datasources")
        if not isinstance(datasources, list) or not datasources:
            raise AlertTemplatePreviewError("Executable has no datasources")

        enrichments = executable.get("enrichments") if isinstance(executable.get("enrichments"), list) else []
        conditions = executable.get("conditions") if isinstance(executable.get("conditions"), dict) else {}

        eval_ctx = {
            "schema_version": "evaluation_context_v1",
            "run": {"run_id": "preview", "attempt": 1, "trigger_type": "periodic", "enqueued_at": _now_rfc3339()},
            "instance": {"instance_id": "preview", "user_id": "preview", "template_id": "preview", "template_version": 1},
            "partition": {"network": req.network, "subnet": req.subnet, "chain_id": int(req.chain_id)},
            "schedule": {"scheduled_for": req.effective_as_of_rfc3339, "data_lag_secs": 0, "effective_as_of": req.effective_as_of_rfc3339},
            "targets": {"mode": "keys", "keys": list(req.target_keys)},
            "variables": dict(req.variables),
        }

        # Fetch each datasource and build per-target rows.
        per_ds: dict[str, dict[str, dict[str, Any]]] = {}
        for ds in datasources:
            if not isinstance(ds, dict):
                continue
            ds_id = str(ds.get("id") or "").strip()
            catalog_id = str(ds.get("catalog_id") or "").strip()
            bindings = ds.get("bindings") if isinstance(ds.get("bindings"), dict) else {}
            if not ds_id or not catalog_id:
                continue

            entry = get_catalog_entry(catalog_id)
            if entry is None or entry.sql is None:
                raise AlertTemplatePreviewError(f"Unknown or non-query catalog_id: {catalog_id!r}")

            params = _build_ducklake_query_parameters(
                catalog_id=catalog_id,
                bindings={str(k): v for k, v in bindings.items()},
                eval_ctx_json=eval_ctx,
            )
            rows = self._executor.query(
                table=entry.routing.table,
                network=req.network,
                subnet=req.subnet,
                query=entry.sql.query,
                parameters=params,
                limit=None,
                timeout_seconds=max(1, int((ds.get("timeout_ms") or 1500)) // 1000),
            )

            key_cols = set(entry.result_schema.key_columns)
            index: dict[str, dict[str, Any]] = {}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                key = row.get("target_key")
                if not isinstance(key, str) or not key:
                    continue
                payload = {k: v for k, v in row.items() if k not in key_cols}
                index[key] = payload
            per_ds[ds_id] = index

        evaluated_rows: list[dict[str, Any]] = []
        matched: list[dict[str, Any]] = []
        for key in req.target_keys:
            row = {
                "target_key": key,
                "datasources": {ds_id: per_ds.get(ds_id, {}).get(key, {}) for ds_id in per_ds.keys()},
                "enrichment": {},
            }

            # Compute enrichments deterministically in order.
            for enr in enrichments:
                if not isinstance(enr, dict):
                    continue
                output = str(enr.get("output") or "").strip()
                if not output.startswith("$.enrichment."):
                    continue
                name = output.split(".", 2)[2]
                expr = enr.get("expr")
                if not isinstance(expr, dict):
                    continue
                row["enrichment"][name] = eval_expr_ast(expr, row=row, variables=req.variables)

            is_match = _conditions_match(conditions, row=row, variables=req.variables)
            evaluated_rows.append({"target_key": key, "matched": is_match, "data": row})
            if is_match and len(matched) < int(req.sample_matches):
                matched.append(
                    {
                        "timestamp": req.effective_as_of_rfc3339,
                        "data": row,
                        "matched_condition": "alert_executable_v1.conditions",
                    }
                )

        total = len(evaluated_rows)
        match_count = sum(1 for r in evaluated_rows if r.get("matched") is True)
        return {
            "success": True,
            "summary": {
                "total_events_evaluated": total,
                "would_have_triggered": match_count,
                "trigger_rate": round((match_count / total) if total else 0.0, 4),
                "estimated_daily_triggers": 0.0,
                "evaluation_time_ms": 0.0,
            },
            "sample_triggers": matched,
            "near_misses": [],
            "evaluation_mode": "aggregate",
            "requires_wasmcloud": False,
            "data_source": "ducklake",
            "effective_as_of": req.effective_as_of_rfc3339,
        }


class NatsDuckLakeQueryExecutor:
    """
    DuckLake query executor backed by the DuckLake Read provider (NATS request/reply).

    Note: DuckLake Read replies with Arrow IPC stream bytes; decoding requires `pyarrow`.
    """

    def __init__(self, *, nats_url: Optional[str] = None, request_timeout_seconds: int = 15):
        self._nats_url = nats_url or getattr(settings, "NATS_URL", "nats://localhost:4222")
        self._timeout = request_timeout_seconds
        self._nc = None

    def query(
        self,
        *,
        table: str,
        network: str,
        subnet: str,
        query: str,
        parameters: list[dict[str, Any]],
        limit: Optional[int],
        timeout_seconds: int,
    ) -> list[dict[str, Any]]:
        import asyncio

        async def _run() -> list[dict[str, Any]]:
            try:
                import nats
            except ImportError as exc:
                raise AlertTemplatePreviewError("nats-py is required for template preview") from exc

            if self._nc is None or not self._nc.is_connected:
                self._nc = await nats.connect(self._nats_url)

            chain = _chain_for_network(network)
            subject = f"ducklake.{table}.{chain}.{subnet}.query"
            payload = {
                "query": query,
                "limit": int(limit) if limit is not None else None,
                "timeout_seconds": int(timeout_seconds or self._timeout),
                "parameters": parameters or None,
            }
            msg = await self._nc.request(subject, json.dumps(payload).encode("utf-8"), timeout=self._timeout)
            return _decode_arrow_ipc_rows(msg.data)

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()


def _decode_arrow_ipc_rows(payload: bytes) -> list[dict[str, Any]]:
    try:
        import pyarrow.ipc as ipc
    except Exception as exc:
        raise AlertTemplatePreviewError("pyarrow is required to decode DuckLake query responses") from exc

    try:
        reader = ipc.open_stream(payload)
        table = reader.read_all()
        return table.to_pylist()
    except Exception as exc:
        raise AlertTemplatePreviewError(f"Failed to decode Arrow IPC stream: {exc}") from exc
