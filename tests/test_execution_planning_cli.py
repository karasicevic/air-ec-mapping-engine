from __future__ import annotations

import json
import sys
from pathlib import Path

from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from air_ecmap.cli import app  # noqa: E402


runner = CliRunner()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _taxonomy_from_runtime(runtime: dict) -> dict:
    keys = list(runtime["source"].keys())
    return {
        "keys": keys,
        "placeholders": {k: f"{k}.<Any>" for k in keys},
        "rules": {"delimiter": ".", "caseSensitive": True},
    }


def test_execution_planning_cli_happy_path_writes_outputs(tmp_path: Path) -> None:
    runtime_path = ROOT / "fixtures" / "execution_planning" / "runtimeContext.Profile.IUC_source.Profile.IUC_target.json"
    runtime = _load_json(runtime_path)
    taxonomy = _taxonomy_from_runtime(runtime)

    source_bundle = {"taxonomy": taxonomy}
    target_bundle = {"taxonomy": taxonomy}

    source_path = tmp_path / "source_bundle.json"
    target_path = tmp_path / "target_bundle.json"
    source_path.write_text(json.dumps(source_bundle), encoding="utf-8")
    target_path.write_text(json.dumps(target_bundle), encoding="utf-8")

    mra_path = ROOT / "fixtures" / "execution_planning" / "mapping.mra.Profile.IUC_source.Profile.IUC_target.json"
    table_path = ROOT / "fixtures" / "execution_planning" / "transformationTable.expanded.DE_to_NL_AE0.json"
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "run-execution-planning",
            "--mapping-mra",
            str(mra_path),
            "--source-bundle",
            str(source_path),
            "--target-bundle",
            str(target_path),
            "--transform-table",
            str(table_path),
            "--runtime-context",
            str(runtime_path),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "execution-planning.Profile.IUC_source.Profile.IUC_target.json").exists()
    assert (out_dir / "execution-planning-validation.Profile.IUC_source.Profile.IUC_target.json").exists()


def test_execution_planning_cli_conflict_exits_nonzero(tmp_path: Path) -> None:
    runtime = {"source": {"A": "A.X"}, "target": {"A": "A.Y"}}
    taxonomy = {
        "keys": ["A"],
        "placeholders": {"A": "A.<Any>"},
        "rules": {"delimiter": ".", "caseSensitive": True},
    }

    mapping_mra = [
        {
            "componentId": "C1",
            "decision": "CONTEXTUAL_TRANSFORM",
            "relevantAxes": ["A"],
            "EC_source": [{"A": "A.X"}],
            "EC_target": [{"A": "A.Y"}],
            "mappingJson": {"source_path": "$.x"},
        },
        {
            "componentId": "C2",
            "decision": "CONTEXTUAL_TRANSFORM",
            "relevantAxes": ["A"],
            "EC_source": [{"A": "A.X"}],
            "EC_target": [{"A": "A.Y"}],
            "mappingJson": {"source_path": "$.y"},
        },
    ]

    table = {
        "version": "TransformTable-1.0",
        "rules": [
            {
                "ruleId": "R1",
                "componentId": "C1",
                "relevantAxes": ["A"],
                "when": {"source": {"A": "A.X"}, "target": {"A": "A.Y"}},
                "then": {
                    "writes": [
                        {"targetPath": "/a", "value": {"kind": "literal", "value": 1}}
                    ]
                },
            },
            {
                "ruleId": "R2",
                "componentId": "C2",
                "relevantAxes": ["A"],
                "when": {"source": {"A": "A.X"}, "target": {"A": "A.Y"}},
                "then": {
                    "writes": [
                        {"targetPath": "/a", "value": {"kind": "literal", "value": 2}}
                    ]
                },
            },
        ],
    }

    mra_path = tmp_path / "mapping.mra.Profile.Source.Profile.Target.json"
    source_path = tmp_path / "source_bundle.json"
    target_path = tmp_path / "target_bundle.json"
    table_path = tmp_path / "transform.json"
    runtime_path = tmp_path / "runtime.json"
    out_dir = tmp_path / "out"

    mra_path.write_text(json.dumps(mapping_mra), encoding="utf-8")
    source_path.write_text(json.dumps({"taxonomy": taxonomy}), encoding="utf-8")
    target_path.write_text(json.dumps({"taxonomy": taxonomy}), encoding="utf-8")
    table_path.write_text(json.dumps(table), encoding="utf-8")
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "run-execution-planning",
            "--mapping-mra",
            str(mra_path),
            "--source-bundle",
            str(source_path),
            "--target-bundle",
            str(target_path),
            "--transform-table",
            str(table_path),
            "--runtime-context",
            str(runtime_path),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["error"] == "ExecutionPlanning"
    assert payload["reason"] == "conflicting_writes"


