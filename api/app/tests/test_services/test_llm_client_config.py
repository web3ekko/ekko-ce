from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from app.services.nlp.llm_client import LLMClient


class TestLLMClientConfig(TestCase):
    @override_settings(GEMINI_MODEL="gemini/gemini-3.0-flash", GEMINI_API_KEY="")
    def test_gemini_model_requires_api_key(self):
        client = LLMClient()
        assert client.is_configured is False
        with self.assertRaises(ValueError):
            client.generate("hi")

    @override_settings(GEMINI_MODEL="ollama/llama3.1", GEMINI_API_KEY="")
    def test_local_model_does_not_require_api_key(self):
        client = LLMClient()
        assert client.is_configured is True

        fake_resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))],
            usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )
        with patch("app.services.nlp.llm_client.litellm.completion", return_value=fake_resp) as mocked:
            resp = client.generate('{"ping":"pong"}', system_prompt="Return JSON")
        # Local backends should not receive an empty Authorization header (api_key=None).
        assert "api_key" not in mocked.call_args.kwargs
        assert resp.content == '{"ok":true}'

    @override_settings(GEMINI_MODEL="gemini/gemini-3.0-flash", GEMINI_API_KEY="test-key")
    def test_gemini_model_passes_api_key_to_litellm(self):
        client = LLMClient()
        assert client.is_configured is True

        fake_resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))],
            usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )
        with patch("app.services.nlp.llm_client.litellm.completion", return_value=fake_resp) as mocked:
            client.generate('{"ping":"pong"}', system_prompt="Return JSON")
        assert mocked.call_args.kwargs.get("api_key") == "test-key"
