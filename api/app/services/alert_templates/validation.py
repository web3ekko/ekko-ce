from __future__ import annotations

from typing import Any, Dict


class AlertTemplateSpecError(ValueError):
    pass


_VAR_TYPES = {
    "string",
    "integer",
    "decimal",
    "boolean",
    "enum",
    "enum_multi",
    "duration",
}


def _validate_variable_value(var: Dict[str, Any], value: Any) -> None:
    var_id = str(var.get("id") or "").strip()
    var_type = str(var.get("type") or "string").strip().lower()
    validation = var.get("validation") if isinstance(var.get("validation"), dict) else {}

    if var_type not in _VAR_TYPES:
        raise AlertTemplateSpecError(f"Unsupported variable type '{var_type}' for {var_id}")

    if var_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise AlertTemplateSpecError(f"Variable '{var_id}' must be an integer")
        if "min" in validation and value < validation["min"]:
            raise AlertTemplateSpecError(f"Variable '{var_id}' must be >= {validation['min']}")
        if "max" in validation and value > validation["max"]:
            raise AlertTemplateSpecError(f"Variable '{var_id}' must be <= {validation['max']}")
        return

    if var_type == "decimal":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AlertTemplateSpecError(f"Variable '{var_id}' must be a number")
        numeric = float(value)
        if "min" in validation and numeric < float(validation["min"]):
            raise AlertTemplateSpecError(f"Variable '{var_id}' must be >= {validation['min']}")
        if "max" in validation and numeric > float(validation["max"]):
            raise AlertTemplateSpecError(f"Variable '{var_id}' must be <= {validation['max']}")
        return

    if var_type == "boolean":
        if not isinstance(value, bool):
            raise AlertTemplateSpecError(f"Variable '{var_id}' must be a boolean")
        return

    if var_type == "enum":
        if not isinstance(value, str) or not value.strip():
            raise AlertTemplateSpecError(f"Variable '{var_id}' must be a non-empty string")
        options = validation.get("options") if isinstance(validation, dict) else None
        if isinstance(options, list) and options and value not in options:
            raise AlertTemplateSpecError(f"Variable '{var_id}' must be one of: {options}")
        return

    if var_type == "enum_multi":
        if not isinstance(value, list):
            raise AlertTemplateSpecError(f"Variable '{var_id}' must be a list")
        options = validation.get("options") if isinstance(validation, dict) else None
        if isinstance(options, list) and options:
            invalid = [v for v in value if v not in options]
            if invalid:
                raise AlertTemplateSpecError(f"Variable '{var_id}' contains invalid values: {invalid}")
        return

    if var_type == "duration":
        if not isinstance(value, str) or not value.strip():
            raise AlertTemplateSpecError(f"Variable '{var_id}' must be a non-empty duration string")
        return

    # string
    if not isinstance(value, str):
        raise AlertTemplateSpecError(f"Variable '{var_id}' must be a string")


def validate_variable_values_against_template(template_spec: Dict[str, Any], variable_values: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate instance variable_values against AlertTemplate.variables and return resolved values.

    Rules:
    - required variables must be present or have defaults
    - extra keys are rejected
    """

    if not isinstance(template_spec, dict):
        raise AlertTemplateSpecError("template_spec must be an object")
    if not isinstance(variable_values, dict):
        raise AlertTemplateSpecError("variable_values must be an object")

    variables = template_spec.get("variables") or []
    if not isinstance(variables, list):
        raise AlertTemplateSpecError("template_spec.variables must be a list")

    resolved: Dict[str, Any] = {}
    allowed_ids: set[str] = set()

    for var in variables:
        if not isinstance(var, dict):
            continue
        var_id = var.get("id")
        if not isinstance(var_id, str) or not var_id.strip():
            continue
        var_id = var_id.strip()
        allowed_ids.add(var_id)

        required = bool(var.get("required", False))
        has_default = "default" in var

        if var_id in variable_values:
            value = variable_values[var_id]
        elif has_default:
            value = var.get("default")
        elif required:
            raise AlertTemplateSpecError(f"Missing required variable: {var_id}")
        else:
            continue

        _validate_variable_value(var, value)
        resolved[var_id] = value

    extras = [k for k in variable_values.keys() if k not in allowed_ids]
    if extras:
        raise AlertTemplateSpecError(f"Unknown variables: {sorted(extras)}")

    return resolved
