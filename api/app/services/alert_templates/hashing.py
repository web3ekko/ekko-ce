from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict


def _canonical_dumps(value: Any) -> str:
    """
    Deterministic JSON serialization used for hashing.

    - sort_keys ensures stable ordering
    - separators remove insignificant whitespace
    """

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_template_spec_hash(template: Dict[str, Any]) -> str:
    """
    Full-hash of canonicalized template JSON (auditing/integrity).
    """

    canonical = _canonical_dumps(template)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


_FINGERPRINT_DROP_KEYS = {
    # Non-semantic / presentation keys.
    "name",
    "description",
    "assumptions",
    "warnings",
    # Server-assigned identity keys (must not affect semantic fingerprint).
    "template_id",
    "template_version",
    "fingerprint",
    "spec_hash",
}


def _strip_non_semantic_fields(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for k, v in value.items():
            if k in _FINGERPRINT_DROP_KEYS:
                continue
            cleaned[k] = _strip_non_semantic_fields(v)
        return cleaned
    if isinstance(value, list):
        return [_strip_non_semantic_fields(v) for v in value]
    return value


def compute_template_fingerprint(template: Dict[str, Any]) -> str:
    """
    Deterministic semantic hash used for dedupe/marketplace uniqueness.

    Important: excludes presentation and server identity fields.
    """

    cleaned = _strip_non_semantic_fields(deepcopy(template))
    canonical = _canonical_dumps(cleaned)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
