from __future__ import annotations

import json
from pathlib import Path


def test_curated_demos_include_notification_placeholders():
    path = Path(__file__).resolve().parents[3] / "test-results" / "nlp_curated_demos_seed_v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert payload, "curated demo file should not be empty"

    for example in payload:
        output = example.get("output_json", {})
        notification = output.get("notification", {}) if isinstance(output, dict) else {}
        title = str(notification.get("title_template") or "")
        body = str(notification.get("body_template") or "")
        assert "{{" in title or "{{" in body
