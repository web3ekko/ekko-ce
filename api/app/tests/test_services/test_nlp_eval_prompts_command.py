from __future__ import annotations

from django.test import TestCase


class TestNLPEvalPromptsCommand(TestCase):
    def test_builtin_seed_cases_include_expectations(self):
        from app.management.commands.nlp_eval_prompts import Command

        cases = Command()._load_cases("")
        assert isinstance(cases, list)
        assert len(cases) >= 5

        # Ensure expectations aren't silently dropped when using the built-in seed list.
        sample = cases[0]
        assert "expected_trigger_modes_any_of" in sample
        assert "expected_missing_info_codes_any_of" in sample
        assert "expected_variable_ids_all" in sample

