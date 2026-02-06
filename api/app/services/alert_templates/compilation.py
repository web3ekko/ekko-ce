from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.datasource_catalog import get_catalog_entry, list_compiler_catalog_entries


class AlertTemplateCompileError(RuntimeError):
    pass


@dataclass(frozen=True)
class CompileContext:
    template_id: uuid.UUID
    template_version: int
    registry_snapshot: Dict[str, str]


def _chain_ids_from_networks(networks: list[str]) -> list[int]:
    # Canonical network keys are `{NETWORK}:{subnet}` (e.g. ETH:mainnet).
    mapping = {"ETH": 1, "AVAX": 43114}
    chain_ids: list[int] = []
    for raw in networks:
        if not isinstance(raw, str) or ":" not in raw:
            continue
        network, _sep, _subnet = raw.partition(":")
        chain_id = mapping.get(network.strip().upper())
        if chain_id is not None and chain_id not in chain_ids:
            chain_ids.append(chain_id)
    return chain_ids


def _collect_signal_names(template: Dict[str, Any]) -> set[str]:
    signals = template.get("signals") if isinstance(template.get("signals"), dict) else {}
    names: set[str] = set()
    for bucket in ("principals", "factors"):
        items = signals.get(bucket)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                names.add(name.strip())
    for deriv in template.get("derivations") if isinstance(template.get("derivations"), list) else []:
        if not isinstance(deriv, dict):
            continue
        name = deriv.get("name")
        if isinstance(name, str) and name.strip():
            names.add(name.strip())
    return names


def _datasource_id_for_catalog_id(catalog_id: str) -> str:
    # Deterministic datasource id derived from catalog_id.
    # Example: ducklake.wallet_balance_window -> ds_ducklake_wallet_balance_window
    cleaned = catalog_id.strip().lower().replace(".", "_")
    return f"ds_{cleaned}"


def _default_binding_for_param(param_name: str) -> str:
    name = param_name.strip()
    if name == "target_keys":
        return "$.targets.keys"
    if name == "as_of":
        return "$.schedule.effective_as_of"
    if name == "window_duration":
        return "{{window_duration}}"
    if name == "network":
        return "$.partition.network"
    if name == "subnet":
        return "$.partition.subnet"
    if name == "chain_id":
        return "$.partition.chain_id"
    raise AlertTemplateCompileError(f"Missing binding rule for datasource param {param_name!r}")


def _collect_catalog_ids(template: Dict[str, Any]) -> list[str]:
    """
    Determine which catalog datasources are required.

    For v1 implementation, we treat signals[].update_sources[].ref as a catalog_id.
    """

    catalog_ids: list[str] = []
    signals = template.get("signals") if isinstance(template.get("signals"), dict) else {}
    for bucket in ("principals", "factors"):
        items = signals.get(bucket)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            sources = item.get("update_sources")
            if not isinstance(sources, list):
                continue
            for src in sources:
                if not isinstance(src, dict):
                    continue
                ref = src.get("ref")
                if isinstance(ref, str) and ref.strip() and ref.strip() not in catalog_ids:
                    catalog_ids.append(ref.strip())
    return catalog_ids


def _collect_catalog_ids_from_text(template: Dict[str, Any]) -> list[str]:
    """
    Fallback: if the template omitted signal definitions, try to recover required
    catalog_ids by scanning string fields for allowlisted catalog IDs.

    This is intentionally conservative:
    - only allowlisted catalog IDs are considered
    - matching is substring-based over string leaf values
    """

    allowlisted: list[str] = []
    for entry in list_compiler_catalog_entries():
        if isinstance(entry, dict) and isinstance(entry.get("catalog_id"), str):
            cid = entry.get("catalog_id", "").strip()
            if cid:
                allowlisted.append(cid)
    if not allowlisted:
        return []

    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
            return
        if isinstance(node, list):
            for v in node:
                walk(v)
            return
        if isinstance(node, str):
            for cid in allowlisted:
                if cid in node:
                    found.add(cid)
            return

    walk(template)
    return sorted(found)