def _bundle_for_pair() -> dict:
    return {
        "taxonomy": {
            "keys": ["Region", "Channel"],
            "placeholders": {"Region": "Region.<Any>", "Channel": "Channel.<Any>"},
            "categories": {
                "Region": ["Region", "Region.EU", "Region.EU.DE", "Region.US"],
                "Channel": ["Channel", "Channel.B2B", "Channel.B2C"],
            },
            "defaults": {"Channel": "Channel.B2B"},
            "rules": {"delimiter": ".", "caseSensitive": True},
        },
        "policy": {
            "policyKeys": ["Region", "Channel"],
            "legalTuples": [
                {"Region": "Region.<Any>", "Channel": "Channel.B2B"},
                {"Region": "Region.EU", "Channel": "Channel.<Any>"},
            ],
        },
        "componentGraph": {
            "rootABIE": "ABIE.Invoice",
            "rules": {"maxFixpointRounds": 8},
            "abies": [
                {"id": "ABIE.Invoice", "childrenBBIE": ["BBIE.InvoiceID"], "childrenASBIE": ["ASBIE.Line"]},
                {"id": "ABIE.Line", "childrenBBIE": ["BBIE.LineAmount"], "childrenASBIE": []},
            ],
            "asbies": [
                {"id": "ASBIE.Line", "sourceABIE": "ABIE.Invoice", "targetABIE": "ABIE.Line"},
            ],
            "bbies": [
                {"id": "BBIE.InvoiceID", "ownerABIE": "ABIE.Invoice"},
                {"id": "BBIE.LineAmount", "ownerABIE": "ABIE.Line"},
            ],
        },
        "assignedBusinessContext": [
            {"componentId": "BBIE.InvoiceID", "tuples": [{"Region": "Region.EU"}]},
            {"componentId": "BBIE.LineAmount", "tuples": [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}]},
            {"componentId": "ASBIE.Line", "tuples": [{"Region": "Region.EU", "Channel": "Channel.<Any>"}]},
        ],
    }


def _iucs_source() -> list[dict]:
    return [{"id": "Profile.Source", "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}]}]


def _iucs_target() -> list[dict]:
    return [{"id": "Profile.Target", "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}]}]


def _mapping_config() -> dict:
    return {
        "profilePairs": [{"sourceProfileId": "Profile.Source", "targetProfileId": "Profile.Target"}],
        "bie_catalog": {
            "BBIE.InvoiceID": {"anchor": "InvoiceID_BBIE", "relevantAxes": ["Region"]},
        },
        "schemaPaths": {
            "source": {"BBIE.InvoiceID": "$.invoice.id"},
            "target": {"BBIE.InvoiceID": "/Invoice/cbc:ID"},
        },
    }


def test_run_all_pair_unchanged_without_execution_planning_flags(tmp_path: Path) -> None:
    bundle_path = tmp_path / "bundle.json"
    source_iucs_path = tmp_path / "iucs_source.json"
    target_iucs_path = tmp_path / "iucs_target.json"
    cfg_path = tmp_path / "mapping_config.json"
    out_dir = tmp_path / "pair_out"

    bundle_path.write_text(json.dumps(_bundle_for_pair()), encoding="utf-8")
    source_iucs_path.write_text(json.dumps(_iucs_source()), encoding="utf-8")
    target_iucs_path.write_text(json.dumps(_iucs_target()), encoding="utf-8")
    cfg_path.write_text(json.dumps(_mapping_config()), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "run-all-pair",
            "--source-bundle",
            str(bundle_path),
            "--target-bundle",
            str(bundle_path),
            "--source-iucs",
            str(source_iucs_path),
            "--target-iucs",
            str(target_iucs_path),
            "--mapping-config",
            str(cfg_path),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    assert list(out_dir.glob("execution-planning.*.json")) == []
    assert list(out_dir.glob("execution-planning-validation.*.json")) == []


def test_run_all_pair_writes_execution_planning_outputs_when_flags_present(tmp_path: Path) -> None:
    bundle_path = tmp_path / "bundle.json"
    source_iucs_path = tmp_path / "iucs_source.json"
    target_iucs_path = tmp_path / "iucs_target.json"
    cfg_path = tmp_path / "mapping_config.json"
    out_dir = tmp_path / "pair_out"

    bundle_path.write_text(json.dumps(_bundle_for_pair()), encoding="utf-8")
    source_iucs_path.write_text(json.dumps(_iucs_source()), encoding="utf-8")
    target_iucs_path.write_text(json.dumps(_iucs_target()), encoding="utf-8")
    cfg_path.write_text(json.dumps(_mapping_config()), encoding="utf-8")

    runtime_path = ROOT / "fixtures" / "execution_planning" / "runtimeContext.Profile.IUC_source.Profile.IUC_target.json"
    table_path = ROOT / "fixtures" / "execution_planning" / "transformationTable.expanded.DE_to_NL_AE0.json"

    result = runner.invoke(
        app,
        [
            "run-all-pair",
            "--source-bundle",
            str(bundle_path),
            "--target-bundle",
            str(bundle_path),
            "--source-iucs",
            str(source_iucs_path),
            "--target-iucs",
            str(target_iucs_path),
            "--mapping-config",
            str(cfg_path),
            "--transform-table",
            str(table_path),
            "--runtime-context",
            str(runtime_path),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "execution-planning.Profile.Source.Profile.Target.json").exists()
    assert (out_dir / "execution-planning-validation.Profile.Source.Profile.Target.json").exists()
