from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from django.conf import settings

from app.services.datasource_catalog import list_compiler_catalog_entries


def _canonical_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def get_registry_snapshot() -> Dict[str, str]:
    """
    Return a deterministic snapshot descriptor for the compiler-visible registry.

    This is intentionally based on the compiler view (no SQL text) so it is safe to
    embed in ProposedSpec.
    """

    entries = list_compiler_catalog_entries()
    canonical = _canonical_dumps(entries)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    version = str(getattr(settings, "DATASOURCE_CATALOG_VERSION", "v1")).strip() or "v1"
    return {
        "kind": "datasource_catalog",
        "version": version,
        "hash": f"sha256:{digest}",
    }

