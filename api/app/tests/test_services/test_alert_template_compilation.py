import uuid

import pytest

from app.services.alert_templates.compilation import (
    AlertTemplateCompileError,
    CompileContext,
    compile_template_to_executable,
)
from app.services.alert_templates.registry_snapshot import get_registry_snapshot


def _compile(template: dict) -> dict:
    template_id = uuid.uuid4()
    snapshot = get_registry_snapshot()
    return compile_template_to_executable(
        template,
        ctx=CompileContext(template_id=template_id, template_version=1, registry_snapshot=snapshot),
    )


def test_compile_allows_tx_only_template_without_datasources() -> None:
    tpl = {
        "schema_version": "alert_template_v2",
        "name": "Incoming Transfer Threshold",
        "description": "Notify when a wallet receives a large native transfer",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [
            {
                "id": "threshold",
                "type": "decimal",
                "label": "Threshold",
                "required": True,
                "default": 0.01,
            }
        ],
        "signals": {"principals": [], "factors": []},
        "derivations": [],
        "trigger": {
            "evaluation_mode": "event_driven",
            "condition_ast": {"op": "gt", "left": "$.tx.value_native", "right": "{{threshold}}"},
            "cron_cadence_seconds": 0,
            "dedupe": {"cooldown_seconds": 60, "key_template": "{{instance_id}}:{{target.key}}"},
            "pruning_hints": {"evm": {"tx_type": "native_transfer"}},
        },
        "notification": {
            "title_template": "Incoming transfer: {{target.short}}",
            "body_template": "Received {{$.tx.value_native}} ETH",
        },
        "fallbacks": [],
        "assumptions": [],
        "fingerprint": "sha256:" + "0" * 64,
    }

    exe = _compile(tpl)
    assert exe["schema_version"] == "alert_executable_v1"
    assert exe["datasources"] == []
    assert exe["conditions"]["all"][0]["left"] == "$.tx.value_native"


def test_compile_maps_derivation_names_into_condition() -> None:
    tpl = {
        "schema_version": "alert_template_v2",
        "name": "Incoming Transfer Threshold (Wei)",
        "description": "Notify when a wallet receives a large native transfer (wei-based)",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [
            {
                "id": "threshold_wei",
                "type": "integer",
                "label": "Threshold (wei)",
                "required": True,
                "default": 10**16,
            }
        ],
        "signals": {"principals": [], "factors": []},
        "derivations": [
            {
                "name": "tx_value_wei",
                "expr_ast": {"op": "coalesce", "values": ["$.tx.value_wei", "$.tx.value"]},
                "output_unit": "WEI",
            }
        ],
        "trigger": {
            "evaluation_mode": "event_driven",
            "condition_ast": {"op": "gte", "left": "tx_value_wei", "right": "{{threshold_wei}}"},
            "cron_cadence_seconds": 0,
            "dedupe": {"cooldown_seconds": 60, "key_template": "{{instance_id}}:{{target.key}}"},
            "pruning_hints": {"evm": {"tx_type": "native_transfer"}},
        },
        "notification": {"title_template": "Incoming transfer", "body_template": "wei={{tx_value_wei}}"},
        "fallbacks": [],
        "assumptions": [],
        "fingerprint": "sha256:" + "1" * 64,
    }

    exe = _compile(tpl)
    assert exe["datasources"] == []
    # Condition should reference the enrichment output, not a bare identifier.
    assert exe["conditions"]["all"][0]["left"] == "$.enrichment.tx_value_wei"


def test_compile_rejects_unresolved_signal_shorthand() -> None:
    tpl = {
        "schema_version": "alert_template_v2",
        "name": "Broken Template",
        "description": "References a signal without selecting a datasource",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [{"id": "threshold", "type": "decimal", "label": "Threshold", "required": True}],
        "signals": {
            "principals": [],
            "factors": [{"name": "balance_latest", "unit": "WEI", "update_sources": []}],
        },
        "derivations": [],
        "trigger": {
            "evaluation_mode": "periodic",
            "condition_ast": {"op": "lt", "left": "balance_latest", "right": "{{threshold}}"},
            "cron_cadence_seconds": 60,
            "dedupe": {"cooldown_seconds": 60, "key_template": "{{instance_id}}:{{target.key}}"},
            "pruning_hints": {"evm": {"tx_type": "any"}},
        },
        "notification": {"title_template": "t", "body_template": "b"},
        "fallbacks": [],
        "assumptions": [],
        "fingerprint": "sha256:" + "2" * 64,
    }

    with pytest.raises(
        AlertTemplateCompileError,
        match="Unresolved signal reference|Suspicious string operand|Signal column name collision",
    ):
        _compile(tpl)


def test_compile_can_recover_catalog_id_from_text_when_signals_missing() -> None:
    tpl = {
        "schema_version": "alert_template_v2",
        "name": "Recovered Catalog",
        "description": "Uses ducklake.wallet_balance_latest but LLM forgot to define signals.",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [],
        "signals": {"principals": [], "factors": []},
        "derivations": [],
        "trigger": {
            "evaluation_mode": "hybrid",
            "condition_ast": {"op": "gt", "left": "$.signals.balance_latest_signal.balance_latest", "right": 0},
            "cron_cadence_seconds": 0,
            "dedupe": {"cooldown_seconds": 0, "key_template": "{{instance_id}}:{{target.key}}"},
            "pruning_hints": {"evm": {"tx_type": "any"}},
        },
        "notification": {"title_template": "t", "body_template": "b"},
        "fallbacks": [],
        "assumptions": [],
        "fingerprint": "sha256:" + "3" * 64,
    }

    exe = _compile(tpl)
    assert exe["datasources"]
    assert exe["datasources"][0]["catalog_id"] == "ducklake.wallet_balance_latest"
    assert exe["conditions"]["all"][0]["left"] == "$.datasources.ds_ducklake_wallet_balance_latest.balance_latest"


def test_compile_can_infer_catalog_id_from_signals_ref_when_signals_missing() -> None:
    tpl = {
        "schema_version": "alert_template_v2",
        "name": "Inferred Catalog",
        "description": "Alert when wallet has any transactions in the last 24 hours.",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [],
        "signals": {"principals": [], "factors": []},
        "derivations": [],
        "trigger": {
            "evaluation_mode": "hybrid",
            "condition_ast": {"op": "gt", "left": {"ref": "signals.tx_count_24h.tx_count_24h"}, "right": 0},
            "cron_cadence_seconds": 0,
            "dedupe": {"cooldown_seconds": 0, "key_template": "{{instance_id}}:{{target.key}}"},
            "pruning_hints": {"evm": {"tx_type": "any"}},
        },
        "notification": {"title_template": "t", "body_template": "b"},
        "fallbacks": [],
        "assumptions": [],
        "fingerprint": "sha256:" + "4" * 64,
    }

    exe = _compile(tpl)
    catalog_ids = {d.get("catalog_id") for d in exe.get("datasources") or []}
    assert "ducklake.address_transactions_count_24h" in catalog_ids
    assert exe["conditions"]["all"][0]["left"] == "$.datasources.ds_ducklake_address_transactions_count_24h.tx_count_24h"
