from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from app.services.nlp.compiler import ProposedSpecCompilationError
from app.tasks import nlp_tasks


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class TestNlpTasks(TestCase):
    def test_parse_nl_description_persists_raw_llm_response_on_failure(self) -> None:
        cache.clear()
        user_id = "user-123"
        job_id = "job-123"
        raw_response = '{"template": {"conditions": "bad"}}'
        error = ProposedSpecCompilationError("boom", raw_response=raw_response)

        with patch("app.tasks.nlp_tasks.publish_progress", return_value=True), patch(
            "app.services.nlp.is_nlp_configured",
            return_value=True,
        ), patch(
            "app.services.nlp.compile_to_proposed_spec",
            side_effect=error,
        ):
            with self.assertRaises(ProposedSpecCompilationError):
                nlp_tasks.parse_nl_description(
                    user_id=user_id,
                    nl_description="test",
                    job_id=job_id,
                )

        cached = cache.get(f"nlp:raw_response:{user_id}:{job_id}")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["raw_response"], raw_response)
        self.assertEqual(cached["error"], "boom")
        self.assertFalse(cached["truncated"])
