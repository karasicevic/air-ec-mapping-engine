from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from air_ecmap.step2 import run_step2_oc, run_step2_oc_safe  # noqa: E402


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
        "defaults": {},
        "rules": {"delimiter": ".", "caseSensitive": True},
    }


def _acyclic_graph() -> dict:
    return {
        "rootABIE": "ABIE.Invoice",
        "rules": {"maxFixpointRounds": 8},
        "abies": [
            {
                "id": "ABIE.Invoice",
                "childrenBBIE": ["BBIE.InvoiceID"],
                "childrenASBIE": ["ASBIE.Line"],
            },
            {
                "id": "ABIE.Line",
                "childrenBBIE": ["BBIE.LineAmount"],
                "childrenASBIE": [],
            },
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


def _prefiltered() -> list[dict]:
    return [
        {"componentId": "BBIE.InvoiceID", "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}]},
        {"componentId": "BBIE.LineAmount", "tuples": [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}]},
        {"componentId": "ASBIE.Line", "tuples": [{"Region": "Region.EU", "Channel": "Channel.<Any>"}]},
    ]


def test_step2_acyclic_computes_oc_by_mission_formulas() -> None:
    out = run_step2_oc(_prefiltered(), _acyclic_graph(), _taxonomy())
    oc = out["oc"]
    assert oc["BBIE"]["BBIE.InvoiceID"] == [{"Region": "Region.EU", "Channel": "Channel.B2B"}]
    assert oc["BBIE"]["BBIE.LineAmount"] == [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}]
    assert oc["ABIE"]["ABIE.Line"] == [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}]
    assert oc["ASBIE"]["ASBIE.Line"] == [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}]
    assert oc["ABIE"]["ABIE.Invoice"] == [
        {"Region": "Region.EU.DE", "Channel": "Channel.B2B"},
        {"Region": "Region.EU", "Channel": "Channel.B2B"},
    ]


def test_step2_acyclic_is_deterministic() -> None:
    out_a = run_step2_oc(_prefiltered(), _acyclic_graph(), _taxonomy())
    out_b = run_step2_oc(_prefiltered(), _acyclic_graph(), _taxonomy())
    assert out_a == out_b


def test_step2_safe_returns_envelope_for_cycle_path() -> None:
    out = run_step2_oc_safe([], _cyclic_graph(), _taxonomy())
    assert set(out.keys()) == {"error", "reason", "details"}
    assert out["error"] == "Step2"
    assert out["reason"] == "OC_non_convergent_cycle"
