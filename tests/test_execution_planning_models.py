from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXECUTION_PLANNING_FIXTURES = ROOT / "tests" / "fixtures" / "execution_planning"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from air_ecmap.execution_planning_models import RuntimeContext, TransformTable  # noqa: E402


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_parses_valid_transform_table_from_fixtures_execution_planning() -> None:
    data = _load_json(EXECUTION_PLANNING_FIXTURES / "transformationTable.json")
    model = TransformTable.model_validate(data)
    assert model.version == "TransformTable-1.0"
    assert len(model.rules) > 0


def test_rejects_duplicate_rule_id() -> None:
    data = _load_json(EXECUTION_PLANNING_FIXTURES / "transformationTable.json")
    data["rules"].append(dict(data["rules"][0]))
    with pytest.raises(ValidationError, match="duplicate ruleId"):
        TransformTable.model_validate(data)


def test_parses_runtime_context_minimal() -> None:
    data = _load_json(
        EXECUTION_PLANNING_FIXTURES / "runtimeContext.Profile.IUC_source.Profile.IUC_target.json"
    )
    model = RuntimeContext.model_validate(data)
    assert "source" in model.model_dump()
    assert "target" in model.model_dump()


def test_rejects_invalid_value_expr_shape() -> None:
    data = _load_json(EXECUTION_PLANNING_FIXTURES / "transformationTable.json")
    data["rules"][0]["then"]["writes"][0]["value"] = {"kind": "literal"}
    with pytest.raises(ValidationError):
        TransformTable.model_validate(data)
