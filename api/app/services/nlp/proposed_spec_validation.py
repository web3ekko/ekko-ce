from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


class ProposedSpecError(ValueError):
    pass


def extract_template_from_proposed_spec(
    proposed_spec: Dict[str, Any], *, expected_job_id: Optional[str] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Validate ProposedSpec shape (v2) and return (template, required_user_inputs).

    Note: vNext templates are executable-backed and validated/compiled at save time.
    """

    if not isinstance(proposed_spec, dict):
        raise ProposedSpecError("ProposedSpec must be an object")

    if proposed_spec.get("schema_version") != "proposed_spec_v2":
        raise ProposedSpecError("Invalid ProposedSpec.schema_version")

    job_id = proposed_spec.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        raise ProposedSpecError("ProposedSpec.job_id must be a non-empty string")
    if expected_job_id and job_id != expected_job_id:
        raise ProposedSpecError("ProposedSpec.job_id does not match request job_id")

    template = proposed_spec.get("template")
    if not isinstance(template, dict):
        raise ProposedSpecError("ProposedSpec.template must be an object")

    required_user_inputs = proposed_spec.get("required_user_inputs") or {}
    if not isinstance(required_user_inputs, dict):
        raise ProposedSpecError("ProposedSpec.required_user_inputs must be an object")

    return template, required_user_inputs


def extract_compiled_executable_from_proposed_spec(
    proposed_spec: Dict[str, Any], *, expected_job_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate ProposedSpec shape (v2) and return compiled_executable.

    This is used by preview/inspection flows where the UI needs to test the compiled
    executable without trusting client-provided JSON.
    """

    if not isinstance(proposed_spec, dict):
        raise ProposedSpecError("ProposedSpec must be an object")

    if proposed_spec.get("schema_version") != "proposed_spec_v2":
        raise ProposedSpecError("Invalid ProposedSpec.schema_version")

    job_id = proposed_spec.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        raise ProposedSpecError("ProposedSpec.job_id must be a non-empty string")
    if expected_job_id and job_id != expected_job_id:
        raise ProposedSpecError("ProposedSpec.job_id does not match request job_id")

    compiled = proposed_spec.get("compiled_executable")
    if not isinstance(compiled, dict):
        raise ProposedSpecError("ProposedSpec.compiled_executable must be an object")

    return compiled
