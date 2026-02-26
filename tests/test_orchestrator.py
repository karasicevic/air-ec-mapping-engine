from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from air_ecmap.orchestrator import run_ec_pipeline  # noqa: E402


def _taxonomy() -> dict:
    return {
        "keys": ["Region", "Channel"],
        "placeholders": {
            "Region": "Region.<Any>",
            "Channel": "Channel.<Any>",
        },
        "categories": {
            "Region": ["Region", "Region.EU", "Region.EU.DE", "Region.US"],
            "Channel": ["Channel", "Channel.B2B", "Channel.B2C"],
        },
        "defaults": {"Channel": "Channel.B2B"},
        "rules": {"delimiter": ".", "caseSensitive": True},
    }


def _acyclic_graph() -> dict:
    return {
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
    }


def _cyclic_graph() -> dict:
    return {
        "rootABIE": "ABIE.A",
        "rules": {"maxFixpointRounds": 8},
        "abies": [
            {"id": "ABIE.A", "childrenBBIE": [], "childrenASBIE": ["ASBIE.AB"]},
            {"id": "ABIE.B", "childrenBBIE": [], "childrenASBIE": ["ASBIE.BA"]},
        ],
        "asbies": [
            {"id": "ASBIE.AB", "sourceABIE": "ABIE.A", "targetABIE": "ABIE.B"},
            {"id": "ASBIE.BA", "sourceABIE": "ABIE.B", "targetABIE": "ABIE.A"},
        ],
        "bbies": [],
    }


def _policy() -> dict:
    return {
        "policyKeys": ["Region", "Channel"],
        "legalTuples": [
            {"Region": "Region.<Any>", "Channel": "Channel.B2B"},
            {"Region": "Region.EU", "Channel": "Channel.<Any>"},
        ],
    }


def _bundle(graph: dict) -> dict:
    if graph["rootABIE"] == "ABIE.Invoice":
        assignments = [
            {"componentId": "BBIE.InvoiceID", "tuples": [{"Region": "Region.EU"}]},
            {"componentId": "BBIE.LineAmount", "tuples": [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}]},
            {"componentId": "ASBIE.Line", "tuples": [{"Region": "Region.EU", "Channel": "Channel.<Any>"}]},
        ]
    else:
        assignments = [
            {"componentId": "ASBIE.AB", "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}]},
            {"componentId": "ASBIE.BA", "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}]},
        ]
    return {
        "taxonomy": _taxonomy(),
        "policy": _policy(),
        "componentGraph": graph,
        "assignedBusinessContext": assignments,
    }


def _iucs() -> list[dict]:
    return [
        {"id": "Profile.Source", "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}]},
        {"id": "Profile.Target", "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}]},
    ]


def test_orchestrator_happy_path_emits_normative_artifact_names() -> None:
    out = run_ec_pipeline(_bundle(_acyclic_graph()), _iucs())
    assert "error" not in out
    artifacts = out["artifacts"]
    assert "step1-prefiltered.json" in artifacts
    assert "step2-oc.json" in artifacts
    assert "step3-ec.Profile.Source.json" in artifacts
    assert "step3-ec.Profile.Target.json" in artifacts
    assert "step4-profile.Profile.Source.json" in artifacts
    assert "step4-profile.Profile.Target.json" in artifacts


def test_orchestrator_is_deterministic_for_same_inputs() -> None:
    out_a = run_ec_pipeline(_bundle(_acyclic_graph()), _iucs())
    out_b = run_ec_pipeline(_bundle(_acyclic_graph()), _iucs())
    assert out_a == out_b


def test_orchestrator_returns_validation_envelope_and_stops() -> None:
    bad = _bundle(_acyclic_graph())
    bad["taxonomy"]["keys"] = ["Region", "Region"]
    out = run_ec_pipeline(bad, _iucs())
    assert set(out.keys()) == {"error", "reason", "details"}
    assert out["error"] == "Validation"


def test_orchestrator_returns_step2_envelope_on_cycle() -> None:
    out = run_ec_pipeline(_bundle(_cyclic_graph()), _iucs())
    assert set(out.keys()) == {"error", "reason", "details"}
    assert out["error"] == "Step2"
    assert out["reason"] == "OC_non_convergent_cycle"
