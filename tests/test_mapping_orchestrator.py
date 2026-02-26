from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from air_ecmap.mapping_orchestrator import run_mapping_pipeline  # noqa: E402


def _profiles() -> dict:
    return {
        "Profile.Source": {
            "ec": {
                "ABIE": {},
                "ASBIE": {},
                "BBIE": {
                    "BBIE.InvoiceID": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
                    "BBIE.TaxCategory": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
                    "BBIE.SourceOnly": [{"Region": "Region.US", "Channel": "Channel.B2B"}],
                },
            },
            "profileSchema": {"profileId": "Profile.Source"},
        },
        "Profile.Target": {
            "ec": {
                "ABIE": {},
                "ASBIE": {},
                "BBIE": {
                    "BBIE.InvoiceID": [{"Region": "Region.EU", "Channel": "Channel.B2C"}],
                    "BBIE.TaxCategory": [{"Region": "Region.US", "Channel": "Channel.B2B"}],
                    "BBIE.TargetOnly": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
                },
            },
            "profileSchema": {"profileId": "Profile.Target"},
        },
    }


def _mapping_config() -> dict:
    return {
        "profilePairs": [{"sourceProfileId": "Profile.Source", "targetProfileId": "Profile.Target"}],
        "bie_catalog": {
            "BBIE.InvoiceID": {"anchor": "InvoiceID_BBIE", "relevantAxes": ["Region"]},
            "BBIE.TaxCategory": {"anchor": "TaxCategory_BBIE", "relevantAxes": ["Region", "Channel"]},
            "BBIE.Unused": {"anchor": "Unused_BBIE"},
        },
        "schemaPaths": {
            "source": {
                "BBIE.InvoiceID": "$.invoice.id",
                "BBIE.TaxCategory": "$.lines[i].tax",
            },
            "target": {
                "BBIE.InvoiceID": "/Invoice/cbc:ID",
                "BBIE.TaxCategory": "/Invoice/cac:TaxTotal",
            },
        },
    }


def test_mapping_orchestrator_emits_mra_and_explanation_artifacts() -> None:
    out = run_mapping_pipeline(_profiles(), _mapping_config())
    assert "error" not in out
    artifacts = out["artifacts"]
    mra_name = "mapping.mra.Profile.Source.Profile.Target.json"
    exp_name = "mapping.explanations.Profile.Source.Profile.Target.json"
    assert mra_name in artifacts
    assert exp_name in artifacts
    mras = artifacts[mra_name]
    exps = artifacts[exp_name]
    assert len(mras) == 2
    assert [m["componentId"] for m in mras] == ["BBIE.InvoiceID", "BBIE.TaxCategory"]
    assert mras[0]["decision"] == "SEAMLESS"
    assert mras[1]["decision"] == "CONTEXTUAL_TRANSFORM"
    assert exps == [m["explanationJson"] for m in mras]


def test_mapping_orchestrator_is_deterministic() -> None:
    out_a = run_mapping_pipeline(_profiles(), _mapping_config())
    out_b = run_mapping_pipeline(_profiles(), _mapping_config())
    assert out_a == out_b


def test_mapping_orchestrator_returns_validation_envelope_on_missing_profile() -> None:
    bad_cfg = _mapping_config()
    bad_cfg["profilePairs"] = [{"sourceProfileId": "Profile.Missing", "targetProfileId": "Profile.Target"}]
    out = run_mapping_pipeline(_profiles(), bad_cfg)
    assert set(out.keys()) == {"error", "reason", "details"}
    assert out["error"] == "Validation"
