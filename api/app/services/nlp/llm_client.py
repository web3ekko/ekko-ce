"""
LLM Client for Django NLP Service.

Direct LiteLLM integration for the NLP pipeline while preserving
chain-of-thought reasoning capabilities.

Features:
- Thread-safe LLM calls
- Built-in response caching
- History tracking for monitoring
- JSON response parsing
- Chain-of-thought prompt helpers
- Django settings integration
"""

import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import litellm
from django.conf import settings

logger = logging.getLogger(__name__)

def _requires_api_key_for_model(model: str) -> bool:
    # Ekko historically named the settings GEMINI_*, but we route through LiteLLM.
    # Only hard-require an API key for Gemini models; local backends (e.g. ollama)
    # should be able to run without any key configured.
    return str(model or "").strip().lower().startswith("gemini/")


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _get_usage_value(usage: Any, key: str) -> Any:
    if isinstance(usage, dict):
        return usage.get(key, 0)
    return getattr(usage, key, 0)


@dataclass
class LLMCallRecord:
    """Record of a single LLM call for history tracking."""

    timestamp: float
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    cached: bool = False
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


@dataclass
class LLMResponse:
    """Structured response from LLM call."""

    content: str
    raw_response: Any
    usage: Dict[str, int] = field(default_factory=dict)
    cached: bool = False
    duration_ms: float = 0.0


