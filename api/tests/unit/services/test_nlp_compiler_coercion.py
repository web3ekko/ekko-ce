from app.services.nlp import compiler


def test_coerce_legacy_expr_handles_val_and_tx_value() -> None:
    expr = {
        "op": "gt",
        "left": {"op": "tx_value"},
        "right": {
            "op": "mul",
            "left": {"op": "var", "name": "threshold_native"},
            "right": {"op": "val", "value": "1000000000000000000"},
        },
    }

    coerced = compiler._coerce_legacy_expr(expr, {"threshold_native"})

    assert isinstance(coerced, dict)
    assert coerced["op"] == "gt"
    assert coerced["left"] == "$.tx.value"
    assert coerced["right"]["op"] == "mul"
    assert coerced["right"]["left"] == "{{threshold_native}}"
    assert coerced["right"]["right"] == 1000000000000000000
