"""
NLP Service (v1, PRD-driven)

Authoritative behavior:
- Parse: NL -> ProposedSpec (async; no DB persistence)
- Save Template: ProposedSpec -> AlertTemplate (sync; dedupe by fingerprint)

See:
- /docs/prd/apps/api/PRD-NLP-Service-USDT.md
- /docs/prd/apps/api/PRD-Alert-System-USDT.md
- /docs/prd/schemas/SCHEMA-ProposedSpec.md
- /docs/prd/schemas/SCHEMA-AlertTemplate.md
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from django.conf import settings


def is_nlp_configured() -> bool:
    """
    Return True when NLP compilation is configured for inference.

    The async parse pipeline should fail fast (503) when this is False.
    """

    if not getattr(settings, "NLP_ENABLED", True):
        return False

    # Ekko routes LLM calls through LiteLLM, but settings are historically named GEMINI_*.
    # Only Gemini models require an API key; local backends (e.g. ollama/*) do not.
    model = str(getattr(settings, "GEMINI_MODEL", "") or "").strip().lower()
    if model.startswith("gemini/"):
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        return bool(api_key and str(api_key).strip())

    return True


def compile_to_proposed_spec(
    *,
    nl_description: str,
    job_id: str,
    client_request_id: Optional[str],
    context: Dict[str, Any],
    pipeline_id: Optional[str] = None,
    progress_callback: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Compile a natural-language request into a ProposedSpec dict.

    This is invoked by the async Django task worker.
    """

    from .compiler import compile_to_proposed_spec as _compile

    return _compile(
        nl_description=nl_description,
        job_id=job_id,
        client_request_id=client_request_id,
        context=context,
        pipeline_id=pipeline_id,
        progress_callback=progress_callback,
    )
