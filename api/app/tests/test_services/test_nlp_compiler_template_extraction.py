import json

from app.services.nlp.compiler import _extract_template_from_result


def _template_stub() -> dict:
    return {
        "name": "Balance Alert",
        "description": "Alert on balance change",
        "alert_type": "wallet",
        "trigger": {},
        "conditions": {},
    }


def test_extracts_template_from_direct_field():
    template = _template_stub()
    result = {"template": template}
    assert _extract_template_from_result(result) == template


def test_extracts_template_from_json_string_field():
    template = _template_stub()
    result = {"template": json.dumps(template)}
    assert _extract_template_from_result(result) == template


def test_extracts_template_from_wrapped_payload():
    template = _template_stub()
    result = {"data": {"template": template}}
    assert _extract_template_from_result(result) == template


def test_extracts_template_from_top_level_spec():
    template = _template_stub()
    assert _extract_template_from_result(template) == template


def test_returns_none_for_invalid_template_payload():
    result = {"template": "not-json"}
    assert _extract_template_from_result(result) is None
