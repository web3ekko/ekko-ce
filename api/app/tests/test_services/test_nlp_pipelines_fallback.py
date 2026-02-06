from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.db.utils import OperationalError
from django.test import TestCase

from app.services.nlp.pipelines import PLAN_PIPELINE_ID, get_pipeline_config


class TestNLPPipelineRegistryFallback(TestCase):
    def test_falls_back_when_registry_tables_missing(self):
        # Offline eval/training should work without applying migrations first.
        mock_qs = MagicMock()
        mock_qs.get.side_effect = OperationalError("no such table: app_nlppipeline")

        with patch("app.services.nlp.pipelines.NLPPipeline.objects.select_related", return_value=mock_qs):
            cfg = get_pipeline_config(PLAN_PIPELINE_ID)

        assert cfg.pipeline_id == PLAN_PIPELINE_ID
        assert cfg.version == "v1"

