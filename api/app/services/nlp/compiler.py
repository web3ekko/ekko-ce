from __future__ import annotations

import json
import logging
import re
import time
import uuid
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional

from django.conf import settings
from django.utils import timezone

from app.services.alert_templates.compilation import (
    AlertTemplateCompileError,
    CompileContext,
    compile_template_to_executable,
)
from app.services.alert_templates.hashing import (
    compute_template_fingerprint,
    compute_template_spec_hash,
)
from app.services.alert_templates.registry_snapshot import get_registry_snapshot
from app.services.datasource_catalog import get_catalog_entry, list_compiler_catalog_entries
from app.services.nlp.llm_client import get_llm_client
from app.services.nlp.pipelines import (
    DEFAULT_PIPELINE_ID,
    PLAN_PIPELINE_ID,
    PipelineConfig,
    PipelineConfigError,
    get_pipeline_config,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProposedSpecBuildContext:
    job_id: str
    client_request_id: Optional[str]
    expires_at: str
    pipeline_id: str
    pipeline_version: str


@dataclass(frozen=True)
class LLMParseResult:
    parsed: Dict[str, Any]
    raw_response: Optional[str]


class ProposedSpecCompilationError(RuntimeError):
    def __init__(self, message: str, raw_response: Optional[str] = None):
        super().__init__(message)
        self.raw_response = raw_response


def _truncate_nl(nl_description: str) -> str:
    max_chars = int(getattr(settings, "NLP_NL_DESCRIPTION_MAX_CHARS", 500))
    text = str(nl_description).strip()
    return text[:max_chars] if len(text) > max_chars else text


def _normalize_llm_response(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    if isinstance(raw, str):
        return raw
    return str(raw)


def _truncate_with_ellipsis(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return f"{text[: max_chars - 3].rstrip()}..."


def _default_template_name(nl_description: str) -> str:
    text = str(nl_description).strip()
    if not text:
        return "Alert Template"
    max_chars = int(getattr(settings, "NLP_TEMPLATE_NAME_MAX_CHARS", 80))
    return _truncate_with_ellipsis(text, max_chars)


def _default_template_description(nl_description: str) -> str:
    text = str(nl_description).strip()
    if not text:
        return "Alert generated from natural language input."
    prefix = "Alert generated from: "
    max_chars = int(getattr(settings, "NLP_TEMPLATE_DESCRIPTION_MAX_CHARS", 160))
    available = max_chars - len(prefix)
    if available <= 0:
        return prefix.rstrip()
    return f"{prefix}{_truncate_with_ellipsis(text, available)}"


_NOTIFICATION_LABEL_OVERRIDES = {
    "balance_latest": "Balance",
    "pct_change_window": "Balance change",
    "tx_count_24h": "Transactions (24h)",
    "tx_count": "Transactions",
    "value_native": "Transaction value",
    "value_wei": "Transaction value (wei)",
    "gas_fee_native": "Gas fee",
}

_NOTIFICATION_OP_PHRASES = {
    "gt": "above",
    "gte": "at or above",
    "lt": "below",
    "lte": "at or below",
    "eq": "equal to",
    "neq": "not equal to",
}


def _titleize_metric_name(value: str) -> str:
    text = re.sub(r"[_\-]+", " ", str(value or "").strip())
    if not text:
        return ""
    lowered = text.lower()
    if lowered.startswith("tx "):
        text = f"Transaction {text[3:]}".strip()
    return text[:1].upper() + text[1:]


def _notification_ref_label_and_placeholder(ref: Any) -> tuple[str, str]:
    if not isinstance(ref, str):
        return "", ""
    text = ref.strip()
    if not text:
        return "", ""
    if text.startswith("$."):
        text = text[2:]
    if text.startswith("datasources.") or text.startswith("enrichment."):
        text = text.split(".")[-1]

    if text.startswith("tx."):
        field = text.split(".", 1)[1] if "." in text else text
        label = _NOTIFICATION_LABEL_OVERRIDES.get(field) or _titleize_metric_name(field)
        return label, f"{{{{tx.{field}}}}}"
    if text.startswith("target."):
        field = text.split(".", 1)[1] if "." in text else text
        label = _titleize_metric_name(field)
        return label, f"{{{{target.{field}}}}}"

    if "." in text:
        leaf = text.split(".")[-1]
    else:
        leaf = text
    label = _NOTIFICATION_LABEL_OVERRIDES.get(leaf) or _titleize_metric_name(leaf)
    return label, f"{{{{{leaf}}}}}"


def _notification_rhs_text(value: Any, variable_ids: set[str]) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        if text.startswith("{{") and text.endswith("}}"):
            return text
        if text.startswith("$.") or text.startswith("tx.") or text.startswith("target."):
            _, placeholder = _notification_ref_label_and_placeholder(text)
            return placeholder
        if text in variable_ids:
            return f"{{{{{text}}}}}"
        return text
    return ""


def _build_default_notification_templates(
    *,
    conditions: list[dict[str, Any]],
    variable_ids: set[str],
) -> tuple[str, str]:
    if not conditions:
        return (
            "Alert triggered: {{target.short}}",
            "Condition met for {{target.short}}.",
        )

    first = conditions[0]
    left_label, left_placeholder = _notification_ref_label_and_placeholder(first.get("left"))
    op_phrase = _NOTIFICATION_OP_PHRASES.get(str(first.get("op") or "").strip().lower(), "triggered")
    right_text = _notification_rhs_text(first.get("right"), variable_ids)

    title_label = left_label or "Alert"
    title = f"{title_label} alert: {{target.short}}"

    if len(conditions) > 1:
        return title, "Multiple conditions met for {{target.short}}."

    if not left_placeholder:
        return title, "Condition met for {{target.short}}."

    body = f"{title_label} for {{target.short}} is {left_placeholder}"
    if right_text:
        body = f"{body} ({op_phrase} {right_text})"
    return title, body


_DEFAULT_BINDINGS: Dict[str, str] = {
    "target_keys": "$.targets.keys",
    "as_of": "$.schedule.effective_as_of",
    "window_duration": "24h",
}


_EXPR_OP_ALIASES = {
    ">": "gt",
    "greater_than": "gt",
    "greater-than": "gt",
    "greater": "gt",
    ">=": "gte",
    "greater_equal": "gte",
    "greater_or_equal": "gte",
    "greater_than_or_equal": "gte",
    "<": "lt",
    "less_than": "lt",
    "less-than": "lt",
    "less": "lt",
    "<=": "lte",
    "less_equal": "lte",
    "less_or_equal": "lte",
    "less_than_or_equal": "lte",
    "==": "eq",
    "=": "eq",
    "equals": "eq",
    "equal": "eq",
    "!=": "neq",
    "not_equal": "neq",
    "not_equals": "neq",
}

_LEGACY_TX_FIELD_MAP = {
    "tx_value": "value",
    "tx_value_wei": "value_wei",
    "tx_value_native": "value_native",
    "tx_from": "from",
    "tx_to": "to",
    "tx_hash": "hash",
    "tx_method_selector": "method_selector",
    "tx_gas_price": "gas_price",
    "tx_block_number": "block_number",
}

_TRIGGER_TX_FIELD_MAP = {
    "type": "tx_type",
    "selector": "method_selector",
    "method": "method_selector",
}

_VALID_VARIABLE_TYPES = {
    "boolean",
    "decimal",
    "duration",
    "enum",
    "enum_multi",
    "integer",
    "string",
}

_VARIABLE_TYPE_ALIASES = {
    "addr": "string",
    "address": "string",
    "bool": "boolean",
    "boolean": "boolean",
    "double": "decimal",
    "float": "decimal",
    "int": "integer",
    "integer": "integer",
    "number": "decimal",
    "numeric": "decimal",
    "str": "string",
    "string": "string",
    "target_key": "string",
}

_DECIMAL_HINTS = {
    "amount",
    "balance",
    "eth",
    "gas",
    "gwei",
    "price",
    "threshold",
    "usd",
    "usdc",
    "usdt",
    "value",
}

_INTEGER_HINTS = {
    "block",
    "blocks",
    "count",
    "confirm",
    "confirmations",
    "height",
    "tx",
    "txn",
}

_STRING_HINTS = {
    "address",
    "recipient",
    "sender",
    "wallet",
}


def _normalize_expr_op(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return _EXPR_OP_ALIASES.get(normalized, normalized)


def _infer_variable_type(var: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("id", "name", "label"):
        value = var.get(key)
        if isinstance(value, str):
            parts.append(value.lower())
    combined = " ".join(parts)
    if "address" in combined:
        return "string"
    for hint in _DECIMAL_HINTS:
        if hint in combined:
            return "decimal"
    for hint in _INTEGER_HINTS:
        if hint in combined:
            return "integer"
    for hint in _STRING_HINTS:
        if hint in combined:
            return "string"
    return "string"


def _normalize_variable_type(var: dict[str, Any], idx: int, warnings: list[str]) -> None:
    var_type = var.get("type")
    normalized: Optional[str] = None
    if isinstance(var_type, str):
        lowered = var_type.strip().lower()
        normalized = _VARIABLE_TYPE_ALIASES.get(lowered, lowered)
        if normalized not in _VALID_VARIABLE_TYPES:
            normalized = None
    if normalized is None:
        inferred = _infer_variable_type(var)
        var["type"] = inferred
        warnings.append(f"AlertTemplate.variables[{idx}].type inferred as {inferred}.")
    elif normalized != var_type:
        var["type"] = normalized
        warnings.append(
            f"AlertTemplate.variables[{idx}].type coerced from {var_type} to {normalized}."
        )


def _default_binding_value(param_name: str) -> str:
    return _DEFAULT_BINDINGS.get(param_name, f"{{{{{param_name}}}}}")


def _normalize_template_identity(template: Dict[str, Any], nl_description: str) -> None:
    warnings = template.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
        template["warnings"] = warnings

    name = template.get("name")
    if not isinstance(name, str) or not name.strip():
        template["name"] = _default_template_name(nl_description)
        warnings.append("AlertTemplate.name missing; defaulted from prompt.")

    description = template.get("description")
    if not isinstance(description, str) or not description.strip():
        template["description"] = _default_template_description(nl_description)
        warnings.append("AlertTemplate.description missing; defaulted from prompt.")


def _sanitize_template_datasources(template: Dict[str, Any]) -> None:
    warnings = template.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
        template["warnings"] = warnings

    raw = template.get("datasources")
    if raw is None:
        return
    if isinstance(raw, dict):
        raw_list = [raw]
    elif isinstance(raw, list):
        raw_list = raw
    else:
        warnings.append("AlertTemplate.datasources invalid; defaulted to empty list.")
        template["datasources"] = []
        return

    cleaned: list[dict[str, Any]] = []
    for idx, ds in enumerate(raw_list):
        if not isinstance(ds, dict):
            warnings.append(f"AlertTemplate.datasources[{idx}] dropped; expected object.")
            continue
        ds_id = ds.get("id")
        if not isinstance(ds_id, str) or not ds_id.strip():
            warnings.append(f"AlertTemplate.datasources[{idx}] dropped; missing id.")
            continue
        catalog_id = ds.get("catalog_id")
        if not isinstance(catalog_id, str) or not catalog_id.strip():
            warnings.append(f"AlertTemplate.datasources[{idx}] dropped; missing catalog_id.")
            continue
        entry = get_catalog_entry(catalog_id.strip())
        if entry is None:
            warnings.append(
                f"AlertTemplate.datasources[{idx}] dropped; unknown catalog_id {catalog_id!r}."
            )
            continue

        bindings = ds.get("bindings")
        if not isinstance(bindings, dict):
            bindings = {}

        param_names = {param.name for param in entry.params}
        unknown_keys = [key for key in bindings.keys() if key not in param_names]
        if unknown_keys:
            for key in unknown_keys:
                bindings.pop(key, None)
            warnings.append(
                f"AlertTemplate.datasources[{idx}] dropped unknown bindings: {', '.join(sorted(unknown_keys))}."
            )

        for key, value in list(bindings.items()):
            if isinstance(value, (str, int, float, bool)) or value is None:
                continue
            bindings[key] = _default_binding_value(key)
            warnings.append(
                f"AlertTemplate.datasources[{idx}].bindings.{key} invalid; defaulted to placeholder."
            )

        for param in entry.params:
            if param.required and param.name not in bindings:
                bindings[param.name] = _default_binding_value(param.name)
                warnings.append(
                    f"AlertTemplate.datasources[{idx}] missing required binding '{param.name}'; defaulted."
                )

        ds["bindings"] = bindings
        cleaned.append(ds)

    template["datasources"] = cleaned


def _sanitize_template_enrichments(template: Dict[str, Any]) -> None:
    warnings = template.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
        template["warnings"] = warnings

    raw = template.get("enrichments")
    if raw is None:
        return
    if isinstance(raw, dict):
        raw_list = [raw]
    elif isinstance(raw, list):
        raw_list = raw
    else:
        warnings.append("AlertTemplate.enrichments invalid; defaulted to empty list.")
        template["enrichments"] = []
        return

    cleaned: list[dict[str, Any]] = []
    for idx, enrichment in enumerate(raw_list):
        if not isinstance(enrichment, dict):
            warnings.append(f"AlertTemplate.enrichments[{idx}] dropped; expected object.")
            continue
        en_id = enrichment.get("id")
        if not isinstance(en_id, str) or not en_id.strip():
            warnings.append(f"AlertTemplate.enrichments[{idx}] dropped; missing id.")
            continue
        output = enrichment.get("output")
        if not isinstance(output, str) or not output.strip():
            warnings.append(f"AlertTemplate.enrichments[{idx}] dropped; missing output.")
            continue
        if "expr" not in enrichment:
            warnings.append(f"AlertTemplate.enrichments[{idx}] dropped; missing expr.")
            continue
        cleaned.append(enrichment)

    template["enrichments"] = cleaned


def _coerce_literal_value(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return value
        if cleaned.startswith("0x"):
            return cleaned
        if re.fullmatch(r"-?\d+", cleaned):
            try:
                return int(cleaned)
            except ValueError:
                return cleaned
        if re.fullmatch(r"-?\d+\.\d+", cleaned):
            try:
                return float(cleaned)
            except ValueError:
                return cleaned
        return cleaned
    return value


def _coerce_ref_string(ref: str, variable_ids: set[str]) -> str:
    cleaned = ref.strip()
    if not cleaned:
        return ref
    if cleaned in variable_ids:
        return f"{{{{{cleaned}}}}}"
    if cleaned.startswith("vars."):
        variable = cleaned.split(".", 1)[-1]
        return f"{{{{{variable}}}}}"
    if cleaned.startswith("user_inputs."):
        variable = cleaned.split(".", 1)[-1]
        return f"{{{{{variable}}}}}"
    if cleaned.startswith("trigger.tx."):
        field = cleaned.split("trigger.tx.", 1)[-1]
        field = _TRIGGER_TX_FIELD_MAP.get(field, field)
        return f"$.tx.{field}"
    if cleaned.startswith("tx."):
        field = cleaned.split("tx.", 1)[-1]
        field = _TRIGGER_TX_FIELD_MAP.get(field, field)
        return f"$.tx.{field}"
    if cleaned.startswith("$."):
        return cleaned
    if cleaned.startswith("ds."):
        cleaned = cleaned.split(".", 1)[-1]
    if cleaned.startswith("datasources."):
        cleaned = cleaned.split(".", 1)[-1]
    if cleaned.startswith("datasource."):
        cleaned = cleaned.split(".", 1)[-1]
    if "." in cleaned:
        return f"$.datasources.{cleaned}"
    return f"{{{{{cleaned}}}}}"


def _extract_address_from_operand(operand: Any) -> Optional[str]:
    candidate: Optional[str] = None
    if isinstance(operand, str):
        candidate = operand.strip()
    elif isinstance(operand, dict):
        op_value = operand.get("op")
        if op_value is None and "operator" in operand:
            op_value = operand.get("operator")
        if op_value is None and "type" in operand:
            op_value = operand.get("type")
        normalized_op = _normalize_expr_op(op_value)
        if normalized_op in {"value", "const", "literal", "string"}:
            raw = operand.get("value")
            if raw is None and "left" in operand:
                raw = operand.get("left")
            if raw is None and "right" in operand:
                raw = operand.get("right")
            if isinstance(raw, str):
                candidate = raw.strip()
        elif normalized_op == "ref":
            values = operand.get("values")
            if isinstance(values, list) and values:
                ref = values[0]
                if isinstance(ref, str):
                    candidate = ref.strip()
        elif isinstance(operand.get("value"), str):
            candidate = operand.get("value").strip()
    elif isinstance(operand, list):
        for item in operand:
            candidate = _extract_address_from_operand(item)
            if candidate:
                break
    if candidate and candidate.startswith("0x") and len(candidate) >= 10:
        return candidate
    return None


def _coerce_trigger_filter(value: Any) -> Dict[str, list]:
    default = {"any_of": [], "labels": [], "not": []}
    if value is None:
        return default
    if isinstance(value, dict):
        if {"any_of", "labels", "not"}.issubset(value):
            any_of = [v.strip() for v in value.get("any_of", []) if isinstance(v, str) and v.strip()]
            labels = [v.strip() for v in value.get("labels", []) if isinstance(v, str) and v.strip()]
            not_values = [v.strip() for v in value.get("not", []) if isinstance(v, str) and v.strip()]
            return {"any_of": any_of, "labels": labels, "not": not_values}
        addresses = value.get("addresses")
        if isinstance(addresses, list):
            any_of = [v.strip() for v in addresses if isinstance(v, str) and v.strip()]
            if any_of:
                return {"any_of": any_of, "labels": [], "not": []}
        op_value = value.get("op")
        if op_value is None and "operator" in value:
            op_value = value.get("operator")
        if op_value is None and "type" in value:
            op_value = value.get("type")
        normalized_op = _normalize_expr_op(op_value)
        if normalized_op in {"any", "all"}:
            return default
        if normalized_op in {"eq"}:
            addr = _extract_address_from_operand(value.get("left"))
            if addr is None:
                addr = _extract_address_from_operand(value.get("right"))
            if addr is None:
                addr = _extract_address_from_operand(value.get("value"))
            if addr:
                return {"any_of": [addr], "labels": [], "not": []}
        if normalized_op in {"any_of", "or"}:
            values = value.get("values") or value.get("args") or []
            if isinstance(values, list):
                any_of = []
                for item in values:
                    addr = _extract_address_from_operand(item)
                    if addr:
                        any_of.append(addr)
                if any_of:
                    return {"any_of": any_of, "labels": [], "not": []}
        addr = _extract_address_from_operand(value.get("value"))
        if addr:
            return {"any_of": [addr], "labels": [], "not": []}
    if isinstance(value, list):
        any_of = [v.strip() for v in value if isinstance(v, str) and v.strip()]
        if any_of:
            return {"any_of": any_of, "labels": [], "not": []}
    if isinstance(value, str) and value.strip():
        return {"any_of": [value.strip()], "labels": [], "not": []}
    return default


def _coerce_legacy_operand(operand: Any, variable_ids: set[str]) -> Any:
    if isinstance(operand, dict):
        # Some stacks emit typed literal wrappers (e.g. {"type":"ExprV1Number","value":1.0}).
        # Normalize these to plain JSON primitives so ExprV1 stays minimal/deterministic.
        otype = operand.get("type")
        if isinstance(otype, str) and "value" in operand:
            tnorm = otype.strip().lower()
            if tnorm in {"exprv1number", "number"} and isinstance(operand.get("value"), (int, float)):
                return operand.get("value")
            if tnorm in {"exprv1string", "string"} and isinstance(operand.get("value"), str):
                return operand.get("value").strip()
            if tnorm in {"exprv1bool", "bool", "boolean"} and isinstance(operand.get("value"), bool):
                return operand.get("value")

        op_value = operand.get("op")
        if op_value is None and "operator" in operand:
            op_value = operand.get("operator")
        if op_value is None and "type" in operand:
            op_value = operand.get("type")
        normalized_op = _normalize_expr_op(op_value)
        # Some model/tooling stacks emit JSONPath operands as structured objects:
        # {"type":"jsonpath","path":"$.tx.value_native"} (or op="jsonpath"). Normalize
        # these into the string path expected by ExprV1.
        if normalized_op in {"jsonpath", "path"}:
            path = operand.get("path") or operand.get("value")
            if isinstance(path, str) and path.strip():
                return _coerce_ref_string(path, variable_ids)
        if normalized_op == "ref":
            values = operand.get("values")
            if isinstance(values, list) and values:
                ref = values[0]
                if isinstance(ref, str):
                    return _coerce_ref_string(ref, variable_ids)
            path = operand.get("path") or operand.get("value")
            if isinstance(path, str) and path.strip():
                return _coerce_ref_string(path, variable_ids)
            return operand
        if normalized_op in {"const", "literal", "value", "val", "string", "bigint", "number", "int", "integer", "decimal", "float"}:
            path = operand.get("path")
            if isinstance(path, str) and path.strip():
                return _coerce_ref_string(path, variable_ids)
            if "value" in operand:
                return _coerce_literal_value(operand.get("value"))
            if "left" in operand:
                return _coerce_literal_value(operand.get("left"))
            return _coerce_literal_value(operand.get("right"))
        if normalized_op == "var":
            name = operand.get("name") or operand.get("value")
            if isinstance(name, str) and name.strip():
                return f"{{{{{name.strip()}}}}}"
            return operand
        if isinstance(normalized_op, str) and normalized_op.startswith("tx."):
            field = normalized_op.split(".", 1)[-1]
            if field == "selector":
                field = "method_selector"
            path = operand.get("path")
            if isinstance(path, str) and path.strip():
                return f"$.tx.{path.strip()}"
            return f"$.tx.{field}"
        if isinstance(normalized_op, str) and normalized_op in _LEGACY_TX_FIELD_MAP:
            return f"$.tx.{_LEGACY_TX_FIELD_MAP[normalized_op]}"
        if isinstance(normalized_op, str) and normalized_op.startswith("tx_"):
            return f"$.tx.{normalized_op[3:]}"
        return _coerce_legacy_expr(operand, variable_ids)
    return operand


def _coerce_legacy_expr(expr: Any, variable_ids: set[str]) -> Any:
    if not isinstance(expr, dict):
        return expr
    op_value = expr.get("op")
    if op_value is None and "operator" in expr:
        op_value = expr.get("operator")
    if op_value is None and "type" in expr:
        op_value = expr.get("type")
    normalized_op = _normalize_expr_op(op_value)
    if normalized_op in {"passthrough", "noop", "identity"}:
        return None
    if normalized_op == "ref":
        return _coerce_legacy_operand(expr, variable_ids)
    if normalized_op in {
        "const",
        "literal",
        "value",
        "val",
        "string",
        "bigint",
        "number",
        "int",
        "integer",
        "decimal",
        "float",
    }:
        value = expr.get("value")
        if value is None and "left" in expr:
            value = expr.get("left")
        coerced_value = _coerce_literal_value(value)
        return {"op": "eq", "left": coerced_value, "right": coerced_value}
    if normalized_op == "var":
        name = expr.get("name") or expr.get("value")
        if isinstance(name, str) and name.strip():
            placeholder = f"{{{{{name.strip()}}}}}"
            return {"op": "eq", "left": placeholder, "right": placeholder}
    coerced = dict(expr)
    if normalized_op:
        coerced["op"] = normalized_op
    coerced.pop("operator", None)
    if isinstance(expr.get("values"), list):
        coerced["values"] = [_coerce_legacy_operand(v, variable_ids) for v in expr.get("values") or []]
    if isinstance(expr.get("args"), list):
        coerced["args"] = [_coerce_legacy_operand(v, variable_ids) for v in expr.get("args") or []]
    coerced["left"] = _coerce_legacy_operand(expr.get("left"), variable_ids)
    coerced["right"] = _coerce_legacy_operand(expr.get("right"), variable_ids)
    return coerced


def _coerce_legacy_template_shape(template: Dict[str, Any]) -> None:
    warnings = template.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
        template["warnings"] = warnings

    legacy_type = template.get("type")
    if "alert_type" not in template and isinstance(legacy_type, str) and legacy_type.strip():
        lowered = legacy_type.strip().lower()
        if lowered in {"alert", "generic", "template"}:
            template["alert_type"] = "wallet"
        elif "balance" in lowered or "wallet" in lowered or "account" in lowered:
            template["alert_type"] = "wallet"
        else:
            template["alert_type"] = lowered
        warnings.append("AlertTemplate.alert_type derived from legacy type field.")
    elif isinstance(template.get("alert_type"), str):
        alert_type = str(template.get("alert_type")).strip().lower()
        if alert_type in {"alert", "generic", "template"}:
            template["alert_type"] = "wallet"
            warnings.append("AlertTemplate.alert_type defaulted to wallet from generic value.")

    variables = template.get("variables")
    variable_ids: set[str] = set()
    if isinstance(variables, dict):
        converted: list[dict[str, Any]] = []
        for key, var in variables.items():
            if not isinstance(var, dict):
                continue
            if "id" not in var and isinstance(key, str):
                var["id"] = key
            converted.append(var)
        template["variables"] = converted
        variables = converted
        warnings.append("AlertTemplate.variables coerced from object to list.")
    if isinstance(variables, list):
        for idx, var in enumerate(variables):
            if not isinstance(var, dict):
                continue
            if "id" not in var and isinstance(var.get("name"), str):
                var["id"] = var["name"]
                warnings.append(f"AlertTemplate.variables[{idx}].id defaulted from name.")
            if "label" not in var and isinstance(var.get("id"), str):
                var["label"] = var["id"].replace("_", " ").title()
            if "required" not in var:
                var["required"] = False
            _normalize_variable_type(var, idx, warnings)
            if isinstance(var.get("id"), str):
                variable_ids.add(var["id"])

    datasources = template.get("datasources")
    if isinstance(datasources, list):
        for idx, ds in enumerate(datasources):
            if not isinstance(ds, dict):
                continue
            if "bindings" not in ds and isinstance(ds.get("params"), dict):
                ds["bindings"] = ds.get("params")
                ds.pop("params", None)
                warnings.append(f"AlertTemplate.datasources[{idx}].params renamed to bindings.")

    trigger_expr: Optional[dict] = None
    trigger = template.get("trigger")
    if isinstance(trigger, dict):
        raw_from = trigger.get("from")
        raw_to = trigger.get("to")
        tx_type = trigger.get("tx_type")
        if isinstance(tx_type, list):
            trigger["tx_type"] = next((t for t in tx_type if isinstance(t, str)), "any") or "any"
            warnings.append("AlertTemplate.trigger.tx_type coerced from list.")
        elif not isinstance(tx_type, str):
            trigger["tx_type"] = "any"
            warnings.append("AlertTemplate.trigger.tx_type defaulted to any.")
        if isinstance(trigger.get("from"), list):
            trigger["from"] = _coerce_trigger_filter(raw_from)
            warnings.append("AlertTemplate.trigger.from coerced from list.")
        if isinstance(trigger.get("to"), list):
            trigger["to"] = _coerce_trigger_filter(raw_to)
            warnings.append("AlertTemplate.trigger.to coerced from list.")
        from_value = trigger.get("from")
        if isinstance(from_value, dict) and isinstance(from_value.get("addresses"), list):
            addresses = [
                addr.strip()
                for addr in from_value.get("addresses", [])
                if isinstance(addr, str) and addr.strip()
            ]
            trigger["from"] = {"any_of": addresses, "labels": [], "not": []}
            warnings.append("AlertTemplate.trigger.from coerced from addresses list.")
            from_value = trigger["from"]
        if not isinstance(from_value, dict) or not {"any_of", "labels", "not"}.issubset(from_value):
            trigger["from"] = _coerce_trigger_filter(raw_from)
            if trigger["from"]["any_of"] and raw_from is not None:
                warnings.append("AlertTemplate.trigger.from coerced from legacy filter.")
        to_value = trigger.get("to")
        if isinstance(to_value, dict) and isinstance(to_value.get("addresses"), list):
            addresses = [
                addr.strip() for addr in to_value.get("addresses", []) if isinstance(addr, str) and addr.strip()
            ]
            trigger["to"] = {"any_of": addresses, "labels": [], "not": []}
            warnings.append("AlertTemplate.trigger.to coerced from addresses list.")
            to_value = trigger["to"]
        if not isinstance(to_value, dict) or not {"any_of", "labels", "not"}.issubset(to_value):
            trigger["to"] = _coerce_trigger_filter(raw_to)
            if trigger["to"]["any_of"] and raw_to is not None:
                warnings.append("AlertTemplate.trigger.to coerced from legacy filter.")
        method_value = trigger.get("method")
        if isinstance(method_value, dict) and "name" in method_value:
            name_value = method_value.get("name")
            if isinstance(name_value, str) and name_value.strip():
                trigger["method"] = {
                    "selector_any_of": [],
                    "name_any_of": [name_value.strip()],
                    "required": True,
                }
                method_value = trigger["method"]
                warnings.append("AlertTemplate.trigger.method defaulted from legacy name.")
        if (
            isinstance(method_value, list)
            or "method" not in trigger
            or not isinstance(method_value, dict)
            or not {"selector_any_of", "name_any_of", "required"}.issubset(method_value)
        ):
            trigger["method"] = {"selector_any_of": [], "name_any_of": [], "required": False}
            warnings.append("AlertTemplate.trigger.method defaulted.")

        legacy_expr = trigger.pop("expression", None)
        if legacy_expr is not None:
            coerced_expr = _coerce_legacy_expr(legacy_expr, variable_ids)
            if isinstance(coerced_expr, dict):
                trigger_expr = coerced_expr
                conditions = template.get("conditions")
                if not isinstance(conditions, dict):
                    conditions = {"all": [], "any": [], "not": []}
                conditions.setdefault("all", [])
                conditions.setdefault("any", [])
                conditions.setdefault("not", [])
                conditions["all"].append(coerced_expr)
                template["conditions"] = conditions
                warnings.append("AlertTemplate.conditions derived from legacy trigger.expression.")

    legacy_expr = template.pop("expression", None)
    if legacy_expr is not None:
        coerced_expr = _coerce_legacy_expr(legacy_expr, variable_ids)
        if isinstance(coerced_expr, dict):
            conditions = template.get("conditions")
            if not isinstance(conditions, dict):
                conditions = {"all": [], "any": [], "not": []}
            conditions.setdefault("all", [])
            conditions.setdefault("any", [])
            conditions.setdefault("not", [])
            conditions["all"].append(coerced_expr)
            template["conditions"] = conditions
            warnings.append("AlertTemplate.conditions derived from legacy template.expression.")

    conditions = template.get("conditions")
    if isinstance(conditions, dict):
        for key in ("all", "any", "not"):
            bucket = conditions.get(key)
            if isinstance(bucket, list):
                coerced_bucket = []
                for expr in bucket:
                    if isinstance(expr, dict) and "expression" in expr:
                        expr_value = expr.get("expression")
                        if isinstance(expr_value, dict):
                            op_value = expr_value.get("op") or expr_value.get("operator") or expr_value.get("type")
                            normalized_op = _normalize_expr_op(op_value)
                            if normalized_op == "eval_trigger_expression" and isinstance(trigger_expr, dict):
                                coerced_bucket.append(trigger_expr)
                                continue
                            coerced_expr = _coerce_legacy_expr(expr_value, variable_ids)
                            if coerced_expr is not None:
                                coerced_bucket.append(coerced_expr)
                        else:
                            if expr_value is not None:
                                coerced_bucket.append(expr_value)
                        continue
                    coerced_expr = _coerce_legacy_expr(expr, variable_ids) if isinstance(expr, dict) else expr
                    if coerced_expr is None:
                        continue
                    coerced_bucket.append(coerced_expr)
                conditions[key] = coerced_bucket

    action = template.get("action")
    if isinstance(action, dict) and "notification_template" not in template:
        title = action.get("title_template") or action.get("title")
        body = action.get("message_template") or action.get("body")
        if isinstance(title, str) or isinstance(body, str):
            template["notification_template"] = {
                "title": title if isinstance(title, str) and title.strip() else template.get("name", ""),
                "body": body if isinstance(body, str) and body.strip() else template.get("description", ""),
            }
            warnings.append("AlertTemplate.notification_template derived from legacy action fields.")


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    def _try_parse(candidate: str) -> Optional[Dict[str, Any]]:
        try:
            loaded = json.loads(candidate)
        except Exception:
            return None
        return loaded if isinstance(loaded, dict) else None

    def _iter_json_candidates(source: str) -> List[str]:
        candidates: List[str] = []

        if not source:
            return candidates

        # Try code-fenced blocks first (```json ... ``` or ``` ... ```).
        for match in re.finditer(r"```(?:json)?\\s*(.*?)\\s*```", source, flags=re.DOTALL | re.IGNORECASE):
            block = match.group(1)
            if block:
                candidates.append(block)

        # Scan for balanced JSON objects in the remaining text.
        brace_indices = [idx for idx, ch in enumerate(source) if ch == "{"]
        for start in brace_indices:
            depth = 0
            for end in range(start, len(source)):
                ch = source[end]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(source[start : end + 1])
                        break

        candidates.append(source)
        return candidates

    for candidate in _iter_json_candidates(text):
        loaded = _try_parse(candidate)
        if loaded is None:
            continue
        if "schema_version" in loaded or "template" in loaded or _looks_like_template(loaded):
            return loaded

    raise ProposedSpecCompilationError("LLM did not return a JSON object")


def _coerce_template(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        # Some models return the template as a JSON string, sometimes wrapped in code fences.
        try:
            loaded = _extract_first_json_object(value)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            try:
                loaded = json.loads(value)
            except Exception:
                # As a last resort, accept Python-literal dict strings (common with local models).
                try:
                    import ast

                    loaded = ast.literal_eval(value)
                except Exception:
                    return None
            if isinstance(loaded, dict):
                return loaded
    return None


def _looks_like_template(candidate: Dict[str, Any]) -> bool:
    required_keys = ("name", "description", "alert_type", "trigger", "conditions")
    return all(key in candidate for key in required_keys)


def _extract_template_from_result(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    candidate = _coerce_template(result.get("template"))
    if candidate:
        return candidate

    for key in ("alert_template", "alertTemplate"):
        candidate = _coerce_template(result.get(key))
        if candidate:
            return candidate

    for wrapper_key in ("proposed_spec", "proposedSpec", "result", "data", "payload"):
        wrapper = result.get(wrapper_key)
        if isinstance(wrapper, dict):
            candidate = _coerce_template(wrapper.get("template"))
            if candidate:
                return candidate
            candidate = _coerce_template(wrapper.get("alert_template")) or _coerce_template(
                wrapper.get("alertTemplate")
            )
            if candidate:
                return candidate

    if _looks_like_template(result):
        return result

    return None


def _looks_like_plan(candidate: Dict[str, Any]) -> bool:
    required_keys = ("target_kind", "trigger", "signals")
    return all(key in candidate for key in required_keys)


def _extract_template_v2_from_result(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    candidate = _coerce_template(result.get("template"))
    if candidate:
        return candidate
    # Back-compat for earlier plan-first outputs.
    candidate = _coerce_template(result.get("plan"))
    if candidate:
        return candidate

    for wrapper_key in ("proposed_spec", "proposedSpec", "result", "data", "payload"):
        wrapper = result.get(wrapper_key)
        if isinstance(wrapper, dict):
            candidate = _coerce_template(wrapper.get("template"))
            if candidate:
                return candidate
            candidate = _coerce_template(wrapper.get("plan"))
            if candidate:
                return candidate

    if _looks_like_plan(result):
        return result

    return None


def _build_system_prompt(pipeline: PipelineConfig) -> str:
    base = (
        "You are a deterministic compiler.\n"
        "Output ONLY a single JSON object.\n"
        "Do not output markdown. Do not output code fences.\n"
        "Your output must conform to ProposedSpec v1 (schema_version='proposed_spec_v1')\n"
        "and include an embedded AlertTemplate v1 (template.version='v1').\n"
        "AlertTemplate expressions MUST use the wasmCloud ExprV1 shape:\n"
        "- each expr is an object with 'op' and operands in 'left'/'right' (or 'values' for coalesce)\n"
        "- do NOT use 'args' or 'expr' keys\n"
        "- 'and'/'or' require both 'left' and 'right'\n"
        "- 'not' uses 'left' (or non-empty 'values')\n"
        "- 'coalesce' prefers non-empty 'values'\n"
        "AlertTemplate.trigger MUST include tx_type, from, to, and method objects.\n"
        "AlertTemplate.datasources MUST include cache_ttl_secs and timeout_ms.\n"
        "AlertTemplate.variables MUST include label and required.\n"
        "AlertTemplate.action MUST include notification_policy, cooldown_secs, cooldown_key_template, dedupe_key_template.\n"
        "AlertTemplate.notification_template.title/body MUST be concise and relevant.\n"
        "Both title and body MUST include at least one placeholder (e.g. {{target.short}}, {{tx.value_native}}).\n"
        "Do NOT copy the nl_description into the notification templates.\n"
        "Never include raw SQL or raw executable code.\n"
        "Templates may only use catalog datasources by catalog_id.\n"
    )
    if pipeline.system_prompt_suffix:
        return f"{base}{pipeline.system_prompt_suffix}\n"
    return base


def _build_system_prompt_v2(pipeline: PipelineConfig) -> str:
    base = (
        "You are a deterministic compiler for Ekko.\n"
        "Output ONLY a single JSON object.\n"
        "Do not output markdown. Do not output code fences.\n"
        "Your output MUST be a single JSON object with exactly these top-level keys:\n"
        "- template: an AlertTemplate v2 draft object (schema_version='alert_template_v2')\n"
        "- warnings: an array of warning strings (may be empty)\n"
        "\n"
        "Hard rules:\n"
        "- nl_description is end-user intent text. Do NOT expect internal IDs (datasource_catalog IDs), tables, or SQL.\n"
        "- Do NOT include targets (no wallet addresses, no group IDs, no target_keys).\n"
        "- Select datasources ONLY from the provided datasource_catalog snapshot.\n"
        "- Prefer event/log-driven sources; polling is a fallback.\n"
        "- If the alert can be evaluated using only the triggering transaction/schedule context, do NOT add datasources.\n"
        "  Use explicit JSONPath refs like $.tx.value_native / $.tx.method_selector in trigger.condition_ast.\n"
        "- Expressions MUST use ExprV1 AST objects with 'op' and operands in 'left'/'right' (or 'values').\n"
        "- Template.trigger.condition_ast must be an expression object.\n"
        "- In ExprV1, JSONPath refs are plain strings (e.g. \"$.tx.value_native\"), not objects.\n"
        "\n"
        "Minimal schema sketch (AlertTemplate v2 draft):\n"
        "- template.schema_version (string)\n"
        "- template.target_kind (\"wallet\" | \"contract\" | \"token\" | \"network\" | \"protocol\")\n"
        "- template.scope.networks (e.g. [\"ETH:mainnet\"]) and template.scope.instrument_constraints (list)\n"
        "- template.signals.principals (list) and template.signals.factors (list)\n"
        "  - each signal: {name, unit, update_sources:[{ref:<catalog_id>, source_type, how_to_ingest, polling:{enabled,cadence_seconds}}]}\n"
        "- template.variables (list, optional)\n"
        "- template.trigger: {evaluation_mode, condition_ast, cron_cadence_seconds, dedupe:{cooldown_seconds,key_template}}\n"
        "- template.notification: {title_template, body_template}\n"
        "- notification.title_template MUST be short and MUST include a placeholder (e.g. {{target.short}}).\n"
        "- notification.body_template MUST include at least one placeholder (e.g. {{target.short}}, {{tx.value_native}}, {{balance_latest}}).\n"
        "- Do NOT copy the nl_description into the notification templates.\n"
        "\n"
        "Example (tx-only, no datasources):\n"
        "{\n"
        "  \"template\": {\n"
        "    \"schema_version\": \"alert_template_v2\",\n"
        "    \"target_kind\": \"wallet\",\n"
        "    \"name\": \"Large send\",\n"
        "    \"description\": \"Alert when a monitored wallet sends more than 1 ETH in one transaction.\",\n"
        "    \"scope\": {\"networks\": [\"ETH:mainnet\"], \"instrument_constraints\": []},\n"
        "    \"signals\": {\"principals\": [], \"factors\": []},\n"
        "    \"variables\": [],\n"
        "    \"trigger\": {\n"
        "      \"evaluation_mode\": \"event_driven\",\n"
        "      \"condition_ast\": {\"op\": \"gte\", \"left\": \"$.tx.value_native\", \"right\": 1.0},\n"
        "      \"cron_cadence_seconds\": 0,\n"
        "      \"dedupe\": {\"cooldown_seconds\": 0, \"key_template\": \"{{instance_id}}:{{target.key}}\"}\n"
        "    },\n"
        "    \"notification\": {\"title_template\": \"Large send: {{target.short}}\", \"body_template\": \"Transaction value {{tx.value_native}} ETH (>= 1.0).\"},\n"
        "    \"derivations\": [],\n"
        "    \"fallbacks\": [],\n"
        "    \"assumptions\": []\n"
        "  },\n"
        "  \"warnings\": []\n"
        "}\n"
        "\n"
        "Example (DuckLake datasource, refer to datasource columns by name):\n"
        "{\n"
        "  \"template\": {\n"
        "    \"schema_version\": \"alert_template_v2\",\n"
        "    \"target_kind\": \"wallet\",\n"
        "    \"name\": \"Low balance\",\n"
        "    \"description\": \"Alert when a monitored wallet balance drops below 0.5.\",\n"
        "    \"scope\": {\"networks\": [\"ETH:mainnet\"], \"instrument_constraints\": []},\n"
        "    \"signals\": {\n"
        "      \"principals\": [\n"
        "        {\"name\": \"balance_latest\", \"unit\": \"decimal\", \"update_sources\": [{\"ref\": \"ducklake.wallet_balance_latest\", \"source_type\": \"observation\", \"how_to_ingest\": \"rpc_call\", \"polling\": {\"enabled\": true, \"cadence_seconds\": 300}}]}\n"
        "      ],\n"
        "      \"factors\": []\n"
        "    },\n"
        "    \"variables\": [],\n"
        "    \"trigger\": {\n"
        "      \"evaluation_mode\": \"periodic\",\n"
        "      \"condition_ast\": {\"op\": \"lt\", \"left\": \"balance_latest\", \"right\": 0.5},\n"
        "      \"cron_cadence_seconds\": 300,\n"
        "      \"dedupe\": {\"cooldown_seconds\": 300, \"key_template\": \"{{instance_id}}:{{target.key}}\"}\n"
        "    },\n"
        "    \"notification\": {\"title_template\": \"Balance alert: {{target.short}}\", \"body_template\": \"Balance {{balance_latest}} (below 0.5).\"},\n"
        "    \"derivations\": [],\n"
        "    \"fallbacks\": [],\n"
        "    \"assumptions\": []\n"
        "  },\n"
        "  \"warnings\": []\n"
        "}\n"
        "\n"
        "For vNext compilation, treat signals[].update_sources[].ref as a datasource catalog_id.\n"
    )
    if pipeline.system_prompt_suffix:
        return f"{base}{pipeline.system_prompt_suffix}\n"
    return base


def _build_plan_logic_system_prompt(pipeline: PipelineConfig) -> str:
    """
    Stage 1 (DSPy): extract a small, schema-safe logic intent from NL.

    This is intentionally narrower than `_build_system_prompt_v2`:
    - The model does NOT choose datasources directly.
    - The model produces normalized condition atoms over either `$.tx.*` or known
      allowlisted datasource columns. We deterministically select datasources and
      assemble the full AlertTemplate v2 draft.
    """

    base = (
        "You are a deterministic planner for Ekko alert creation.\n"
        "Output ONLY a single JSON object. No markdown. No code fences.\n"
        "\n"
        "You must extract the user's end-user intent into a small logic spec.\n"
        "\n"
        "Hard rules:\n"
        "- Do NOT include targets (no wallet addresses, no group IDs, no target_keys).\n"
        "- Do NOT include datasource_catalog IDs in the output.\n"
        "- Do NOT guess network if context.preferred_network is missing.\n"
        "- If the user is asking about a SINGLE transaction (\"in a single transaction\", \"whenever it sends\", \"whenever it receives\"),\n"
        "  you MUST use tx JSONPath refs (e.g. $.tx.value_native / $.tx.method_selector) and MUST NOT use aggregate metrics like tx_count_24h.\n"
        "- Only reference tx fields via explicit JSONPath strings starting with `$.tx.`.\n"
        "- Only reference non-tx metrics using allowlisted datasource column names from datasource_catalog.result_schema.\n"
        "\n"
        "Return JSON with exactly these top-level keys:\n"
        "- target_kind: one of wallet|contract|token|network|protocol\n"
        "- combine_op: one of and|or (how to combine multiple conditions)\n"
        "- conditions: array of condition objects, each: {left, op, right}\n"
        "- window_duration: duration string like 24h/1h/7d/30d (empty string if not needed)\n"
        "- notes: array of short strings (may be empty)\n"
        "\n"
        "Condition object rules:\n"
        "- left: either a JSONPath `$.tx.<field>` OR a datasource column name (e.g. balance_latest)\n"
        "- op: one of gt|gte|lt|lte|eq|neq\n"
        "- right: number or string\n"
        "\n"
        "Percent-change rule:\n"
        "- pct_change_window is a FRACTIONAL decimal (10% => 0.10). Drops use negative (drop 10% => -0.10).\n"
        "\n"
        "Examples:\n"
        "1) tx-only:\n"
        "{\n"
        "  \"target_kind\": \"wallet\",\n"
        "  \"combine_op\": \"and\",\n"
        "  \"conditions\": [{\"left\": \"$.tx.value_native\", \"op\": \"gte\", \"right\": 1.0}],\n"
        "  \"window_duration\": \"\",\n"
        "  \"notes\": []\n"
        "}\n"
        "2) scheduled (datasource column):\n"
        "{\n"
        "  \"target_kind\": \"wallet\",\n"
        "  \"combine_op\": \"and\",\n"
        "  \"conditions\": [{\"left\": \"balance_latest\", \"op\": \"lt\", \"right\": 0.5}],\n"
        "  \"window_duration\": \"\",\n"
        "  \"notes\": []\n"
        "}\n"
        "3) windowed:\n"
        "{\n"
        "  \"target_kind\": \"wallet\",\n"
        "  \"combine_op\": \"and\",\n"
        "  \"conditions\": [{\"left\": \"pct_change_window\", \"op\": \"lt\", \"right\": -0.10}],\n"
        "  \"window_duration\": \"24h\",\n"
        "  \"notes\": []\n"
        "}\n"
    )

    if pipeline.system_prompt_suffix:
        return f"{base}{pipeline.system_prompt_suffix}\n"
    return base


def _build_plan_logic_repair_system_prompt(pipeline: PipelineConfig) -> str:
    base = _build_plan_logic_system_prompt(pipeline)
    return (
        f"{base}\n"
        "Repair instruction:\n"
        "- The previous attempt was invalid because it produced no usable conditions.\n"
        "- You MUST return at least one condition.\n"
        "- If the user intent is about *any incoming/outgoing transfer* and no threshold is given, use:\n"
        "  {\"left\":\"$.tx.value_native\",\"op\":\"gt\",\"right\":0.0}.\n"
    )


def _build_user_prompt(
    nl_description: str,
    context: Dict[str, Any],
    pipeline: PipelineConfig,
) -> str:
    catalog = list_compiler_catalog_entries()
    supported_networks = _supported_networks_from_context(context)
    payload = {
        "nl_description": nl_description,
        "context": context,
        "datasource_catalog": catalog,
        "pipeline": {"id": pipeline.pipeline_id, "version": pipeline.version},
        "constraints": {
            "supported_networks": supported_networks,
            "default_condition_match": "any_match",
            "max_expression_depth": 8,
            "max_datasources": 10,
        },
        "required_output_keys": [
            "schema_version",
            "job_id",
            "expires_at",
            "pipeline_id",
            "pipeline_version",
            "template",
            "required_user_inputs",
            "human_preview",
            "fingerprint_candidate",
            "warnings",
        ],
    }
    if pipeline.user_prompt_context:
        payload["pipeline_context"] = pipeline.user_prompt_context
    if pipeline.examples:
        payload["examples"] = pipeline.examples
    return json.dumps(payload, sort_keys=True)


def _build_user_prompt_v2(
    nl_description: str,
    context: Dict[str, Any],
    pipeline: PipelineConfig,
) -> str:
    catalog = list_compiler_catalog_entries()
    supported_networks = _supported_networks_from_context(context)
    payload: Dict[str, Any] = {
        "nl_description": nl_description,
        "context": context,
        "datasource_catalog": catalog,
        "pipeline": {"id": pipeline.pipeline_id, "version": pipeline.version},
        "constraints": {
            "supported_networks": supported_networks,
            "max_expression_depth": 8,
            "max_signals": 12,
        },
        "required_output_schema": "alert_template_v2_draft",
        "required_template_keys": [
            "schema_version",
            "target_kind",
            "scope",
            "signals",
            "trigger",
            "notification",
        ],
    }
    if pipeline.user_prompt_context:
        payload["pipeline_context"] = pipeline.user_prompt_context
    if pipeline.examples:
        payload["examples"] = pipeline.examples
    return json.dumps(payload, sort_keys=True)


def _build_plan_logic_prompt_json(
    nl_description: str,
    context: Dict[str, Any],
    pipeline: PipelineConfig,
) -> str:
    catalog = list_compiler_catalog_entries()
    supported_networks = _supported_networks_from_context(context)
    payload: Dict[str, Any] = {
        "nl_description": nl_description,
        "context": context,
        "supported_networks": supported_networks,
        "datasource_catalog": catalog,
        "allowed_tx_refs": [
            "$.tx.value_native",
            "$.tx.method_selector",
            "$.tx.gas_fee_native",
        ],
        "allowed_ops": ["gt", "gte", "lt", "lte", "eq", "neq"],
        "guidance": {
            "network_selection": "If context.preferred_network is missing, do not guess network; extraction should be network-agnostic.",
            "datasources": "Do not output catalog IDs; only use datasource column names from result_schema.columns[].name.",
            "tx_vs_aggregate": "Use tx_count_24h only when the user explicitly asks about 'transactions in the last 24 hours' (aggregate). For single-transaction alerts use $.tx.* only.",
        },
        "pipeline": {"id": pipeline.pipeline_id, "version": pipeline.version},
    }
    if pipeline.user_prompt_context:
        payload["pipeline_context"] = pipeline.user_prompt_context
    return json.dumps(payload, sort_keys=True)


def _build_proposed_spec_envelope(
    *,
    template: Dict[str, Any],
    required_user_inputs: Dict[str, Any],
    human_preview: Dict[str, Any],
    warnings: list[str],
    ctx: ProposedSpecBuildContext,
) -> Dict[str, Any]:
    fingerprint_candidate = compute_template_fingerprint(template)
    proposed_spec: Dict[str, Any] = {
        "schema_version": "proposed_spec_v1",
        "job_id": ctx.job_id,
        "expires_at": ctx.expires_at,
        "pipeline_id": ctx.pipeline_id,
        "pipeline_version": ctx.pipeline_version,
        "template": template,
        "required_user_inputs": required_user_inputs,
        "human_preview": human_preview,
        "fingerprint_candidate": fingerprint_candidate,
        "warnings": warnings,
    }
    if ctx.client_request_id:
        proposed_spec["client_request_id"] = ctx.client_request_id
    return proposed_spec


def _build_proposed_spec_v2_envelope(
    *,
    template: Dict[str, Any],
    compiled_executable: Dict[str, Any],
    compile_report: Dict[str, Any],
    required_user_inputs: Dict[str, Any],
    human_preview: Dict[str, Any],
    warnings: list[str],
    confidence: float,
    missing_info: list[dict[str, Any]],
    assumptions: list[str],
    pipeline_metadata: Dict[str, Any],
    ctx: ProposedSpecBuildContext,
) -> Dict[str, Any]:
    proposed_spec: Dict[str, Any] = {
        "schema_version": "proposed_spec_v2",
        "job_id": ctx.job_id,
        "expires_at": ctx.expires_at,
        "pipeline_id": ctx.pipeline_id,
        "pipeline_version": ctx.pipeline_version,
        "template": template,
        "compiled_executable": compiled_executable,
        "compile_report": compile_report,
        "required_user_inputs": required_user_inputs,
        "human_preview": human_preview,
        "confidence": float(confidence),
        "missing_info": missing_info,
        "assumptions": assumptions,
        "warnings": warnings,
        "pipeline_metadata": pipeline_metadata,
    }
    if ctx.client_request_id:
        proposed_spec["client_request_id"] = ctx.client_request_id
    return proposed_spec


def _build_dspy_demos(dspy_module: Any, examples: list[dict[str, Any]]) -> list[Any]:
    demo_cls = getattr(dspy_module, "Example", None)
    if demo_cls is None:
        return []

    demos: list[Any] = []
    for example in examples:
        nl_description = example.get("nl_description")
        if not isinstance(nl_description, str) or not nl_description.strip():
            continue

        context = example.get("context") if isinstance(example.get("context"), dict) else {}
        output_json = example.get("output_json")
        if output_json is None:
            continue
        template_value = output_json
        if isinstance(output_json, str) and output_json.strip():
            try:
                template_value = _extract_first_json_object(output_json)
            except Exception:
                template_value = output_json

        try:
            demo = demo_cls(
                nl_description=nl_description.strip(),
                context_json=json.dumps(context, sort_keys=True),
                template=template_value,
                warnings=[],
            ).with_inputs("nl_description", "context_json")
            demos.append(demo)
        except Exception:
            continue

    return demos


_SUPPORTED_TARGET_KINDS: set[str] = {"wallet", "contract", "token", "network", "protocol"}


_DURATION_RE = re.compile(
    r"(?:(?:last|past|over the last|over|in the last)\\s+)?(?P<num>\\d+)\\s*(?P<unit>hours?|hrs?|h|days?|d)",
    re.IGNORECASE,
)


def _extract_window_duration_from_text(nl_description: str) -> Optional[str]:
    """
    Best-effort duration extraction used only as a fallback when the LLM omits it.
    """

    text = str(nl_description or "")
    match = _DURATION_RE.search(text)
    if not match:
        # Common singular phrasing ("last hour").
        if re.search(r"\\blast\\s+hour\\b", text, flags=re.IGNORECASE):
            return "1h"
        return None

    num = match.group("num")
    unit = (match.group("unit") or "").lower()
    try:
        n = int(num)
    except Exception:
        return None
    if n <= 0:
        return None
    if unit.startswith("h"):
        return f"{n}h"
    if unit.startswith("d"):
        return f"{n}d"
    return None


def _flatten_simple_bool_expr(expr: Any) -> Optional[tuple[str, list[dict[str, Any]]]]:
    """
    Convert a simple ExprV1 boolean tree (and/or of comparisons) into a flat list.

    Returns (combine_op, conditions) when representable; otherwise None.
    """

    if not isinstance(expr, dict) or not expr:
        return None

    op = str(expr.get("op") or "").strip().lower()
    if op in {"and", "or"}:
        left = _flatten_simple_bool_expr(expr.get("left"))
        right = _flatten_simple_bool_expr(expr.get("right"))
        if left is None or right is None:
            return None
        left_op, left_conds = left
        right_op, right_conds = right
        # Only flatten when the subtree uses the same boolean op.
        if left_op != op or right_op != op:
            return None
        return op, [*left_conds, *right_conds]

    # Leaf comparison.
    if op not in {"gt", "gte", "lt", "lte", "eq", "neq"}:
        return None
    left_val = expr.get("left")
    right_val = expr.get("right")
    if not isinstance(left_val, str) or not left_val.strip():
        return None
    if isinstance(right_val, (dict, list)):
        return None
    return "and", [{"left": left_val.strip(), "op": op, "right": right_val}]


def _build_dspy_plan_logic_demos(
    dspy_module: Any,
    examples: list[dict[str, Any]],
    pipeline: PipelineConfig,
) -> list[Any]:
    """
    Build demos for the plan-logic extraction stage from stored template examples.
    """

    demo_cls = getattr(dspy_module, "Example", None)
    if demo_cls is None:
        return []

    demos: list[Any] = []
    for example in examples:
        nl_description = example.get("nl_description")
        if not isinstance(nl_description, str) or not nl_description.strip():
            continue
        context = example.get("context") if isinstance(example.get("context"), dict) else {}
        output_json = example.get("output_json")
        if output_json is None:
            continue
        template_value = output_json
        if isinstance(output_json, str) and output_json.strip():
            try:
                template_value = _extract_first_json_object(output_json)
            except Exception:
                template_value = output_json

        if not isinstance(template_value, dict):
            continue
        trigger = template_value.get("trigger") if isinstance(template_value.get("trigger"), dict) else {}
        condition_ast = trigger.get("condition_ast")
        flattened = _flatten_simple_bool_expr(condition_ast)
        if flattened is None:
            continue
        combine_op, conditions = flattened

        window_duration = ""
        # Prefer explicit variable default when present.
        variables = template_value.get("variables") if isinstance(template_value.get("variables"), list) else []
        for var in variables:
            if not isinstance(var, dict):
                continue
            if str(var.get("id") or "").strip() == "window_duration":
                default = var.get("default")
                if isinstance(default, str) and default.strip():
                    window_duration = default.strip()
                break
        if not window_duration:
            window_duration = _extract_window_duration_from_text(nl_description) or ""

        target_kind = str(template_value.get("target_kind") or "wallet").strip().lower() or "wallet"
        if target_kind not in _SUPPORTED_TARGET_KINDS:
            target_kind = "wallet"

        try:
            demo = demo_cls(
                nl_description=nl_description.strip(),
                prompt_json=_build_plan_logic_prompt_json(nl_description.strip(), context, pipeline),
                target_kind=target_kind,
                combine_op=combine_op,
                conditions=conditions,
                window_duration=window_duration,
                notes=[],
            ).with_inputs("nl_description", "prompt_json")
            demos.append(demo)
        except Exception:
            continue

    return demos

def _supported_networks_from_context(context: Dict[str, Any]) -> list[str]:
    """
    Supported networks are a platform capability/config surface.

    Prefer explicit context (dashboard/org scoped). Fall back to server settings.
    """
    raw = context.get("supported_networks") or context.get("supportedNetworks")
    if isinstance(raw, list):
        return [str(v).strip() for v in raw if isinstance(v, str) and str(v).strip()]

    configured = getattr(settings, "NLP_SUPPORTED_NETWORKS", None)
    if isinstance(configured, (list, tuple)):
        return [str(v).strip() for v in configured if str(v).strip()]

    return []


def _default_plan_name(nl_description: str) -> str:
    # Reuse the same heuristics as template names.
    return _default_template_name(nl_description).replace("Template", "Plan")


def _default_plan_description(nl_description: str) -> str:
    return _default_template_description(nl_description).replace("Alert generated from:", "Plan generated from:")


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if isinstance(v, str) and str(v).strip()]


def _sanitize_plan_scope(
    plan: Dict[str, Any],
    *,
    context: Dict[str, Any],
    warnings: list[str],
) -> None:
    scope = plan.get("scope")
    if not isinstance(scope, dict):
        scope = {}
        plan["scope"] = scope

    networks = _coerce_string_list(scope.get("networks"))
    preferred = context.get("preferred_network") or context.get("preferredNetwork")
    if not networks and isinstance(preferred, str) and preferred.strip():
        networks = [preferred.strip()]
        warnings.append("Plan.scope.networks missing; defaulted from context.preferred_network.")

    # Filter to supported networks (if configured) and preserve stable ordering.
    supported = _supported_networks_from_context(context)
    if supported:
        filtered = [n for n in networks if n in supported]
        if not filtered and isinstance(preferred, str) and preferred.strip() and preferred.strip() in supported:
            # If the model produced an invalid network string (e.g. "ETH"), fall back to the
            # UI-provided preferred network rather than treating it as missing.
            filtered = [preferred.strip()]
            warnings.append("Plan.scope.networks contained unsupported values; defaulted to context.preferred_network.")
        networks = filtered
    scope["networks"] = networks

    # Normalize legacy entity list into instrument_constraints when present.
    instrument_constraints = scope.get("instrument_constraints")
    if not isinstance(instrument_constraints, list):
        instrument_constraints = []

    entities = scope.get("entities")
    if isinstance(entities, list):
        mapped: list[dict[str, Any]] = []
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            entity_type = str(ent.get("entity_type") or ent.get("entityType") or "").strip().lower()
            ref = str(ent.get("ref") or "").strip()
            if not ref:
                continue
            mapped.append(
                {
                    "kind": entity_type or "custom",
                    "ref": ref,
                    "notes": str(ent.get("notes") or "").strip() or None,
                }
            )
        if mapped:
            instrument_constraints.extend(mapped)
            warnings.append("Plan.scope.entities was normalized into scope.instrument_constraints.")

    # Compact null notes.
    compacted: list[dict[str, Any]] = []
    for item in instrument_constraints:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "custom").strip().lower() or "custom"
        ref = str(item.get("ref") or "").strip()
        if not ref:
            continue
        normalized: dict[str, Any] = {"kind": kind, "ref": ref}
        notes = item.get("notes")
        if isinstance(notes, str) and notes.strip():
            normalized["notes"] = notes.strip()
        compacted.append(normalized)
    scope["instrument_constraints"] = compacted


def _sanitize_plan_signals(
    plan: Dict[str, Any],
    *,
    warnings: list[str],
) -> None:
    signals = plan.get("signals")
    if not isinstance(signals, dict):
        signals = {}
        plan["signals"] = signals

    allowed_catalog_ids = {c.get("catalog_id") for c in list_compiler_catalog_entries() if isinstance(c, dict)}

    def sanitize_bucket(bucket: str) -> list[dict[str, Any]]:
        items = signals.get(bucket)
        if not isinstance(items, list):
            return []

        cleaned: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            unit = str(item.get("unit") or "").strip() or "custom"
            sources = item.get("update_sources")
            if not isinstance(sources, list):
                sources = []

            cleaned_sources: list[dict[str, Any]] = []
            for src in sources:
                if not isinstance(src, dict):
                    continue
                # LLMs frequently vary the key name; accept a small set and normalize.
                ref = str(
                    src.get("ref")
                    or src.get("catalog_id")
                    or src.get("catalogId")
                    or src.get("source_ref")
                    or src.get("sourceRef")
                    or ""
                ).strip()
                if not ref:
                    continue
                if ref not in allowed_catalog_ids:
                    warnings.append(f"Plan signal source ref {ref!r} is not in DatasourceCatalog; dropped.")
                    continue
                source_type = str(src.get("source_type") or "").strip().lower() or "observation"
                how = str(src.get("how_to_ingest") or "").strip().lower() or "rpc_call"
                cleaned_sources.append(
                    {
                        "source_type": source_type,
                        "ref": ref,
                        "how_to_ingest": how,
                        "polling": src.get("polling") if isinstance(src.get("polling"), dict) else {"enabled": False, "cadence_seconds": 0},
                    }
                )

            if not cleaned_sources:
                continue
            cleaned.append({"name": name.strip(), "unit": unit, "update_sources": cleaned_sources})

        return cleaned

    signals["principals"] = sanitize_bucket("principals")
    signals["factors"] = sanitize_bucket("factors")


def _sanitize_plan_variables(plan: Dict[str, Any]) -> None:
    variables = plan.get("variables")
    if not isinstance(variables, list):
        plan["variables"] = []
        return

    cleaned: list[dict[str, Any]] = []
    for var in variables:
        if not isinstance(var, dict):
            continue
        var_id = var.get("id") or var.get("name")
        if not isinstance(var_id, str) or not var_id.strip():
            continue
        vtype = str(var.get("type") or "string").strip().lower()
        label = str(var.get("label") or var_id).strip()
        required = bool(var.get("required", True))
        normalized: dict[str, Any] = {
            "id": var_id.strip(),
            "type": vtype,
            "label": label,
            "required": required,
        }
        if var.get("description"):
            normalized["description"] = str(var.get("description")).strip()
        if "default" in var and var.get("default") is not None:
            normalized["default"] = var.get("default")
        if isinstance(var.get("validation"), dict):
            normalized["validation"] = dict(var.get("validation"))
        if isinstance(var.get("ui"), dict):
            normalized["ui"] = dict(var.get("ui"))
        cleaned.append(normalized)

    plan["variables"] = cleaned


def _sanitize_plan_trigger(plan: Dict[str, Any], *, warnings: list[str]) -> None:
    trigger = plan.get("trigger")
    if not isinstance(trigger, dict):
        trigger = {}
        plan["trigger"] = trigger

    variable_ids: set[str] = set()
    variables = plan.get("variables")
    if isinstance(variables, list):
        for var in variables:
            if not isinstance(var, dict):
                continue
            var_id = var.get("id") or var.get("name")
            if isinstance(var_id, str) and var_id.strip():
                variable_ids.add(var_id.strip())

    raw_mode = str(trigger.get("evaluation_mode") or trigger.get("evaluationMode") or "").strip().lower()
    mode_aliases = {
        "event": "event_driven",
        "realtime": "event_driven",
        "real-time": "event_driven",
        "event-driven": "event_driven",
        "on_tx": "event_driven",
        "on_transaction": "event_driven",
        "cron": "periodic",
        "scheduled": "periodic",
        "schedule": "periodic",
    }
    mode = mode_aliases.get(raw_mode, raw_mode)
    if mode not in {"event_driven", "periodic", "hybrid"}:
        # Default to hybrid so the dashboard can choose event-driven vs scheduled.
        trigger["evaluation_mode"] = "hybrid"
        warnings.append("Plan.trigger.evaluation_mode missing/invalid; defaulted to 'hybrid'.")
    else:
        trigger["evaluation_mode"] = mode

    # Normalize condition AST.
    condition = trigger.get("condition_ast") or trigger.get("condition")
    if isinstance(condition, dict):
        trigger["condition_ast"] = _coerce_legacy_expr(condition, variable_ids)
    else:
        trigger["condition_ast"] = trigger.get("condition_ast") if isinstance(trigger.get("condition_ast"), dict) else {}

    if not isinstance(trigger.get("condition_ast"), dict) or not trigger.get("condition_ast"):
        warnings.append("Plan.trigger.condition_ast missing or invalid; compilation may fail until repaired.")

    if "cron_cadence_seconds" not in trigger:
        trigger["cron_cadence_seconds"] = int(trigger.get("cron", 0) or 0)
    if not isinstance(trigger.get("dedupe"), dict):
        trigger["dedupe"] = {"cooldown_seconds": 0, "key_template": "{{instance_id}}:{{target.key}}"}


def _sanitize_plan_notification(plan: Dict[str, Any]) -> None:
    notification = plan.get("notification")
    if not isinstance(notification, dict):
        notification = {}
        plan["notification"] = notification
    title = str(notification.get("title_template") or "").strip()
    body = str(notification.get("body_template") or "").strip()

    variable_ids = {
        str(v.get("id")).strip()
        for v in (plan.get("variables") or [])
        if isinstance(v, dict) and str(v.get("id") or "").strip()
    }

    trigger = plan.get("trigger") if isinstance(plan.get("trigger"), dict) else {}
    condition_ast = trigger.get("condition_ast") if isinstance(trigger.get("condition_ast"), dict) else {}
    extracted_conditions = _extract_conditions_from_ast(condition_ast)
    defaults = _build_default_notification_templates(
        conditions=extracted_conditions,
        variable_ids=variable_ids,
    )

    if not title:
        notification["title_template"] = defaults[0]
    if not body:
        notification["body_template"] = defaults[1] or notification.get("title_template") or ""
    if isinstance(notification.get("body_template"), str) and not notification["body_template"].strip():
        notification["body_template"] = defaults[1] or notification.get("title_template") or ""


def _sanitize_plan_targeting(plan: Dict[str, Any], *, warnings: list[str]) -> None:
    # vNext hard rule: targets are supplied only by the instance form, never by NLP.
    for key in ("targets", "target_keys", "target_selector", "group_id", "groupId"):
        if key in plan:
            plan.pop(key, None)
            warnings.append(f"Plan contained forbidden key {key!r}; removed.")


def _collect_plan_catalog_ids(plan: Dict[str, Any]) -> list[str]:
    catalog_ids: list[str] = []
    signals = plan.get("signals") if isinstance(plan.get("signals"), dict) else {}
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


def _expr_to_text(expr: Any) -> str:
    if isinstance(expr, dict):
        op = str(expr.get("op") or "").strip().lower()
        op_map = {
            "gt": ">",
            "gte": ">=",
            "lt": "<",
            "lte": "<=",
            "eq": "==",
            "neq": "!=",
            "and": "AND",
            "or": "OR",
            "add": "+",
            "sub": "-",
            "mul": "*",
            "div": "/",
        }
        if op == "not":
            return f"NOT ({_expr_to_text(expr.get('left'))})"
        if op in {"and", "or"}:
            return f"({_expr_to_text(expr.get('left'))} {op_map[op]} {_expr_to_text(expr.get('right'))})"
        if op in {"gt", "gte", "lt", "lte", "eq", "neq", "add", "sub", "mul", "div"}:
            return f"{_expr_to_text(expr.get('left'))} {op_map[op]} {_expr_to_text(expr.get('right'))}"
        return op
    if isinstance(expr, str):
        return expr.strip()
    if expr is None:
        return ""
    return str(expr)


def _build_plan_human_preview(plan: Dict[str, Any]) -> Dict[str, Any]:
    scope = plan.get("scope") if isinstance(plan.get("scope"), dict) else {}
    networks = _coerce_string_list(scope.get("networks"))
    trigger = plan.get("trigger") if isinstance(plan.get("trigger"), dict) else {}
    condition_ast = trigger.get("condition_ast") if isinstance(trigger.get("condition_ast"), dict) else {}
    condition_text = _expr_to_text(condition_ast) if condition_ast else ""
    target_kind = str(plan.get("target_kind") or "").strip() or "target"
    network_text = ", ".join(networks) if networks else "any supported network"
    summary = f"Alert on {target_kind} when {condition_text} ({network_text})".strip()
    return {"summary": summary, "segments": []}


def _build_plan_required_user_inputs(plan: Dict[str, Any]) -> Dict[str, Any]:
    variables = plan.get("variables") if isinstance(plan.get("variables"), list) else []
    required_vars: list[str] = []
    defaults: dict[str, Any] = {}
    for var in variables:
        if not isinstance(var, dict):
            continue
        var_id = var.get("id")
        if not isinstance(var_id, str) or not var_id.strip():
            continue
        if bool(var.get("required", True)):
            required_vars.append(var_id)
        if "default" in var and var.get("default") is not None:
            defaults[var_id] = var.get("default")

    trigger = plan.get("trigger") if isinstance(plan.get("trigger"), dict) else {}
    mode = str(trigger.get("evaluation_mode") or "periodic").strip().lower()
    if mode == "event_driven":
        supported_triggers = ["event_driven"]
    elif mode == "hybrid":
        supported_triggers = ["periodic", "event_driven"]
    else:
        supported_triggers = ["periodic"]

    target_kind = str(plan.get("target_kind") or "wallet").strip().lower()
    return {
        "targets_required": True,
        "target_kind": target_kind,
        "required_variables": sorted(set(required_vars)),
        "suggested_defaults": defaults,
        "supported_trigger_types": supported_triggers,
    }


def _build_plan_missing_info(
    plan: Dict[str, Any],
    *,
    compile_errors: list[str],
    context: Dict[str, Any],
) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    scope = plan.get("scope") if isinstance(plan.get("scope"), dict) else {}
    networks = _coerce_string_list(scope.get("networks"))
    if not networks:
        supported = _supported_networks_from_context(context)
        missing.append(
            {
                "code": "network_required",
                "message": "Select a network for this alert.",
                "field": "scope.networks",
                # Options include a context_patch so the dashboard can deterministically
                # re-run the pipeline without ad-hoc client-side mappings.
                "options": [
                    {"id": n, "label": n, "context_patch": {"preferred_network": n}}
                    for n in supported
                ],
            }
        )

    catalog_ids = _collect_plan_catalog_ids(plan)
    signals = plan.get("signals") if isinstance(plan.get("signals"), dict) else {}
    principals = signals.get("principals") if isinstance(signals.get("principals"), list) else []
    factors = signals.get("factors") if isinstance(signals.get("factors"), list) else []
    has_signal_defs = bool(principals or factors)

    # Tx-only / schedule-only alerts can compile without datasources.
    if not catalog_ids and has_signal_defs:
        missing.append(
            {
                "code": "datasource_required",
                "message": "The plan must reference at least one allowlisted datasource.",
                "field": "signals",
                "options": [],
            }
        )

    trigger = plan.get("trigger") if isinstance(plan.get("trigger"), dict) else {}
    condition_ast = trigger.get("condition_ast") if isinstance(trigger.get("condition_ast"), dict) else {}
    if not condition_ast:
        missing.append(
            {
                "code": "condition_required",
                "message": "The plan is missing a trigger condition.",
                "field": "trigger.condition_ast",
                "options": [],
            }
        )

    if compile_errors:
        missing.append(
            {
                "code": "compile_failed",
                "message": "The plan could not be compiled into an executable yet.",
                "field": "compiled_executable",
                "options": [],
            }
        )

    return missing


def _compute_plan_confidence(*, compiled_ok: bool, missing_info: list[dict[str, Any]]) -> float:
    score = 0.35
    if compiled_ok:
        score += 0.35
    if not missing_info:
        score += 0.25
    else:
        score -= 0.05 * len(missing_info)
    if score < 0.0:
        score = 0.0
    if score > 1.0:
        score = 1.0
    return float(round(score, 3))


def _normalize_plan_logic_left_ref(left: Any) -> Optional[str]:
    if not isinstance(left, str):
        return None
    text = left.strip()
    if not text:
        return None
    if text.startswith("$."):
        return text
    lowered = text.lower()
    # Small alias set to make the extraction stage resilient across models.
    tx_aliases = {
        "tx.value_native": "$.tx.value_native",
        "tx_value_native": "$.tx.value_native",
        "value_native": "$.tx.value_native",
        "tx.method_selector": "$.tx.method_selector",
        "tx_method_selector": "$.tx.method_selector",
        "method_selector": "$.tx.method_selector",
        "tx.gas_fee_native": "$.tx.gas_fee_native",
        "tx_gas_fee_native": "$.tx.gas_fee_native",
        "gas_fee_native": "$.tx.gas_fee_native",
    }
    if lowered in tx_aliases:
        return tx_aliases[lowered]
    return text


def _normalize_plan_logic_conditions(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        # Be resilient to minor schema drift from local models / adapters.
        left = _normalize_plan_logic_left_ref(item.get("left") or item.get("lhs") or item.get("left_ref"))
        op = _normalize_expr_op(item.get("op") or item.get("operator") or item.get("comparison"))
        right = item.get("right")
        if right is None and "rhs" in item:
            right = item.get("rhs")
        if right is None and "value" in item:
            right = item.get("value")
        if left is None or op is None:
            continue
        if op not in {"gt", "gte", "lt", "lte", "eq", "neq"}:
            continue
        # Permit number or string literals.
        if not isinstance(right, (int, float, str)) and right is not None:
            continue
        out.append({"left": left, "op": op, "right": right})
    return out


def _extract_conditions_from_ast(ast: Any) -> list[dict[str, Any]]:
    if not isinstance(ast, dict):
        return []

    op_raw = ast.get("op")
    op = _normalize_expr_op(op_raw)
    if op in {"gt", "gte", "lt", "lte", "eq", "neq"}:
        left = _normalize_plan_logic_left_ref(ast.get("left"))
        right = ast.get("right")
        if left is None:
            return []
        if right is not None and not isinstance(right, (int, float, str)):
            return []
        return [{"left": left, "op": op, "right": right}]

    if op in {"and", "or"}:
        return _extract_conditions_from_ast(ast.get("left")) + _extract_conditions_from_ast(ast.get("right"))

    extracted: list[dict[str, Any]] = []
    for key in ("all", "any", "not"):
        items = ast.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            extracted.extend(_extract_conditions_from_ast(item))
    return extracted


def _fold_conditions_to_expr_ast(combine_op: str, conditions: list[dict[str, Any]]) -> dict[str, Any]:
    op = str(combine_op or "and").strip().lower()
    if op not in {"and", "or"}:
        op = "and"
    # Empty => placeholder invalid AST (will surface as missing_info/compile_failed).
    if not conditions:
        return {}
    # One => direct leaf.
    if len(conditions) == 1:
        cond = conditions[0]
        return {"op": cond["op"], "left": cond["left"], "right": cond.get("right")}
    # Fold into a binary tree for ExprV1 compatibility.
    cur: dict[str, Any] = {
        "op": conditions[0]["op"],
        "left": conditions[0]["left"],
        "right": conditions[0].get("right"),
    }
    for cond in conditions[1:]:
        cur = {
            "op": op,
            "left": cur,
            "right": {"op": cond["op"], "left": cond["left"], "right": cond.get("right")},
        }
    return cur


def _infer_catalog_ids_from_signal_names(signal_names: set[str]) -> list[str]:
    # Deterministic mapping for v1 allowlisted catalog entries.
    if "pct_change_window" in signal_names:
        return ["ducklake.wallet_balance_window"]
    selected: list[str] = []
    if "tx_count_24h" in signal_names:
        selected.append("ducklake.address_transactions_count_24h")
    if "balance_latest" in signal_names:
        # balance_latest exists in both window+latest; prefer window when pct_change_window is present.
        selected.append("ducklake.wallet_balance_latest")
    return selected


def _signal_unit_for_catalog_column(catalog_id: str, column: str) -> str:
    entry = get_catalog_entry(catalog_id)
    if entry is None:
        return "custom"
    for col in entry.result_schema.columns:
        if col.name == column:
            # Column types are already normalized to "decimal"/"integer"/etc in the catalog.
            return str(col.type or "custom").strip().lower() or "custom"
    return "custom"


def _build_signals_for_columns(*, catalog_ids: list[str], columns: set[str]) -> dict[str, Any]:
    principals: list[dict[str, Any]] = []
    for name in sorted(columns):
        # Choose the first matching catalog id that contains this column.
        chosen: Optional[str] = None
        for cid in catalog_ids:
            entry = get_catalog_entry(cid)
            if entry is None:
                continue
            if any(c.name == name for c in entry.result_schema.columns):
                chosen = cid
                break
        if not chosen:
            continue
        principals.append(
            {
                "name": name,
                "unit": _signal_unit_for_catalog_column(chosen, name),
                "update_sources": [
                    {
                        "ref": chosen,
                        "source_type": "observation",
                        "how_to_ingest": "rpc_call",
                        "polling": {"enabled": True, "cadence_seconds": 300},
                    }
                ],
            }
        )
    return {"principals": principals, "factors": []}


def _ensure_window_duration_variable(template: dict[str, Any], *, default_value: str) -> None:
    variables = template.get("variables")
    if not isinstance(variables, list):
        variables = []
        template["variables"] = variables
    for var in variables:
        if isinstance(var, dict) and str(var.get("id") or "").strip() == "window_duration":
            # Ensure correct type (offline gate).
            var["type"] = "duration"
            return
    variables.append(
        {
            "id": "window_duration",
            "type": "duration",
            "label": "Window duration",
            "required": True,
            "default": default_value,
        }
    )


def _compile_plan_logic_to_template_v2(
    *,
    nl_description: str,
    context: Dict[str, Any],
    target_kind: str,
    combine_op: str,
    conditions: list[dict[str, Any]],
    window_duration: str,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []

    normalized_target_kind = str(target_kind or "wallet").strip().lower() or "wallet"
    if normalized_target_kind not in _SUPPORTED_TARGET_KINDS:
        normalized_target_kind = "wallet"
        warnings.append("target_kind invalid; defaulted to 'wallet'.")

    left_refs = {str(c.get("left") or "").strip() for c in conditions if isinstance(c, dict)}
    signal_names = {ref for ref in left_refs if ref and not ref.startswith("$.")}

    catalog_ids = _infer_catalog_ids_from_signal_names(signal_names)
    # If we selected the window datasource, ensure we don't also select the latest-only variant.
    if "ducklake.wallet_balance_window" in catalog_ids:
        catalog_ids = ["ducklake.wallet_balance_window"]

    # Hybrid when datasources are involved so the Dashboard can offer both scheduled and
    # event-driven evaluation modes (PRD). Tx-only defaults to event-driven.
    evaluation_mode = "hybrid" if catalog_ids else "event_driven"
    cron_cadence_seconds = 300 if catalog_ids else 0

    scope_networks: list[str] = []
    preferred = context.get("preferred_network") or context.get("preferredNetwork")
    if isinstance(preferred, str) and preferred.strip():
        scope_networks = [preferred.strip()]

    condition_ast = _fold_conditions_to_expr_ast(combine_op, conditions)

    template: dict[str, Any] = {
        "schema_version": "alert_template_v2",
        "target_kind": normalized_target_kind,
        "name": _default_template_name(nl_description),
        "description": _default_template_description(nl_description),
        "scope": {"networks": scope_networks, "instrument_constraints": []},
        "signals": {"principals": [], "factors": []},
        "variables": [],
        "trigger": {
            "evaluation_mode": evaluation_mode,
            "condition_ast": condition_ast,
            "cron_cadence_seconds": cron_cadence_seconds,
            "dedupe": {"cooldown_seconds": cron_cadence_seconds, "key_template": "{{instance_id}}:{{target.key}}"},
        },
        "notification": {"title_template": "", "body_template": ""},
        "derivations": [],
        "fallbacks": [],
        "assumptions": [],
    }

    if catalog_ids:
        template["signals"] = _build_signals_for_columns(catalog_ids=catalog_ids, columns=signal_names)
        if "ducklake.wallet_balance_window" in catalog_ids:
            duration = str(window_duration or "").strip()
            if not duration:
                duration = _extract_window_duration_from_text(nl_description) or "24h"
                warnings.append("window_duration missing; defaulted from prompt.")
            _ensure_window_duration_variable(template, default_value=duration)

    variable_ids = {
        str(v.get("id")).strip()
        for v in template.get("variables", [])
        if isinstance(v, dict) and str(v.get("id") or "").strip()
    }
    title_template, body_template = _build_default_notification_templates(
        conditions=conditions,
        variable_ids=variable_ids,
    )
    template["notification"]["title_template"] = title_template
    template["notification"]["body_template"] = body_template

    return template, warnings


def compile_to_proposed_spec(
    *,
    nl_description: str,
    job_id: str,
    client_request_id: Optional[str],
    context: Dict[str, Any],
    pipeline_id: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Compile natural language into a ProposedSpec dict.

    Implementation notes:
    - Uses DSPy if available; falls back to direct LiteLLM calls.
    - Pipeline determines output shape:
      - dspy_compiler_v1 -> ProposedSpec v1 (template)
      - dspy_plan_compiler_v1 -> ProposedSpec v2 (plan + compiled_executable preview)
    """

    selected_pipeline_id = str(pipeline_id or DEFAULT_PIPELINE_ID).strip()
    if not selected_pipeline_id:
        raise ProposedSpecCompilationError("pipeline_id is required")

    def _emit(stage: str, progress: int, message: str) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(stage, int(progress), str(message))
        except Exception:
            # Never let progress publishing crash the compile path.
            return

    try:
        pipeline = get_pipeline_config(selected_pipeline_id)
    except PipelineConfigError as exc:
        raise ProposedSpecCompilationError(str(exc)) from exc
    if pipeline.pipeline_id != PLAN_PIPELINE_ID:
        # Legacy template pipelines have been removed; vNext ProposedSpec v2 is authoritative.
        raise ProposedSpecCompilationError(f"Unsupported pipeline_id {pipeline.pipeline_id!r}")

    ttl_secs = int(getattr(settings, "NLP_PROPOSED_SPEC_TTL_SECS", 3600))
    expires_at = (timezone.now() + timedelta(seconds=ttl_secs)).isoformat()
    ctx = ProposedSpecBuildContext(
        job_id=str(job_id),
        client_request_id=str(client_request_id).strip() if client_request_id else None,
        expires_at=expires_at,
        pipeline_id=pipeline.pipeline_id,
        pipeline_version=pipeline.version,
    )

    nl = _truncate_nl(nl_description)
    if not nl:
        raise ProposedSpecCompilationError("nl_description is required")

    allow_fallback = bool(getattr(settings, "NLP_FALLBACK_ON_DSPY_FAILURE", settings.DEBUG))
    raw_response: Optional[str] = None
    t_total_start = time.monotonic()

    is_plan = pipeline.pipeline_id == PLAN_PIPELINE_ID
    stage_timings_ms: Dict[str, int] = {}
    model_name = str(getattr(settings, "GEMINI_MODEL", "gemini/gemini-3.0-flash"))
    force_direct_llm = bool(getattr(settings, "NLP_FORCE_DIRECT_LLM", False))

    _emit("classify", 10, "Analyzing intent...")

    if force_direct_llm:
        _emit("draft_plan" if is_plan else "draft_template", 35, "Drafting alert logic...")
        t_llm_start = time.monotonic()
        result_payload = _compile_with_llm(
            nl_description=nl,
            job_id=ctx.job_id,
            client_request_id=ctx.client_request_id,
            expires_at=ctx.expires_at,
            context=context,
            pipeline=pipeline,
        )
        stage_timings_ms["draft_plan" if is_plan else "draft_template"] = int((time.monotonic() - t_llm_start) * 1000)
        result = result_payload.parsed
        raw_response = result_payload.raw_response
    else:
        try:
            _emit("draft_plan" if is_plan else "draft_template", 35, "Drafting alert logic...")
            t_llm_start = time.monotonic()
            result_payload = _compile_with_dspy(
                nl_description=nl,
                job_id=ctx.job_id,
                client_request_id=ctx.client_request_id,
                expires_at=ctx.expires_at,
                context=context,
                pipeline=pipeline,
            )
            stage_timings_ms["draft_plan" if is_plan else "draft_template"] = int(
                (time.monotonic() - t_llm_start) * 1000
            )
            result = result_payload.parsed
            raw_response = result_payload.raw_response
        except ProposedSpecCompilationError as exc:
            if not allow_fallback:
                if exc.raw_response is None and raw_response:
                    raise ProposedSpecCompilationError(str(exc), raw_response=raw_response) from exc
                raise
            logger.warning("DSPy compile failed; falling back to direct LLM", exc_info=exc)
            _emit("draft_plan" if is_plan else "draft_template", 35, "Drafting alert logic...")
            t_llm_start = time.monotonic()
            result_payload = _compile_with_llm(
                nl_description=nl,
                job_id=ctx.job_id,
                client_request_id=ctx.client_request_id,
                expires_at=ctx.expires_at,
                context=context,
                pipeline=pipeline,
            )
            stage_timings_ms["draft_plan" if is_plan else "draft_template"] = int(
                (time.monotonic() - t_llm_start) * 1000
            )
            result = result_payload.parsed
            raw_response = result_payload.raw_response

    # vNext plan pipeline: build ProposedSpec v2.
    if pipeline.pipeline_id == PLAN_PIPELINE_ID:
        _emit("resolve_scope", 45, "Checking chain support...")
        _emit("validate", 55, "Validating plan...")
        t_validate_start = time.monotonic()
        template = _extract_template_v2_from_result(result)
        if not isinstance(template, dict):
            raise ProposedSpecCompilationError(
                "ProposedSpec.template must be an object",
                raw_response=raw_response,
            )

        template_spec = deepcopy(template)
        warnings_raw = result.get("warnings", [])
        warnings: list[str] = []
        if isinstance(warnings_raw, list):
            warnings = [str(w).strip() for w in warnings_raw if str(w).strip()]

        _sanitize_plan_targeting(template_spec, warnings=warnings)

        # Ensure top-level identity exists, but keep fingerprint semantics separate.
        if not isinstance(template_spec.get("name"), str) or not str(template_spec.get("name") or "").strip():
            template_spec["name"] = _default_template_name(nl)
            warnings.append("AlertTemplate.name missing; defaulted from prompt.")
        if not isinstance(template_spec.get("description"), str) or not str(template_spec.get("description") or "").strip():
            template_spec["description"] = _default_template_description(nl)
            warnings.append("AlertTemplate.description missing; defaulted from prompt.")

        template_spec["schema_version"] = "alert_template_v2"
        target_kind = str(template_spec.get("target_kind") or "").strip().lower()
        if target_kind not in _SUPPORTED_TARGET_KINDS:
            template_spec["target_kind"] = "wallet"
            warnings.append("AlertTemplate.target_kind missing/invalid; defaulted to 'wallet'.")

        _sanitize_plan_scope(template_spec, context=context if isinstance(context, dict) else {}, warnings=warnings)
        _sanitize_plan_variables(template_spec)
        _sanitize_plan_signals(template_spec, warnings=warnings)
        _sanitize_plan_trigger(template_spec, warnings=warnings)
        _sanitize_plan_notification(template_spec)

        if not isinstance(template_spec.get("derivations"), list):
            template_spec["derivations"] = []
        if not isinstance(template_spec.get("fallbacks"), list):
            template_spec["fallbacks"] = []
        assumptions = template_spec.get("assumptions")
        if not isinstance(assumptions, list):
            assumptions = []
        assumptions_list = [str(a).strip() for a in assumptions if isinstance(a, str) and str(a).strip()]
        template_spec["assumptions"] = assumptions_list

        # Deterministic fingerprint candidate (semantic; excludes identity/presentation keys).
        fingerprint_candidate = compute_template_fingerprint(template_spec)

        # Deterministic preview template_id derived from (fingerprint, snapshot).
        snapshot = get_registry_snapshot()
        preview_template_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{fingerprint_candidate}:{snapshot.get('hash')}")
        template_spec["template_id"] = str(preview_template_id)
        template_spec["template_version"] = 1
        template_spec["fingerprint"] = fingerprint_candidate
        template_spec["spec_hash"] = compute_template_spec_hash(template_spec)
        stage_timings_ms["validate"] = int((time.monotonic() - t_validate_start) * 1000)

        compile_errors: list[str] = []
        # Always include a schema-stable executable envelope, even if compilation fails.
        compiled_executable: Dict[str, Any] = {
            "schema_version": "alert_executable_v1",
            "executable_id": "",
            "template": {
                "schema_version": "alert_template_v2",
                "template_id": str(preview_template_id),
                "fingerprint": str(template_spec.get("fingerprint") or "").strip(),
                "version": int(template_spec.get("template_version") or 1),
            },
            "registry_snapshot": dict(snapshot),
            "target_kind": str(template_spec.get("target_kind") or "").strip() or "wallet",
            "variables": template_spec.get("variables") if isinstance(template_spec.get("variables"), list) else [],
            "trigger_pruning": {},
            "datasources": [],
            "enrichments": [],
            "conditions": {"all": [], "any": [], "not": []},
            "notification_template": {
                "title": str(template_spec.get("name") or "").strip(),
                "body": str(template_spec.get("description") or "").strip(),
            },
            "action": {
                "notification_policy": "per_matched_target",
                "cooldown_secs": 0,
                "cooldown_key_template": "{{instance_id}}:{{target.key}}",
                "dedupe_key_template": "{{run_id}}:{{instance_id}}:{{target.key}}",
            },
            "performance": {},
            "warnings": [],
        }
        compiled_ok = False
        _emit("compile", 75, "Compiling executable...")
        t_compile_start = time.monotonic()
        try:
            compiled_executable = compile_template_to_executable(
                template_spec,
                ctx=CompileContext(template_id=preview_template_id, template_version=1, registry_snapshot=snapshot),
            )
            compiled_ok = True
        except AlertTemplateCompileError as exc:
            compile_errors.append(str(exc))
        stage_timings_ms["compile"] = int((time.monotonic() - t_compile_start) * 1000)

        compile_report: Dict[str, Any] = {
            "registry_snapshot": dict(snapshot),
            "selected_catalog_ids": _collect_plan_catalog_ids(template_spec),
            "fallbacks_used": [],
            "errors": compile_errors,
        }

        missing_info = _build_plan_missing_info(
            template_spec,
            compile_errors=compile_errors,
            context=context if isinstance(context, dict) else {},
        )
        confidence = _compute_plan_confidence(compiled_ok=compiled_ok, missing_info=missing_info)

        _emit("assemble_preview", 90, "Assembling preview...")
        t_assemble_start = time.monotonic()
        # Ensure `assemble_preview` exists as a timing key even if near-zero.
        stage_timings_ms["assemble_preview"] = int((time.monotonic() - t_assemble_start) * 1000)
        pipeline_metadata: Dict[str, Any] = {
            "model": model_name,
            "latency_ms": int((time.monotonic() - t_total_start) * 1000),
            "stage_timings_ms": dict(stage_timings_ms),
        }

        return _build_proposed_spec_v2_envelope(
            template=template_spec,
            compiled_executable=compiled_executable,
            compile_report=compile_report,
            required_user_inputs=_build_plan_required_user_inputs(template_spec),
            human_preview=_build_plan_human_preview(template_spec),
            warnings=warnings,
            confidence=confidence,
            missing_info=missing_info,
            assumptions=assumptions_list,
            pipeline_metadata=pipeline_metadata,
            ctx=ctx,
        )

    raise ProposedSpecCompilationError(f"Unsupported pipeline_id {pipeline.pipeline_id!r}")


def _compile_with_dspy(
    *,
    nl_description: str,
    job_id: str,
    client_request_id: Optional[str],
    expires_at: str,
    context: Dict[str, Any],
    pipeline: PipelineConfig,
) -> LLMParseResult:
    """
    DSPy inference role implementation.

    By default, DSPy is required (PRD). You may allow a direct-LLM fallback for local
    development by setting `NLP_REQUIRE_DSPY=False`.
    """

    require_dspy = bool(getattr(settings, "NLP_REQUIRE_DSPY", True))

    try:
        import dspy  # type: ignore
    except Exception:
        if require_dspy:
            raise ProposedSpecCompilationError("DSPy is required but not installed")
        return _compile_with_llm(
            nl_description=nl_description,
            job_id=job_id,
            client_request_id=client_request_id,
            expires_at=expires_at,
            context=context,
            pipeline=pipeline,
        )

    lm = _configure_dspy_lm(dspy)
    if lm is None:
        if require_dspy:
            raise ProposedSpecCompilationError("Failed to configure DSPy language model")
        return _compile_with_llm(
            nl_description=nl_description,
            job_id=job_id,
            client_request_id=client_request_id,
            expires_at=expires_at,
            context=context,
            pipeline=pipeline,
        )

    is_plan = pipeline.pipeline_id == PLAN_PIPELINE_ID

    # DSPy settings are process-global and not safe to reconfigure from arbitrary
    # threads. Scope the LM to this inference call instead.
    if hasattr(dspy, "context"):
        dspy_ctx = dspy.context(lm=lm)  # type: ignore[attr-defined]
    elif hasattr(getattr(dspy, "settings", None), "context"):
        dspy_ctx = dspy.settings.context(lm=lm)  # type: ignore[attr-defined]
    else:
        dspy_ctx = nullcontext()

    with dspy_ctx:
        if is_plan:
            # Multistage plan compiler:
            # 1) DSPy extracts a small logic spec (no datasources, no targets).
            # 2) We deterministically assemble an AlertTemplate v2 draft from that spec.
            class ExtractPlanLogic(dspy.Signature):  # type: ignore
                """DSPy signature: extract normalized alert logic from natural language."""

                nl_description: str = dspy.InputField()
                prompt_json: str = dspy.InputField()

                target_kind: str = dspy.OutputField()
                combine_op: str = dspy.OutputField()
                conditions: List[Dict[str, Any]] = dspy.OutputField()
                window_duration: str = dspy.OutputField()
                notes: List[str] = dspy.OutputField()

            ExtractPlanLogic.__doc__ = _build_plan_logic_system_prompt(pipeline)
            extractor = dspy.Predict(ExtractPlanLogic)  # type: ignore

            demos = _build_dspy_plan_logic_demos(dspy, pipeline.examples, pipeline)
            if demos and isinstance(getattr(extractor, "demos", None), list):
                extractor.demos.extend(demos)

            prompt_json = _build_plan_logic_prompt_json(nl_description, context, pipeline)
            try:
                response = extractor(nl_description=nl_description, prompt_json=prompt_json)
            except Exception as exc:
                raise ProposedSpecCompilationError(f"DSPy inference failed: {exc}", raw_response=str(exc)) from exc

            target_kind = getattr(response, "target_kind", None)
            combine_op = getattr(response, "combine_op", None)
            conditions_raw = getattr(response, "conditions", None)
            window_duration = getattr(response, "window_duration", None)

            # Adapter variance: some backends may stringify lists/objects.
            if isinstance(conditions_raw, str) and conditions_raw.strip():
                try:
                    conditions_raw = json.loads(conditions_raw)
                except Exception:
                    try:
                        conditions_raw = _extract_first_json_object(conditions_raw)
                    except Exception:
                        conditions_raw = []

            normalized_conditions = _normalize_plan_logic_conditions(conditions_raw)
            normalized_target_kind = str(target_kind or "wallet").strip().lower() or "wallet"
            normalized_window_duration = str(window_duration or "").strip()
            normalized_combine_op = str(combine_op or "and").strip().lower() or "and"

            # If the model omitted required window_duration, fall back to NL parsing.
            if not normalized_window_duration:
                normalized_window_duration = _extract_window_duration_from_text(nl_description) or ""

            if not normalized_conditions:
                # Repair pass: some local-model outputs omit conditions when network is missing.
                class RepairPlanLogic(dspy.Signature):  # type: ignore
                    """DSPy signature: repair missing/invalid plan logic extraction."""

                    nl_description: str = dspy.InputField()
                    prompt_json: str = dspy.InputField()
                    failure_reason: str = dspy.InputField()

                    target_kind: str = dspy.OutputField()
                    combine_op: str = dspy.OutputField()
                    conditions: List[Dict[str, Any]] = dspy.OutputField()
                    window_duration: str = dspy.OutputField()
                    notes: List[str] = dspy.OutputField()

                RepairPlanLogic.__doc__ = _build_plan_logic_repair_system_prompt(pipeline)
                repairer = dspy.Predict(RepairPlanLogic)  # type: ignore
                if demos and isinstance(getattr(repairer, "demos", None), list):
                    repairer.demos.extend(demos)
                try:
                    repaired = repairer(
                        nl_description=nl_description,
                        prompt_json=prompt_json,
                        failure_reason="conditions_empty_after_normalization",
                    )
                except Exception:
                    repaired = None
                if repaired is not None:
                    repaired_conditions = getattr(repaired, "conditions", None)
                    if isinstance(repaired_conditions, str) and repaired_conditions.strip():
                        try:
                            repaired_conditions = json.loads(repaired_conditions)
                        except Exception:
                            repaired_conditions = repaired_conditions
                    normalized_conditions = _normalize_plan_logic_conditions(repaired_conditions)
                    normalized_target_kind = (
                        str(getattr(repaired, "target_kind", normalized_target_kind) or normalized_target_kind)
                        .strip()
                        .lower()
                        or normalized_target_kind
                    )
                    normalized_combine_op = (
                        str(getattr(repaired, "combine_op", normalized_combine_op) or normalized_combine_op)
                        .strip()
                        .lower()
                        or normalized_combine_op
                    )
                    normalized_window_duration = (
                        str(getattr(repaired, "window_duration", normalized_window_duration) or normalized_window_duration)
                        .strip()
                    )

            if not normalized_conditions:
                # Last-resort guardrail: ensure the plan compiles to a schema-safe tx-only condition.
                normalized_conditions = [{"left": "$.tx.value_native", "op": "gt", "right": 0.0}]

            template_value, compile_warnings = _compile_plan_logic_to_template_v2(
                nl_description=nl_description,
                context=context if isinstance(context, dict) else {},
                target_kind=normalized_target_kind,
                combine_op=normalized_combine_op,
                conditions=normalized_conditions,
                window_duration=normalized_window_duration,
            )

            wrapper: Dict[str, Any] = {"template": template_value, "warnings": compile_warnings}
            output_text = json.dumps(wrapper, ensure_ascii=True)
            raw_response = _normalize_llm_response(output_text)
            parsed = {"template": template_value, "warnings": compile_warnings}
            parsed["schema_version"] = "proposed_spec_v2"
            parsed["job_id"] = job_id
            parsed["expires_at"] = expires_at
            if client_request_id:
                parsed["client_request_id"] = client_request_id
            return LLMParseResult(parsed=parsed, raw_response=raw_response)

        # Legacy: single-shot template compiler (kept for local experimentation only).
        class CompileProposedSpec(dspy.Signature):  # type: ignore
            """DSPy signature for AlertTemplate v2 draft compilation."""

            nl_description: str = dspy.InputField()
            context_json: str = dspy.InputField()
            template: Dict[str, Any] = dspy.OutputField(desc="AlertTemplate v2 draft JSON object")
            warnings: List[str] = dspy.OutputField(desc="Warning strings (may be empty)")

        CompileProposedSpec.__doc__ = _build_system_prompt_v2(pipeline)
        compiler = dspy.Predict(CompileProposedSpec)  # type: ignore

        demos = _build_dspy_demos(dspy, pipeline.examples)
        if demos and isinstance(getattr(compiler, "demos", None), list):
            compiler.demos.extend(demos)

        try:
            response = compiler(
                nl_description=nl_description,
                context_json=_build_user_prompt_v2(nl_description, context, pipeline),
            )
        except Exception as exc:
            raise ProposedSpecCompilationError(f"DSPy inference failed: {exc}", raw_response=str(exc)) from exc

        template_value = getattr(response, "template", None)
        warnings_value = getattr(response, "warnings", None)

        if isinstance(template_value, str) and template_value.strip():
            try:
                template_value = _extract_first_json_object(template_value)
            except Exception:
                try:
                    template_value = json.loads(template_value)
                except Exception:
                    template_value = template_value

        if isinstance(warnings_value, str) and warnings_value.strip():
            try:
                warnings_value = json.loads(warnings_value)
            except Exception:
                warnings_value = [warnings_value.strip()]

        wrapper = {"template": template_value, "warnings": warnings_value}
        output_text = json.dumps(wrapper, ensure_ascii=True)
        raw_response = _normalize_llm_response(output_text)
        try:
            parsed = _extract_first_json_object(output_text)
        except ProposedSpecCompilationError as exc:
            raise ProposedSpecCompilationError(str(exc), raw_response=raw_response) from exc
        parsed["schema_version"] = "proposed_spec_v2"
        parsed["job_id"] = job_id
        parsed["expires_at"] = expires_at
        if client_request_id:
            parsed["client_request_id"] = client_request_id
        return LLMParseResult(parsed=parsed, raw_response=raw_response)


def _configure_dspy_lm(dspy_module: Any) -> Any:
    """
    Build a DSPy LM instance.

    DSPy v3 uses `dspy.LM(...)`. Older DSPy builds may expose `dspy.LiteLLM`.

    NOTE: Do not call `dspy.configure(...)` (or `dspy.settings.configure(...)`) from
    background threads. DSPy settings are process-global and guarded to only be
    mutated by the thread that performed the initial configuration. We instead
    scope the LM to inference via `dspy.context(lm=...)` in `_compile_with_dspy`.
    """

    model = getattr(settings, "GEMINI_MODEL", "gemini/gemini-3.0-flash")
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if (not api_key) and str(model or "").strip().lower().startswith("gemini/"):
        raise ProposedSpecCompilationError("GEMINI_API_KEY not configured for gemini/* model")

    try:
        temperature = float(getattr(settings, "NLP_TEMPERATURE", 0.1))
        max_tokens = int(getattr(settings, "NLP_MAX_TOKENS", 2048))

        if hasattr(dspy_module, "LM"):
            lm_kwargs: Dict[str, Any] = {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "cache": False,
            }
            # Avoid passing api_key=None to local backends (e.g. ollama/*), which can
            # trigger an empty `Authorization: Bearer ` header in some HTTP stacks.
            if api_key and str(model or "").strip().lower().startswith("gemini/"):
                lm_kwargs["api_key"] = api_key

            return dspy_module.LM(**lm_kwargs)  # type: ignore[attr-defined]

        if hasattr(dspy_module, "LiteLLM"):
            lite_kwargs: Dict[str, Any] = {"model": model}
            if api_key and str(model or "").strip().lower().startswith("gemini/"):
                lite_kwargs["api_key"] = api_key
            return dspy_module.LiteLLM(**lite_kwargs)  # type: ignore[attr-defined]

    except Exception as exc:
        logger.info("Failed to configure DSPy LM; falling back", exc_info=exc)

    return None


def _compile_with_llm(
    *,
    nl_description: str,
    job_id: str,
    client_request_id: Optional[str],
    expires_at: str,
    context: Dict[str, Any],
    pipeline: PipelineConfig,
) -> LLMParseResult:
    client = get_llm_client()
    is_plan = pipeline.pipeline_id == PLAN_PIPELINE_ID
    system_prompt = _build_system_prompt_v2(pipeline) if is_plan else _build_system_prompt(pipeline)
    prompt = _build_user_prompt_v2(nl_description, context, pipeline) if is_plan else _build_user_prompt(nl_description, context, pipeline)
    try:
        response = client.generate(prompt=prompt, system_prompt=system_prompt, use_cache=False)
    except Exception as exc:
        raise ProposedSpecCompilationError(f"LLM request failed: {exc}") from exc
    raw_response = _normalize_llm_response(response.content)
    try:
        parsed = _extract_first_json_object(raw_response or "")
    except ProposedSpecCompilationError as exc:
        raise ProposedSpecCompilationError(str(exc), raw_response=raw_response) from exc

    parsed["schema_version"] = "proposed_spec_v2" if is_plan else "proposed_spec_v1"
    parsed["job_id"] = job_id
    parsed["expires_at"] = expires_at
    if client_request_id:
        parsed["client_request_id"] = client_request_id
    return LLMParseResult(parsed=parsed, raw_response=raw_response)