class LLMClient:
    """
    Production-ready LLM client for Django NLP service.

    Direct LiteLLM calls while preserving:
    - Same configuration interface
    - Thread-safe operation
    - Response caching
    - History/metrics tracking
    - Chain-of-thought prompting

    Usage:
        client = get_llm_client()
        response = client.generate("Classify this alert: ...")

        # Or with JSON output:
        result = client.generate_json("Return JSON with event_type field",
                                       schema={"event_type": str})
    """

    def __init__(self):
        """Initialize LLM client with Django settings."""
        self._lock = threading.Lock()
        self._cache: Dict[str, str] = {}
        self._cache_lock = threading.Lock()
        self._history: List[LLMCallRecord] = []
        self._history_lock = threading.Lock()
        self._configured = False

        # Load configuration from Django settings
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from Django settings."""
        # PRD default: Gemini 3.0 Flash (can be overridden via GEMINI_MODEL).
        self.model = getattr(settings, "GEMINI_MODEL", "gemini/gemini-3.0-flash")
        self.api_key = getattr(settings, "GEMINI_API_KEY", None)
        self.temperature = getattr(settings, "NLP_TEMPERATURE", 0.1)
        self.max_tokens = getattr(settings, "NLP_MAX_TOKENS", 2048)
        self.timeout = getattr(settings, "NLP_TIMEOUT", 30)
        self.cache_enabled = getattr(settings, "NLP_CACHE_ENABLED", True)
        self.max_retries = getattr(settings, "LLM_MAX_RETRIES", 3)

        if self.api_key or not _requires_api_key_for_model(self.model):
            self._configured = True

        if self._configured:
            logger.info(
                "LLM client configured",
                extra={
                    "model": self.model,
                    "timeout": self.timeout,
                    "cache_enabled": self.cache_enabled,
                    "requires_api_key": _requires_api_key_for_model(self.model),
                },
            )

    def _get_cache_key(self, prompt: str, **kwargs) -> str:
        """Generate cache key from prompt and parameters."""
        cache_data = f"{prompt}|{self.model}|{self.temperature}|{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.sha256(cache_data.encode()).hexdigest()

    def _record_call(
        self,
        response: Optional[Any],
        cached: bool,
        duration_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """Record LLM call in history."""
        record = LLMCallRecord(
            timestamp=time.time(),
            model=self.model,
            cached=cached,
            duration_ms=duration_ms,
            success=error is None,
            error=error,
        )

        usage = getattr(response, "usage", None) if response else None
        if usage:
            record.prompt_tokens = _coerce_int(_get_usage_value(usage, "prompt_tokens"))
            record.completion_tokens = _coerce_int(
                _get_usage_value(usage, "completion_tokens")
            )
            record.total_tokens = _coerce_int(_get_usage_value(usage, "total_tokens"))

        # Estimate cost (Gemini pricing approximate)
        if record.total_tokens > 0:
            record.cost = (record.prompt_tokens * 0.000001) + (record.completion_tokens * 0.000002)

        with self._history_lock:
            self._history.append(record)
            # Keep history bounded
            if len(self._history) > 1000:
                self._history = self._history[-500:]

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        use_cache: bool = True,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate LLM response with optional caching.

        Args:
            prompt: User prompt to send
            system_prompt: Optional system prompt
            use_cache: Whether to use response cache
            temperature: Override default temperature
            max_tokens: Override default max tokens
            **kwargs: Additional parameters for litellm

        Returns:
            LLMResponse with content and metadata

        Raises:
            ValueError: If API key not configured
            Exception: If LLM call fails after retries
        """
        if _requires_api_key_for_model(self.model) and not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured for gemini/* model")

        # Check cache
        cache_key = self._get_cache_key(prompt, system=system_prompt, **kwargs)
        if use_cache and self.cache_enabled:
            with self._cache_lock:
                if cache_key in self._cache:
                    logger.debug("Cache hit for LLM request")
                    self._record_call(None, cached=True, duration_ms=0)
                    return LLMResponse(
                        content=self._cache[cache_key],
                        raw_response=None,
                        cached=True,
                    )

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Make LLM call
        start_time = time.time()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                completion_kwargs: Dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature or self.temperature,
                    "max_tokens": max_tokens or self.max_tokens,
                    "timeout": self.timeout,
                    **kwargs,
                }
                # For local backends (e.g. ollama/*), passing api_key=None can still
                # produce an empty `Authorization: Bearer ` header in some stacks.
                if _requires_api_key_for_model(self.model):
                    completion_kwargs["api_key"] = self.api_key

                response = litellm.completion(**completion_kwargs)

                duration_ms = (time.time() - start_time) * 1000
                content = response.choices[0].message.content

                # Record and cache
                self._record_call(response, cached=False, duration_ms=duration_ms)

                if use_cache and self.cache_enabled:
                    with self._cache_lock:
                        self._cache[cache_key] = content

                return LLMResponse(
                    content=content,
                    raw_response=response,
                    usage={
                        "prompt_tokens": _coerce_int(
                            _get_usage_value(getattr(response, "usage", {}), "prompt_tokens")
                        ),
                        "completion_tokens": _coerce_int(
                            _get_usage_value(getattr(response, "usage", {}), "completion_tokens")
                        ),
                        "total_tokens": _coerce_int(
                            _get_usage_value(getattr(response, "usage", {}), "total_tokens")
                        ),
                    },
                    cached=False,
                    duration_ms=duration_ms,
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    f"LLM call attempt {attempt + 1} failed: {e}",
                    extra={"attempt": attempt + 1, "max_retries": self.max_retries},
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        # All retries failed
        duration_ms = (time.time() - start_time) * 1000
        self._record_call(None, cached=False, duration_ms=duration_ms, error=str(last_error))
        raise last_error

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate LLM response and parse as JSON.

        The prompt should instruct the LLM to return JSON.
        This method extracts JSON from the response, handling
        markdown code blocks and other formatting.

        Args:
            prompt: User prompt requesting JSON output
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Parsed JSON as dictionary

        Raises:
            ValueError: If response cannot be parsed as JSON
        """
        response = self.generate(prompt, system_prompt=system_prompt, **kwargs)
        return parse_json_response(response.content)

    def chain_of_thought(
        self,
        task: str,
        context: str,
        output_fields: Dict[str, str],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute chain-of-thought reasoning and return structured output.

        Provides chain-of-thought reasoning via LiteLLM.

        Args:
            task: The task description (e.g., "Classify this alert request")
            context: Input context for the task
            output_fields: Dict of field_name -> description for expected outputs
            system_prompt: Optional system prompt override
            **kwargs: Additional parameters

        Returns:
            Dict with 'reasoning' and all output fields

        Example:
            result = client.chain_of_thought(
                task="Classify the alert type",
                context="Alert me when ETH drops below $2000",
                output_fields={
                    "event_type": "The classified event type",
                    "sub_event": "The specific sub-event",
                    "confidence": "Confidence score 0.0-1.0",
                }
            )
            # Returns: {"reasoning": "...", "event_type": "...", ...}
        """
        # Build chain-of-thought prompt
        fields_spec = "\n".join(
            f'  "{name}": {desc}'
            for name, desc in output_fields.items()
        )

        cot_prompt = f"""{task}

Input:
{context}

Think through this step by step:
1. Analyze the input carefully
2. Consider all relevant factors
3. Reason through to your conclusion

Respond with JSON containing:
- "reasoning": Your step-by-step analysis
{fields_spec}

Return ONLY valid JSON, no additional text."""

        default_system = (
            "You are an expert analyst. Provide careful, step-by-step reasoning "
            "before reaching conclusions. Always respond with valid JSON."
        )

        return self.generate_json(
            cot_prompt,
            system_prompt=system_prompt or default_system,
            **kwargs,
        )

    def get_history(self, limit: Optional[int] = None) -> List[LLMCallRecord]:
        """
        Get LLM call history for monitoring.

        Args:
            limit: Maximum number of recent calls to return

        Returns:
            List of call records
        """
        with self._history_lock:
            if limit:
                return list(self._history[-limit:])
            return list(self._history)

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics from call history.

        Returns:
            Dict with total_calls, total_tokens, total_cost, cache_hits
        """
        with self._history_lock:
            if not self._history:
                return {
                    "total_calls": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "cache_hits": 0,
                    "success_rate": 1.0,
                    "avg_duration_ms": 0.0,
                }

            total_calls = len(self._history)
            cache_hits = sum(1 for r in self._history if r.cached)
            successful = sum(1 for r in self._history if r.success)
            total_tokens = sum(r.total_tokens for r in self._history)
            total_cost = sum(r.cost for r in self._history)

            non_cached = [r for r in self._history if not r.cached and r.success]
            avg_duration = (
                sum(r.duration_ms for r in non_cached) / len(non_cached)
                if non_cached else 0.0
            )

            return {
                "total_calls": total_calls,
                "total_tokens": total_tokens,
                "total_cost": total_cost,
                "cache_hits": cache_hits,
                "success_rate": successful / total_calls if total_calls > 0 else 1.0,
                "avg_duration_ms": avg_duration,
            }

    def clear_cache(self) -> None:
        """Clear response cache."""
        with self._cache_lock:
            self._cache.clear()
        logger.debug("Cleared LLM response cache")

    def clear_history(self) -> None:
        """Clear call history and response cache."""
        with self._history_lock:
            self._history.clear()
        with self._cache_lock:
            self._cache.clear()
        logger.debug("Cleared LLM call history and response cache")

    @property
    def is_configured(self) -> bool:
        """Check if client is properly configured."""
        return self._configured


def parse_json_response(content: str) -> Dict[str, Any]:
    """
    Parse JSON from LLM response, handling various formats.

    Handles:
    - Plain JSON
    - JSON in markdown code blocks (```json ... ```)
    - JSON with surrounding text

    Args:
        content: Raw LLM response content

    Returns:
        Parsed JSON dictionary

    Raises:
        ValueError: If no valid JSON found
    """
    # Try direct parse first
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    matches = re.findall(code_block_pattern, content)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try finding JSON object in text
    json_pattern = r"\{[\s\S]*\}"
    matches = re.findall(json_pattern, content)
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    raise ValueError(f"Could not parse JSON from response: {content[:200]}...")


def format_cot_prompt(
    task: str,
    context: str,
    output_format: str,
    examples: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Format a chain-of-thought prompt with optional few-shot examples.

    Args:
        task: Task description
        context: Input context
        output_format: Description of expected output format
        examples: Optional list of {"input": ..., "output": ...} examples

    Returns:
        Formatted prompt string
    """
    prompt_parts = [f"Task: {task}\n"]

    if examples:
        prompt_parts.append("Examples:")
        for i, ex in enumerate(examples, 1):
            prompt_parts.append(f"\nExample {i}:")
            prompt_parts.append(f"Input: {ex['input']}")
            prompt_parts.append(f"Output: {ex['output']}")
        prompt_parts.append("\n")

    prompt_parts.extend([
        f"Input:\n{context}\n",
        "Think through this step by step, then provide your answer.",
        f"\n{output_format}",
    ])

    return "\n".join(prompt_parts)


# Singleton instance
_llm_client: Optional[LLMClient] = None
_client_lock = threading.Lock()


def get_llm_client() -> LLMClient:
    """
    Get singleton LLMClient instance.

    Thread-safe singleton pattern for Django usage.

    Returns:
        Configured LLMClient instance
    """
    global _llm_client
    if _llm_client is None:
        with _client_lock:
            if _llm_client is None:
                _llm_client = LLMClient()
    return _llm_client


def configure_llm() -> bool:
    """
    Ensure LLM client is configured.

    Returns:
        True if configuration succeeded
    """
    try:
        client = get_llm_client()
        return client.is_configured
    except Exception as e:
        logger.error(f"Failed to configure LLM client: {e}")
        return False


def is_llm_configured() -> bool:
    """Check if LLM client is configured."""
    return _llm_client is not None and _llm_client.is_configured
