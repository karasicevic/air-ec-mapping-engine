from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXECUTION_PLANNING_FIXTURES = ROOT / "tests" / "fixtures" / "execution_planning"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from air_ecmap.execution_planning_core import (  # noqa: E402
    filter_contextual_mras,
    is_rule_applicable,
    order_rules,
    select_rule_for_mra,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _taxonomy_from_runtime(runtime: dict) -> dict:
    keys = list(runtime["source"].keys())
    placeholders = {k: f"{k}.<Any>" for k in keys}
    return {
        "keys": keys,
        "placeholders": placeholders,
        "rules": {"delimiter": ".", "caseSensitive": True},
    }


def _execution_planning_inputs() -> tuple[list[dict], dict, dict]:
    mras = _load_json(
        EXECUTION_PLANNING_FIXTURES / "mapping.mra.Profile.IUC_source.Profile.IUC_target.json"
    )
    table = _load_json(EXECUTION_PLANNING_FIXTURES / "transformationTable.json")
    runtime = _load_json(
        EXECUTION_PLANNING_FIXTURES / "runtimeContext.Profile.IUC_source.Profile.IUC_target.json"
    )
    return mras, table, runtime


def _pick_contextual_mra(mras: list[dict], component_id: str) -> dict:
    return next(
        m for m in mras if m.get("componentId") == component_id and m.get("decision") == "CONTEXTUAL_TRANSFORM"
    )


def _pick_rule(table: dict, component_id: str) -> dict:
    return next(r for r in table["rules"] if r.get("componentId") == component_id)


def test_applicable_rule_matches_runtime_context_on_relevantAxes() -> None:
    mras, table, runtime = _execution_planning_inputs()
    taxonomy = _taxonomy_from_runtime(runtime)
    mra = _pick_contextual_mra(mras, "TaxCategory_BBIE")
    rule = _pick_rule(table, "TaxCategory_BBIE")
    assert is_rule_applicable(rule, mra, runtime, taxonomy)


def test_rule_rejected_if_relevantAxes_mismatch() -> None:
    mras, table, runtime = _execution_planning_inputs()
    taxonomy = _taxonomy_from_runtime(runtime)
    mra = _pick_contextual_mra(mras, "TaxCategory_BBIE")
    rule = deepcopy(_pick_rule(table, "TaxCategory_BBIE"))
    rule["relevantAxes"] = list(rule["relevantAxes"]) + ["IND"]
    assert not is_rule_applicable(rule, mra, runtime, taxonomy)


def test_winner_selection_ordering_is_deterministic() -> None:
    mras, table, runtime = _execution_planning_inputs()
    taxonomy = _taxonomy_from_runtime(runtime)
    mra = _pick_contextual_mra(mras, "TaxCategory_BBIE")
    specific = deepcopy(_pick_rule(table, "TaxCategory_BBIE"))
    specific["ruleId"] = "rule_specific"

    wildcard = deepcopy(specific)
    wildcard["ruleId"] = "rule_wildcard"
    axis = mra["relevantAxes"][0]
    placeholder = taxonomy["placeholders"][axis]
    wildcard["when"]["source"][axis] = placeholder
    wildcard["when"]["target"][axis] = placeholder

    assert is_rule_applicable(specific, mra, runtime, taxonomy)
    assert is_rule_applicable(wildcard, mra, runtime, taxonomy)

    ordered = order_rules([wildcard, specific], mra["relevantAxes"], taxonomy)
    assert [r["ruleId"] for r in ordered] == ["rule_specific", "rule_wildcard"]


def test_unresolved_when_no_applicable_rule() -> None:
    mras, table, runtime = _execution_planning_inputs()
    taxonomy = _taxonomy_from_runtime(runtime)
    mra = _pick_contextual_mra(mras, "TaxCategory_BBIE")
    runtime_bad = deepcopy(runtime)
    runtime_bad["target"]["TAX"] = "TAX.OTHER"
    winner, trace, unresolved = select_rule_for_mra(mra, table["rules"], runtime_bad, taxonomy)
    assert winner is None
    assert unresolved == "no_applicable_rule"
    assert trace["candidateRuleIds"]
    assert trace["applicableRuleIds"] == []
