from __future__ import annotations

from django.test import TestCase

from app.services.datasource_catalog.catalog import list_catalog_entries
from app.services.nlp.eval.seed_prompts import seed_prompt_cases


class TestNLPSeedPrompts(TestCase):
    def test_seed_prompts_are_end_user_intent_only(self):
        catalog_ids = [e.catalog_id for e in list_catalog_entries()]

        cases = seed_prompt_cases()
        assert len(cases) >= 5

        for case in cases:
            nl = case.nl_description
            assert isinstance(nl, str) and nl.strip()

            # Guardrail: seed prompts must not include internal datasource IDs.
            for catalog_id in catalog_ids:
                assert catalog_id not in nl

            # Avoid teaching users internal terms via examples.
            lowered = nl.lower()
            assert "ducklake." not in lowered
            assert "datasource" not in lowered

    def test_seed_prompt_expectations_reference_allowlisted_catalog_ids(self):
        allowlisted = {e.catalog_id for e in list_catalog_entries()}
        for case in seed_prompt_cases():
            if not case.expected_catalog_ids_any_of:
                continue
            for cid in case.expected_catalog_ids_any_of:
                assert cid in allowlisted

