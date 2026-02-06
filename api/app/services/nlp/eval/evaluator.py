from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.datasource_catalog.catalog import list_catalog_entries


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    ok: bool
    errors: List[str]
    selected_catalog_ids: List[str]
    template_trigger_mode: Optional[str] = None


def _walk_keys(value: Any) -> List[str]:
    keys: List[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            keys.append(str(k))
            keys.extend(_walk_keys(v))
    elif isinstance(value, list):
        for item in value:
            keys.extend(_walk_keys(item))
    return keys


def _contains_eth_address(value: Any) -> bool:
    # Detect EVM address literals (0x + 40 hex chars) anywhere in the output.
    import re

    text = ""
    try:
        text = json_dumps_stable(value)
    except Exception:
        text = str(value)
    return re.search(r"0x[a-fA-F0-9]{40}", text) is not None


def json_dumps_stable(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _collect_selected_catalog_ids(proposed_spec: Dict[str, Any]) -> List[str]:
    report = proposed_spec.get("compile_report") if isinstance(proposed_spec.get("compile_report"), dict) else {}
    selected = report.get("selected_catalog_ids")
    if isinstance(selected, list):
        return [str(x) for x in selected if isinstance(x, str) and str(x).strip()]

    # Fallback: derive from executable datasource refs.
    exe = proposed_spec.get("compiled_executable") if isinstance(proposed_spec.get("compiled_executable"), dict) else {}
    datasources = exe.get("datasources")
    if not isinstance(datasources, list):
        return []

    ids: List[str] = []
    for ds in datasources:
        if not isinstance(ds, dict):
            continue
        ref = ds.get("catalog_id") or ds.get("ref") or ds.get("catalogId")
        if isinstance(ref, str) and ref.strip():
            ids.append(ref.strip())
    return ids


def evaluate_compiler_output(
    *,
    case_id: str,
    proposed_spec: Dict[str, Any],
    expected_catalog_ids_any_of: Optional[List[str]] = None,
    expected_no_catalog_ids: bool = False,
    expected_trigger_modes_any_of: Optional[List[str]] = None,
    expected_missing_info_codes_any_of: Optional[List[str]] = None,
    expected_variable_ids_all: Optional[List[str]] = None,
) -> EvalResult:
    errors: List[str] = []

    if proposed_spec.get("schema_version") != "proposed_spec_v2":
        errors.append("schema_version must be proposed_spec_v2")

    template = proposed_spec.get("template") if isinstance(proposed_spec.get("template"), dict) else {}
    if template.get("schema_version") != "alert_template_v2":
        errors.append("template.schema_version must be alert_template_v2")

    # Required keys (v2 draft surface).
    required_template_keys = {"schema_version", "target_kind", "scope", "signals", "trigger", "notification"}
    if not required_template_keys.issubset(set(template.keys())):
        missing = sorted(required_template_keys - set(template.keys()))
        errors.append(f"template missing required keys: {missing}")

    target_kind = str(template.get("target_kind") or "").strip().lower()
    if target_kind not in {"wallet", "contract", "token", "network", "protocol"}:
        errors.append(f"template.target_kind invalid: {template.get('target_kind')!r}")

    # Targets must never appear in templates.
    forbidden_keys = {"target_keys", "candidate_target_keys", "group_id", "targets"}
    keys = set(_walk_keys(template))
    if forbidden_keys & keys:
        errors.append(f"template contains forbidden keys: {sorted(forbidden_keys & keys)}")

    if _contains_eth_address(template):
        errors.append("template contains an EVM address literal (0x...40 hex); targets must not appear in templates")

    selected_ids = _collect_selected_catalog_ids(proposed_spec)
    allowlisted_catalog_ids = {e.catalog_id for e in list_catalog_entries() if getattr(e, "enabled", True)}
    for cid in selected_ids:
        if cid not in allowlisted_catalog_ids:
            errors.append(f"selected_catalog_id not allowlisted: {cid!r}")

    trigger = template.get("trigger") if isinstance(template.get("trigger"), dict) else {}
    mode = trigger.get("evaluation_mode")
    mode_str = str(mode).strip().lower() if isinstance(mode, str) else None
    if mode_str not in {"event_driven", "periodic", "hybrid"}:
        errors.append(f"template.trigger.evaluation_mode invalid: {mode!r}")

    condition_ast = trigger.get("condition_ast")
    if not isinstance(condition_ast, dict) or not condition_ast:
        errors.append("template.trigger.condition_ast must be a non-empty expression object")
    elif not isinstance(condition_ast.get("op"), str) or not str(condition_ast.get("op") or "").strip():
        errors.append("template.trigger.condition_ast must include a non-empty 'op' string")

    if expected_no_catalog_ids and isinstance(condition_ast, dict) and condition_ast:
        # Tx-only alerts must be evaluable from the tx context alone.
        ast_text = json_dumps_stable(condition_ast)
        if "$.tx." not in ast_text and "$.schedule." not in ast_text:
            errors.append("expected tx-only condition_ast to reference $.tx.* (or $.schedule.*), but it did not")

    if expected_trigger_modes_any_of:
        expected_modes = {m.strip().lower() for m in expected_trigger_modes_any_of if isinstance(m, str) and m.strip()}
        if expected_modes and (mode_str not in expected_modes):
            errors.append(f"expected trigger mode in {sorted(expected_modes)}, got {mode_str!r}")

    compile_report = proposed_spec.get("compile_report") if isinstance(proposed_spec.get("compile_report"), dict) else {}
    compile_errors = compile_report.get("errors")
    if isinstance(compile_errors, list) and [e for e in compile_errors if str(e).strip()]:
        errors.append(f"compile_report.errors not empty: {compile_errors}")

    missing_info = proposed_spec.get("missing_info")
    missing_codes: List[str] = []
    if isinstance(missing_info, list):
        for item in missing_info:
            if not isinstance(item, dict):
                continue
            code = item.get("code")
            if isinstance(code, str) and code.strip():
                missing_codes.append(code.strip())
    else:
        missing_info = []

    if expected_missing_info_codes_any_of:
        expected_missing = {
            c.strip() for c in expected_missing_info_codes_any_of if isinstance(c, str) and c.strip()
        }
        if expected_missing and not (set(missing_codes) & expected_missing):
            errors.append(f"expected missing_info codes to include one of {sorted(expected_missing)}, got {missing_codes}")
    else:
        # For "happy path" eval cases we expect the compiler to resolve everything.
        if missing_codes:
            errors.append(f"unexpected missing_info present: {missing_codes}")
        else:
            # When not missing info, ensure a concrete network was selected.
            scope = template.get("scope") if isinstance(template.get("scope"), dict) else {}
            networks = scope.get("networks")
            if not isinstance(networks, list) or not [n for n in networks if isinstance(n, str) and n.strip()]:
                errors.append("expected template.scope.networks to be non-empty when missing_info is empty")

    if expected_no_catalog_ids and selected_ids:
        errors.append(f"expected no datasources, but selected {selected_ids}")

    if expected_no_catalog_ids:
        signals = template.get("signals") if isinstance(template.get("signals"), dict) else {}
        principals = signals.get("principals") if isinstance(signals.get("principals"), list) else []
        factors = signals.get("factors") if isinstance(signals.get("factors"), list) else []
        if principals or factors:
            errors.append("expected tx-only alert (no signals), but template.signals is non-empty")
        compiled_executable = proposed_spec.get("compiled_executable") if isinstance(proposed_spec.get("compiled_executable"), dict) else {}
        datasources = compiled_executable.get("datasources")
        if isinstance(datasources, list) and datasources:
            errors.append("expected tx-only alert (no datasources), but compiled_executable.datasources is non-empty")

    # If we expect datasources, ensure the LLM declared signal sources explicitly (don't rely on
    # compilation heuristics like text scanning).
    if expected_catalog_ids_any_of:
        signals = template.get("signals") if isinstance(template.get("signals"), dict) else {}
        declared_ids: list[str] = []
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
                    if isinstance(ref, str) and ref.strip():
                        declared_ids.append(ref.strip())

        if not declared_ids:
            errors.append("expected at least one signal.update_sources[].ref, but none were declared")
        elif not any(cid in set(declared_ids) for cid in expected_catalog_ids_any_of):
            errors.append(
                "expected signal.update_sources[].ref to include one of "
                f"{expected_catalog_ids_any_of}, got {sorted(set(declared_ids))}"
            )

    if expected_catalog_ids_any_of:
        if not any(cid in set(selected_ids) for cid in expected_catalog_ids_any_of):
            errors.append(
                "expected datasource selection to include one of "
                f"{expected_catalog_ids_any_of}, got {selected_ids}"
            )

    if expected_variable_ids_all:
        variables = template.get("variables") if isinstance(template.get("variables"), list) else []
        var_ids = {
            str(v.get("id")).strip()
            for v in variables
            if isinstance(v, dict) and isinstance(v.get("id"), str) and str(v.get("id")).strip()
        }
        missing_vars = [vid for vid in expected_variable_ids_all if isinstance(vid, str) and vid.strip() and vid.strip() not in var_ids]
        if missing_vars:
            errors.append(f"expected template.variables to include ids {missing_vars}, got {sorted(var_ids)}")
        # Known variable semantics we want the model to learn (strict offline gate).
        for var in variables:
            if not isinstance(var, dict):
                continue
            var_id = str(var.get("id") or "").strip()
            if not var_id:
                continue
            if var_id == "window_duration":
                vtype = str(var.get("type") or "").strip().lower()
                if vtype != "duration":
                    errors.append(f"window_duration variable must have type 'duration', got {vtype!r}")

    compiled_executable = proposed_spec.get("compiled_executable")
    if not isinstance(compiled_executable, dict) or compiled_executable.get("schema_version") != "alert_executable_v1":
        errors.append("compiled_executable.schema_version must be alert_executable_v1")

    ok = len(errors) == 0
    return EvalResult(
        case_id=case_id,
        ok=ok,
        errors=errors,
        selected_catalog_ids=selected_ids,
        template_trigger_mode=mode_str,
    )
