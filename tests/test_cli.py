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


def _bundle() -> dict:
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


def _iucs() -> list[dict]:
    return [
        {"id": "Profile.Source", "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}]},
        {"id": "Profile.Target", "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}]},
    ]


def test_cli_run_ec_writes_normative_artifacts(tmp_path: Path) -> None:
    bundle_path = tmp_path / "bundle.json"
    iucs_path = tmp_path / "iucs.json"
    out_dir = tmp_path / "out"
    bundle_path.write_text(json.dumps(_bundle()), encoding="utf-8")
    iucs_path.write_text(json.dumps(_iucs()), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "run-ec",
            "--bundle",
            str(bundle_path),
            "--iucs",
            str(iucs_path),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    expected = [
        "step1-prefiltered.json",
        "step2-oc.json",
        "step3-ec.Profile.Source.json",
        "step3-ec.Profile.Target.json",
        "step4-profile.Profile.Source.json",
        "step4-profile.Profile.Target.json",
    ]
    for name in expected:
        assert (out_dir / name).exists(), f"Missing artifact: {name}"


def test_cli_run_ec_returns_envelope_on_validation_failure(tmp_path: Path) -> None:
    bad_bundle = _bundle()
    bad_bundle["taxonomy"]["keys"] = ["Region", "Region"]

    bundle_path = tmp_path / "bundle.json"
    iucs_path = tmp_path / "iucs.json"
    out_dir = tmp_path / "out"
    bundle_path.write_text(json.dumps(bad_bundle), encoding="utf-8")
    iucs_path.write_text(json.dumps(_iucs()), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "run-ec",
            "--bundle",
            str(bundle_path),
            "--iucs",
            str(iucs_path),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code != 0
    assert '"error":"Validation"' in result.stdout


def test_cli_run_mapping_writes_mapping_artifacts(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "profiles"
    out_dir = tmp_path / "mapping_out"
    cfg_path = tmp_path / "mapping_config.json"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    (profiles_dir / "step3-ec.Profile.Source.json").write_text(
        json.dumps(
            {
                "ec": {
                    "ABIE": {},
                    "ASBIE": {},
                    "BBIE": {
                        "BBIE.InvoiceID": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (profiles_dir / "step3-ec.Profile.Target.json").write_text(
        json.dumps(
            {
                "ec": {
                    "ABIE": {},
                    "ASBIE": {},
                    "BBIE": {
                        "BBIE.InvoiceID": [{"Region": "Region.EU", "Channel": "Channel.B2C"}],
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (profiles_dir / "step4-profile.Profile.Source.json").write_text(
        json.dumps({"profileId": "Profile.Source", "includes": {"ABIE": [], "ASBIE": [], "BBIE": []}}),
        encoding="utf-8",
    )
    (profiles_dir / "step4-profile.Profile.Target.json").write_text(
        json.dumps({"profileId": "Profile.Target", "includes": {"ABIE": [], "ASBIE": [], "BBIE": []}}),
        encoding="utf-8",
    )

    cfg_path.write_text(
        json.dumps(
            {
                "profilePairs": [{"sourceProfileId": "Profile.Source", "targetProfileId": "Profile.Target"}],
                "bie_catalog": {
                    "BBIE.InvoiceID": {"anchor": "InvoiceID_BBIE", "relevantAxes": ["Region"]},
                },
                "schemaPaths": {
                    "source": {"BBIE.InvoiceID": "$.invoice.id"},
                    "target": {"BBIE.InvoiceID": "/Invoice/cbc:ID"},
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "run-mapping",
            "--profiles-dir",
            str(profiles_dir),
            "--mapping-config",
            str(cfg_path),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0
    assert (out_dir / "mapping.mra.Profile.Source.Profile.Target.json").exists()
    assert (out_dir / "mapping.explanations.Profile.Source.Profile.Target.json").exists()


def test_cli_run_all_writes_ec_and_mapping_artifacts(tmp_path: Path) -> None:
    bundle_path = tmp_path / "bundle.json"
    iucs_path = tmp_path / "iucs.json"
    cfg_path = tmp_path / "mapping_config.json"
    out_dir = tmp_path / "all_out"
    bundle_path.write_text(json.dumps(_bundle()), encoding="utf-8")
    iucs_path.write_text(json.dumps(_iucs()), encoding="utf-8")
    cfg_path.write_text(
        json.dumps(
            {
                "profilePairs": [{"sourceProfileId": "Profile.Source", "targetProfileId": "Profile.Target"}],
                "bie_catalog": {
                    "BBIE.InvoiceID": {"anchor": "InvoiceID_BBIE", "relevantAxes": ["Region"]},
                },
                "schemaPaths": {
                    "source": {"BBIE.InvoiceID": "$.invoice.id"},
                    "target": {"BBIE.InvoiceID": "/Invoice/cbc:ID"},
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "run-all",
            "--bundle",
            str(bundle_path),
            "--iucs",
            str(iucs_path),
            "--mapping-config",
            str(cfg_path),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0
    assert (out_dir / "step1-prefiltered.json").exists()
    assert (out_dir / "step2-oc.json").exists()
    assert (out_dir / "step3-ec.Profile.Source.json").exists()
    assert (out_dir / "step4-profile.Profile.Source.json").exists()
    assert (out_dir / "mapping.mra.Profile.Source.Profile.Target.json").exists()
    assert (out_dir / "mapping.explanations.Profile.Source.Profile.Target.json").exists()


def test_cli_run_all_stops_on_ec_validation_failure(tmp_path: Path) -> None:
    bad_bundle = _bundle()
    bad_bundle["taxonomy"]["keys"] = ["Region", "Region"]
    bundle_path = tmp_path / "bundle.json"
    iucs_path = tmp_path / "iucs.json"
    cfg_path = tmp_path / "mapping_config.json"
    out_dir = tmp_path / "all_out"
    bundle_path.write_text(json.dumps(bad_bundle), encoding="utf-8")
    iucs_path.write_text(json.dumps(_iucs()), encoding="utf-8")
    cfg_path.write_text(
        json.dumps(
            {
                "profilePairs": [{"sourceProfileId": "Profile.Source", "targetProfileId": "Profile.Target"}],
                "bie_catalog": {
                    "BBIE.InvoiceID": {"anchor": "InvoiceID_BBIE", "relevantAxes": ["Region"]},
                },
                "schemaPaths": {
                    "source": {"BBIE.InvoiceID": "$.invoice.id"},
                    "target": {"BBIE.InvoiceID": "/Invoice/cbc:ID"},
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "run-all",
            "--bundle",
            str(bundle_path),
            "--iucs",
            str(iucs_path),
            "--mapping-config",
            str(cfg_path),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code != 0
    assert '"error":"Validation"' in result.stdout
