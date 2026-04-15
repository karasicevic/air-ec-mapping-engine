from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from air_ecmap.execution_planning_execution import (  # noqa: E402
    build_write_operations,
    dedup_write_operations,
    evaluate_value_expr,
)


def test_literal_write_resolves() -> None:
    plans = [
        {
            "componentId": "C1",
            "selectedRuleId": "R1",
            "writes": [
                {"targetPath": "/a", "value": {"kind": "literal", "value": 5}}
            ],
        }
    ]
    ops, err = build_write_operations(plans, runtime_values=None, code_lists={})
    assert err is None
    assert ops[0]["status"] == "resolved"
    assert ops[0]["value"] == 5


def test_source_value_missing_is_symbolic() -> None:
    plans = [
        {
            "componentId": "C1",
            "selectedRuleId": "R1",
            "writes": [
                {
                    "targetPath": "/a",
                    "value": {"kind": "source_value", "sourcePath": "$.x"},
                }
            ],
        }
    ]
    ops, err = build_write_operations(plans, runtime_values={}, code_lists={})
    assert err is None
    assert ops[0]["status"] == "symbolic"
    assert ops[0]["missingReason"] == "missing_runtime_value"


def test_lookup_missing_source_is_symbolic() -> None:
    value_expr = {
        "kind": "lookup",
        "tableId": "Table1",
        "input": {"kind": "source_value", "sourcePath": "$.missing"},
    }
    status, value, missing = evaluate_value_expr(value_expr, runtime_values={}, code_lists={})
    assert status == "symbolic"
    assert value is None
    assert missing == "missing_runtime_value"


def test_conflicting_resolved_values_same_targetPath_is_error_envelope() -> None:
    plans = [
        {
            "componentId": "C1",
            "selectedRuleId": "R1",
            "writes": [
                {"targetPath": "/a", "value": {"kind": "literal", "value": 1}}
            ],
        },
        {
            "componentId": "C2",
            "selectedRuleId": "R2",
            "writes": [
                {"targetPath": "/a", "value": {"kind": "literal", "value": 2}}
            ],
        },
    ]
    ops, err = build_write_operations(plans, runtime_values=None, code_lists={})
    assert ops == []
    assert err is not None
    assert err["error"] == "ExecutionPlanning"
    assert err["reason"] == "conflicting_writes"


def test_dedup_write_operations_removes_exact_duplicates_in_first_seen_order() -> None:
    first = {
        "componentId": "C1",
        "ruleId": "R1",
        "targetPath": "/a",
        "valueExpr": {"sourcePath": "$.x", "kind": "source_value"},
        "status": "symbolic",
        "missingReason": "missing_runtime_value",
    }
    duplicate_with_different_provenance = {
        **first,
        "componentId": "C2",
        "ruleId": "R2",
    }
    second = {
        "componentId": "C3",
        "ruleId": "R3",
        "targetPath": "/b",
        "valueExpr": {"kind": "literal", "value": 0},
        "status": "resolved",
        "value": 0,
    }

    unique = dedup_write_operations([first, duplicate_with_different_provenance, second])

    assert unique == [first, second]


def test_dedup_write_operations_keeps_same_targetPath_with_different_valueExpr() -> None:
    operations = [
        {
            "componentId": "C1",
            "ruleId": "R1",
            "targetPath": "/a",
            "valueExpr": {"kind": "source_value", "sourcePath": "$.x"},
            "status": "symbolic",
            "missingReason": "missing_runtime_value",
        },
        {
            "componentId": "C2",
            "ruleId": "R2",
            "targetPath": "/a",
            "valueExpr": {"kind": "source_value", "sourcePath": "$.y"},
            "status": "symbolic",
            "missingReason": "missing_runtime_value",
        },
    ]

    assert dedup_write_operations(operations) == operations