def _infer_catalog_ids_from_expr(template: Dict[str, Any]) -> list[str]:
    """
    Fallback: infer required catalog_ids from expression references.

    If templates omit signals.update_sources but reference `signals.<id>.<column>` or
    similar shorthands, we infer the datasource by column name.

    Determinism rule:
    - A referenced column must exist in exactly one allowlisted datasource, otherwise
      compilation fails with a collision/ambiguity error.
    """

    entries = list_compiler_catalog_entries()
    topics: dict[str, list[str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("catalog_id")
        schema = entry.get("result_schema")
        if not isinstance(cid, str) or not cid.strip():
            continue
        cols: list[dict[str, Any]] = []
        if isinstance(schema, dict) and isinstance(schema.get("columns"), list):
            cols = [c for c in schema.get("columns") if isinstance(c, dict)]
        for col in cols:
            name = col.get("name")
            if isinstance(name, str) and name.strip():
                topics.setdefault(name.strip(), []).append(cid.strip())

    if not topics:
        return []

    required_cols: set[str] = set()

    def consider_text(text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        # Match "signals.<id>.<col>" or "$.signals.<id>.<col>" and take the column suffix.
        if cleaned.startswith("$.signals.") or cleaned.startswith("$.signal.") or cleaned.startswith("signals.") or cleaned.startswith("signal."):
            col = cleaned.split(".")[-1].strip()
            if col in topics:
                required_cols.add(col)
            return
        # Match "<anything>.<col>" shorthands and take the suffix.
        if cleaned.count(".") == 1 and not cleaned.startswith("$."):
            _prefix, _sep, col = cleaned.partition(".")
            col = col.strip()
            if col in topics:
                required_cols.add(col)
            return
        # Bare identifier that matches exactly one known column name.
        if _IDENTIFIER_RE.match(cleaned) and cleaned in topics:
            required_cols.add(cleaned)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            # Expr node
            if "op" in node:
                walk(node.get("left"))
                walk(node.get("right"))
                values = node.get("values")
                if isinstance(values, list):
                    for v in values:
                        walk(v)
                return
            # Operand wrappers (LLM may emit {"ref": "..."} / {"literal": 1})
            if isinstance(node.get("ref"), str):
                consider_text(str(node.get("ref")))
                return
            return
        if isinstance(node, list):
            for v in node:
                walk(v)
            return
        if isinstance(node, str):
            consider_text(node)
            return
        return

    trigger = template.get("trigger") if isinstance(template.get("trigger"), dict) else {}
    walk(trigger.get("condition_ast"))

    if not required_cols:
        return []

    selected: set[str] = set()
    for col in sorted(required_cols):
        cids = sorted(set(topics.get(col) or []))
        if len(cids) == 1:
            selected.add(cids[0])
            continue
        if len(cids) > 1:
            raise AlertTemplateCompileError(
                f"Signal column name collision for {col!r}; cannot infer datasource deterministically"
            )

    return sorted(selected)


def _build_signal_ref_map(
    *,
    catalog_ids: list[str],
) -> dict[str, str]:
    """
    Map signal names (which also correspond to datasource output columns) to
    executable JSONPath refs.

    Resolution rule (v1): signal name must match a column in exactly one selected datasource.
    """

    mapping: dict[str, str] = {}
    collisions: dict[str, list[str]] = {}

    for catalog_id in catalog_ids:
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            continue
        ds_id = _datasource_id_for_catalog_id(catalog_id)
        for col in entry.result_schema.columns:
            col_name = col.name
            ref = f"$.datasources.{ds_id}.{col_name}"
            if col_name in mapping and mapping[col_name] != ref:
                collisions.setdefault(col_name, []).extend([mapping[col_name], ref])
            else:
                mapping[col_name] = ref

    if collisions:
        # Keep the error message stable.
        first = sorted(collisions.items(), key=lambda kv: kv[0])[0]
        raise AlertTemplateCompileError(
            f"Signal column name collision for {first[0]!r}; cannot resolve deterministically"
        )

    return mapping


def _normalize_operand(value: Any, signal_ref_map: dict[str, str]) -> Any:
    if isinstance(value, dict) and "op" in value:
        return _normalize_expr(value, signal_ref_map)
    if isinstance(value, dict):
        # LLMs sometimes emit operand wrapper objects rather than raw literals/refs.
        # Normalize these into the supported scalar forms so compilation is deterministic.
        if isinstance(value.get("ref"), str) and value.get("ref", "").strip():
            return _normalize_operand(str(value.get("ref")), signal_ref_map)
        if "literal" in value:
            return value.get("literal")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        # Keep variable placeholders and explicit JSONPath refs.
        if text.startswith("{{") and text.endswith("}}"):
            return text
        if text.startswith("$.datasources.") or text.startswith("$.enrichment.") or text.startswith("$.tx."):
            return text
        # Legacy/LLM alias: "$.signals.<signal_id>.<column>" -> datasource column ref.
        if text.startswith("$.signals.") or text.startswith("$.signal."):
            candidate = text.split(".")[-1].strip()
            mapped = signal_ref_map.get(candidate)
            if mapped:
                return mapped
        if text.startswith("signals.") or text.startswith("signal."):
            candidate = text.split(".")[-1].strip()
            mapped = signal_ref_map.get(candidate)
            if mapped:
                return mapped
        # Common LLM shorthand: "<signal>.<column>" where the suffix is a datasource column name.
        #
        # Example: "s_tx_count_24h.tx_count_24h" should map to the selected datasource column
        # "tx_count_24h". We intentionally do NOT treat `tx.*` as datasource shorthand.
        if not text.startswith("$.") and text.count(".") == 1:
            prefix, suffix = text.split(".", 1)
            if prefix.strip().lower() not in {
                "tx",
                "trigger",
                "vars",
                "var",
                "user",
                "user_inputs",
                "schedule",
                "targets",
                "enrichment",
                "datasources",
                "datasource",
            }:
                mapped = signal_ref_map.get(suffix.strip())
                if mapped:
                    return mapped
        # Allow shorthand signal refs: "$.<name>" or "<name>"
        if text.startswith("$.") and text.count(".") == 1:
            candidate = text[2:]
        else:
            candidate = text
        mapped = signal_ref_map.get(candidate)
        if mapped:
            return mapped
        return text
    return value


def _normalize_expr(expr: Dict[str, Any], signal_ref_map: dict[str, str]) -> Dict[str, Any]:
    op = expr.get("op")
    if not isinstance(op, str) or not op.strip():
        raise AlertTemplateCompileError("Expression op must be a non-empty string")
    normalized: dict[str, Any] = {"op": op.strip()}
    if "left" in expr:
        normalized["left"] = _normalize_operand(expr.get("left"), signal_ref_map)
    if "right" in expr:
        normalized["right"] = _normalize_operand(expr.get("right"), signal_ref_map)
    if "values" in expr:
        values = expr.get("values")
        if isinstance(values, list):
            normalized["values"] = [_normalize_operand(v, signal_ref_map) for v in values]
        else:
            normalized["values"] = values
    return normalized


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_NUMERIC_LITERAL_RE = re.compile(r"^-?(?:\\d+)(?:\\.\\d+)?$")


def _find_suspicious_string_operands(expr: Any) -> list[str]:
    """
    Catch string operands that are likely intended as signal refs but were not normalized.

    We allow string literals only when explicitly compared to an explicit JSONPath (e.g.
    `$.tx.method_selector == "0xa9059cbb"`). Everywhere else, free-form identifiers and
    dotted refs are treated as suspicious and should fail compilation deterministically.
    """

    suspicious: list[str] = []

    def is_allowed_literal(text: str, *, sibling: Any, op: str) -> bool:
        if not text:
            return True
        if text.startswith("{{") and text.endswith("}}"):
            return True
        if text.startswith("$."):
            return True
        if text.startswith("0x"):
            return True
        if _NUMERIC_LITERAL_RE.match(text):
            return True
        # Allow string literals only when compared directly against explicit JSONPath.
        if op in {"eq", "neq"} and isinstance(sibling, str) and sibling.strip().startswith("$."):
            return True
        return False

    def walk(node: Any) -> None:
        if isinstance(node, dict) and "op" in node:
            op = str(node.get("op") or "").strip()
            left = node.get("left")
            right = node.get("right")
            if isinstance(left, str):
                text = left.strip()
                if not is_allowed_literal(text, sibling=right, op=op):
                    if "." in text or _IDENTIFIER_RE.match(text):
                        suspicious.append(text)
            if isinstance(right, str):
                text = right.strip()
                if not is_allowed_literal(text, sibling=left, op=op):
                    if "." in text or _IDENTIFIER_RE.match(text):
                        suspicious.append(text)
            walk(left)
            walk(right)
            values = node.get("values")
            if isinstance(values, list):
                for v in values:
                    if isinstance(v, str):
                        text = v.strip()
                        if not is_allowed_literal(text, sibling=None, op=op):
                            if "." in text or _IDENTIFIER_RE.match(text):
                                suspicious.append(text)
                    walk(v)
            return

        if isinstance(node, list):
            for v in node:
                walk(v)
            return

        # Leaf string nodes are handled via their parent op above.
        return

    walk(expr)
    return sorted(set(suspicious))


def _find_unresolved_signal_refs(expr: Any, *, known_names: set[str]) -> list[str]:
    """
    Catch common "shorthand" identifier refs that should have been normalized to JSONPaths.

    This makes compilation fail fast (deterministically) instead of emitting an executable
    that will later fail at runtime due to missing columns/refs.
    """

    unresolved: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict) and "op" in node:
            walk(node.get("left"))
            walk(node.get("right"))
            values = node.get("values")
            if isinstance(values, list):
                for v in values:
                    walk(v)
            return

        if isinstance(node, list):
            for v in node:
                walk(v)
            return

        if not isinstance(node, str):
            return

        text = node.strip()
        if not text:
            return
        if text.startswith("{{") and text.endswith("}}"):
            return
        if text.startswith("$."):
            # Explicit JSONPath refs are always allowed.
            # However, "$.<name>" is ambiguous shorthand and should have been normalized.
            if text.count(".") == 1:
                candidate = text[2:]
                if candidate in known_names:
                    unresolved.append(text)
            return

        # Bare identifier-like values are treated as signal refs (not string literals).
        if _IDENTIFIER_RE.match(text) and text in known_names:
            unresolved.append(text)

    walk(expr)
    # Keep the list stable for error messages.
    return sorted(set(unresolved))


def compile_template_to_executable(
    template: Dict[str, Any],
    *,
    ctx: CompileContext,
) -> Dict[str, Any]:
    """
    Deterministically compile an AlertTemplate (v2) into an AlertExecutable v1 artifact.

    This is intentionally conservative: if the plan cannot be resolved against the
    allowlisted registry, compilation fails with a structured error.
    """

    if template.get("schema_version") != "alert_template_v2":
        raise AlertTemplateCompileError("Unsupported template schema_version")

    template_version = int(ctx.template_version)
    if template_version < 1:
        raise AlertTemplateCompileError("template_version must be >= 1")

    target_kind = template.get("target_kind")
    if not isinstance(target_kind, str) or not target_kind.strip():
        raise AlertTemplateCompileError("target_kind is required")

    scope = template.get("scope") if isinstance(template.get("scope"), dict) else {}
    networks = scope.get("networks") if isinstance(scope.get("networks"), list) else []
    networks = [n for n in networks if isinstance(n, str) and n.strip()]

    catalog_ids = _collect_catalog_ids(template)
    if not catalog_ids:
        catalog_ids = _collect_catalog_ids_from_text(template)
    if not catalog_ids:
        catalog_ids = _infer_catalog_ids_from_expr(template)
    datasources: list[dict[str, Any]] = []
    for catalog_id in catalog_ids:
        entry = get_catalog_entry(catalog_id)
        if entry is None or not entry.enabled:
            raise AlertTemplateCompileError(f"Unknown or disabled catalog_id: {catalog_id!r}")

        ds_id = _datasource_id_for_catalog_id(catalog_id)
        bindings: dict[str, Any] = {}
        for param in entry.params:
            bindings[param.name] = _default_binding_for_param(param.name)

        datasources.append(
            {
                "id": ds_id,
                "catalog_id": entry.catalog_id,
                "bindings": bindings,
                "cache_ttl_secs": int(entry.cache_policy.get("default_ttl_secs", 30)),
                "timeout_ms": int(entry.timeouts.get("default_timeout_ms", 1500)),
            }
        )

    # Ensure stable ordering.
    datasources.sort(key=lambda d: str(d.get("id")))

    signal_ref_map = _build_signal_ref_map(catalog_ids=catalog_ids)

    enrichments: list[dict[str, Any]] = []
    for deriv in template.get("derivations") if isinstance(template.get("derivations"), list) else []:
        if not isinstance(deriv, dict):
            continue
        name = deriv.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        expr = deriv.get("expr_ast")
        if not isinstance(expr, dict):
            raise AlertTemplateCompileError(f"Derivation {name!r} missing expr_ast")
        compiled_expr = _normalize_expr(expr, signal_ref_map)
        enrichments.append(
            {
                "id": f"en_{name.strip()}",
                "expr": compiled_expr,
                "output": f"$.enrichment.{name.strip()}",
            }
        )

    enrichments.sort(key=lambda e: str(e.get("id")))

    # Allow condition_ast to reference derivation outputs by name.
    for enr in enrichments:
        out = enr.get("output")
        enr_id = enr.get("id")
        if not isinstance(out, str) or not out.startswith("$.enrichment."):
            continue
        # en_<name> -> <name>
        if isinstance(enr_id, str) and enr_id.startswith("en_"):
            name = enr_id[len("en_") :]
            if name and name not in signal_ref_map:
                signal_ref_map[name] = out

    trigger = template.get("trigger") if isinstance(template.get("trigger"), dict) else {}
    condition_ast = trigger.get("condition_ast")
    if not isinstance(condition_ast, dict):
        raise AlertTemplateCompileError("trigger.condition_ast must be an expression object")
    compiled_condition = _normalize_expr(condition_ast, signal_ref_map)

    suspicious: list[str] = []
    for enr in enrichments:
        suspicious.extend(_find_suspicious_string_operands(enr.get("expr")))
    suspicious.extend(_find_suspicious_string_operands(compiled_condition))
    if suspicious:
        first = suspicious[0]
        raise AlertTemplateCompileError(
            f"Suspicious string operand {first!r}. Use explicit JSONPath refs (e.g. $.tx.* / $.datasources.*), "
            "or ensure the operand maps to a selected allowlisted datasource column."
        )

    # Compile pruning hints to an EVM-style pruning block (scheduler stage-1).
    pruning = trigger.get("pruning_hints") if isinstance(trigger.get("pruning_hints"), dict) else {}
    evm_hints = pruning.get("evm") if isinstance(pruning.get("evm"), dict) else {}
    method_selectors = evm_hints.get("method_selector_any_of")
    topic0s = evm_hints.get("event_topic0_any_of")
    addrs = evm_hints.get("contract_addresses_any_of")

    trigger_pruning = {
        "evm": {
            "chain_ids": _chain_ids_from_networks(networks),
            "tx_type": str(evm_hints.get("tx_type") or "any"),
            "from": {"any_of": [], "labels": [], "not": []},
            "to": {"any_of": [a for a in (addrs or []) if isinstance(a, str)], "labels": [], "not": []},
            "method": {
                "selector_any_of": [s for s in (method_selectors or []) if isinstance(s, str)],
                "name_any_of": [],
                "required": bool(method_selectors),
            },
            "event": {
                "topic0_any_of": [t for t in (topic0s or []) if isinstance(t, str)],
                "name_any_of": [],
                "required": bool(topic0s),
            },
        }
    }

    # Variables are largely a passthrough; the compiler validates at save time elsewhere.
    variables = template.get("variables") if isinstance(template.get("variables"), list) else []
    variables = [v for v in variables if isinstance(v, dict)]

    notification = template.get("notification") if isinstance(template.get("notification"), dict) else {}
    notification_template = {
        "title": str(notification.get("title_template") or "").strip(),
        "body": str(notification.get("body_template") or "").strip(),
    }

    dedupe = trigger.get("dedupe") if isinstance(trigger.get("dedupe"), dict) else {}
    cooldown_seconds = int(dedupe.get("cooldown_seconds") or 0)
    cooldown_key_template = str(dedupe.get("key_template") or "{{instance_id}}:{{target.key}}").strip()

    known_names = _collect_signal_names(template)
    # Derivations are materialized to `$.enrichment.<name>`, so include those names too.
    for enr in enrichments:
        out = enr.get("output")
        if isinstance(out, str) and out.startswith("$.enrichment."):
            known_names.add(out[len("$.enrichment.") :])

    # If the template references known signal names without a datasource (or without a matching
    # selected datasource column), fail fast with a deterministic error.
    unresolved: list[str] = []
    for enr in enrichments:
        unresolved.extend(_find_unresolved_signal_refs(enr.get("expr"), known_names=known_names))
    unresolved.extend(_find_unresolved_signal_refs(compiled_condition, known_names=known_names))
    if unresolved:
        first = unresolved[0]
        raise AlertTemplateCompileError(
            f"Unresolved signal reference {first!r}. Use an explicit JSONPath (e.g. $.tx.* / $.enrichment.*) "
            "or ensure the signal maps to a selected allowlisted datasource."
        )

    # Deterministic executable_id (UUIDv5) based on plan identity and pinned snapshot.
    name = f"{ctx.template_id}:{template_version}:{ctx.registry_snapshot.get('hash')}"
    executable_id = uuid.uuid5(uuid.NAMESPACE_URL, name)

    return {
        "schema_version": "alert_executable_v1",
        "executable_id": str(executable_id),
        "template": {
            "schema_version": "alert_template_v2",
            "template_id": str(ctx.template_id),
            "fingerprint": str(template.get("fingerprint") or "").strip(),
            "version": template_version,
        },
        "registry_snapshot": dict(ctx.registry_snapshot),
        "target_kind": target_kind.strip(),
        "variables": variables,
        "trigger_pruning": trigger_pruning,
        "datasources": datasources,
        "enrichments": enrichments,
        "conditions": {"all": [compiled_condition], "any": [], "not": []},
        "notification_template": notification_template,
        "action": {
            "notification_policy": "per_matched_target",
            "cooldown_secs": cooldown_seconds,
            "cooldown_key_template": cooldown_key_template,
            "dedupe_key_template": "{{run_id}}:{{instance_id}}:{{target.key}}",
        },
        "performance": {},
        "warnings": [],
    }
