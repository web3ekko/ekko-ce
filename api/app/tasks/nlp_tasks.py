"""
NLP Processing Tasks - Django 6.0 Task Framework

Async Parse pipeline with WebSocket progress events.

Workflow (authoritative PRDs):
1. POST /api/alerts/parse/ → 202 + job_id (no DB persistence)
2. Django Task compiles NL → ProposedSpec (untrusted until validated)
3. Progress events published to NATS ws.events
4. wasmCloud WS provider forwards to connected clients
5. ProposedSpec stored in Redis (TTL configurable; default 1 hour)
6. POST /api/alert-templates/ with job_id → saves AlertTemplate (dedupe by fingerprint)
"""

import logging
from typing import Any, Dict, Optional

from django.core.cache import cache
from django.conf import settings

from app.tasks.tasking import task
from app.services.nlp.pipelines import DEFAULT_PIPELINE_ID

logger = logging.getLogger(__name__)

def _truncate_raw_response(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return f"{text[: max_chars - 3].rstrip()}..."


def _persist_raw_llm_response(
    *,
    user_id: str,
    job_id: str,
    error: Exception,
    raw_response: Optional[str],
) -> None:
    if not raw_response:
        return

    ttl_secs = int(getattr(settings, "NLP_PROPOSED_SPEC_TTL_SECS", 3600))
    max_chars = int(getattr(settings, "NLP_RAW_RESPONSE_MAX_CHARS", 20000))
    truncated = raw_response
    was_truncated = len(raw_response) > max_chars
    if was_truncated:
        truncated = _truncate_raw_response(raw_response, max_chars)

    cache_key = f"nlp:raw_response:{user_id}:{job_id}"
    cache.set(
        cache_key,
        {
            "raw_response": truncated,
            "error": str(error),
            "truncated": was_truncated,
        },
        timeout=ttl_secs,
    )


def publish_progress(user_id: str, event_type: str, job_id: str, payload: Dict[str, Any]) -> bool:
    """
    Publish progress event to NATS ws.events.

    Uses the sync wrapper from nats_service.
    """
    from app.services.nats_service import publish_ws_event_sync

    return publish_ws_event_sync(
        user_id=user_id,
        event_type=event_type,
        payload=payload,
        job_id=job_id,
    )


@task(queue_name="nlp")
def parse_nl_description(
    user_id: str,
    nl_description: str,
    job_id: str,
    client_request_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    pipeline_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Async NLP parse task - compiles to ProposedSpec, stores in Redis, emits WS events.

    Called from /api/alerts/parse/ endpoint via task.enqueue().

    Args:
        user_id: User ID for WebSocket routing
        nl_description: Natural language alert description
        job_id: Unique job identifier for tracking
        client_request_id: Optional client correlation id (UUID)
        context: Optional context object from the client

    Returns:
        ProposedSpec dictionary (also stored in Redis)

    Events Published:
        - nlp.status: Progress updates (stage, progress, message)
        - nlp.complete: Parse completed (result: ProposedSpec)
        - nlp.error: Parse failed (code, message, suggestions)
    """
    from app.services.nlp import compile_to_proposed_spec, is_nlp_configured
    from app.services.nlp.compiler import ProposedSpecCompilationError

    try:
        if not is_nlp_configured():
            publish_progress(user_id, "nlp.error", job_id, {
                "client_request_id": client_request_id,
                "code": "nlp_not_configured",
                "message": "NLP service not configured",
                "suggestions": ["Try again later", "Contact support if this persists"],
            })
            raise ValueError("NLP service not configured")

        selected_pipeline_id = pipeline_id or DEFAULT_PIPELINE_ID
        last_progress: dict[str, object] = {"stage": None, "progress": None}

        def progress_cb(stage: str, progress: int, message: str) -> None:
            # Avoid spamming; emit only when stage/progress changes.
            if last_progress.get("stage") == stage and last_progress.get("progress") == progress:
                return
            last_progress["stage"] = stage
            last_progress["progress"] = progress
            publish_progress(
                user_id,
                "nlp.status",
                job_id,
                {
                    "client_request_id": client_request_id,
                    "stage": stage,
                    "progress": progress,
                    "message": message,
                },
            )

        proposed_spec = compile_to_proposed_spec(
            nl_description=nl_description.strip(),
            job_id=job_id,
            client_request_id=client_request_id,
            context=context or {},
            pipeline_id=selected_pipeline_id,
            progress_callback=progress_cb,
        )

        ttl_secs = int(getattr(settings, "NLP_PROPOSED_SPEC_TTL_SECS", 3600))
        cache_key = f"nlp:proposed_spec:{user_id}:{job_id}"
        cache.set(cache_key, proposed_spec, timeout=ttl_secs)

        publish_progress(user_id, "nlp.complete", job_id, {
            "client_request_id": client_request_id,
            "result": proposed_spec,
        })

        logger.info(f"NLP parse completed: job_id={job_id}, user_id={user_id}")
        return proposed_spec

    except ProposedSpecCompilationError as e:
        _persist_raw_llm_response(
            user_id=user_id,
            job_id=job_id,
            error=e,
            raw_response=e.raw_response,
        )
        if e.raw_response:
            max_log_chars = int(getattr(settings, "NLP_RAW_RESPONSE_LOG_MAX_CHARS", 2000))
            logger.error(
                "NLP parse failed: job_id=%s, error=%s, raw_response=%s",
                job_id,
                e,
                _truncate_raw_response(e.raw_response, max_log_chars),
            )
        else:
            logger.error(f"NLP parse failed: job_id={job_id}, error={e}")
        publish_progress(user_id, "nlp.error", job_id, {
            "client_request_id": client_request_id,
            "code": "compile_failed",
            "message": str(e),
            "suggestions": ["Try rephrasing the request", "Specify a network (ETH/AVAX)"],
        })
        raise
    except Exception as e:
        logger.error(f"NLP parse failed: job_id={job_id}, error={e}")
        publish_progress(user_id, "nlp.error", job_id, {
            "client_request_id": client_request_id,
            "code": "compile_failed",
            "message": str(e),
            "suggestions": ["Try rephrasing the request", "Specify a network (ETH/AVAX)"],
        })
        raise
