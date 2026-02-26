from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from air_ecmap.step3 import run_step3_ec, run_step3_ec_safe  # noqa: E402


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
            {
                "id": "ABIE.Standalone",
                "childrenBBIE": ["BBIE.Standalone"],
                "childrenASBIE": [],
            },
        ],
        "asbies": [
            {"id": "ASBIE.Line", "sourceABIE": "ABIE.Invoice", "targetABIE": "ABIE.Line"},
        ],
        "bbies": [
            {"id": "BBIE.InvoiceID", "ownerABIE": "ABIE.Invoice"},
            {"id": "BBIE.LineAmount", "ownerABIE": "ABIE.Line"},
            {"id": "BBIE.Standalone", "ownerABIE": "ABIE.Standalone"},
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


def _oc() -> dict:
    return {
        "ABIE": {
            "ABIE.Invoice": [
                {"Region": "Region.EU.DE", "Channel": "Channel.B2B"},
                {"Region": "Region.EU", "Channel": "Channel.B2B"},
            ],
            "ABIE.Line": [
                {"Region": "Region.EU.DE", "Channel": "Channel.B2B"},
            ],
            "ABIE.Standalone": [
                {"Region": "Region.US", "Channel": "Channel.B2C"},
            ],
        },
        "ASBIE": {
            "ASBIE.Line": [
                {"Region": "Region.EU.DE", "Channel": "Channel.B2B"},
            ],
        },
        "BBIE": {
            "BBIE.InvoiceID": [
                {"Region": "Region.EU", "Channel": "Channel.B2B"},
            ],
            "BBIE.LineAmount": [
                {"Region": "Region.EU.DE", "Channel": "Channel.B2B"},
            ],
            "BBIE.Standalone": [
                {"Region": "Region.US", "Channel": "Channel.B2C"},
            ],
        },
    }


def _iuc() -> dict:
    return {
        "id": "Profile.Source",
        "description": "source profile",
        "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
    }


def test_step3_acyclic_computes_ec_with_top_down_propagation() -> None:
    out = run_step3_ec(_oc(), _acyclic_graph(), _taxonomy(), _iuc())
    ec = out["ec"]
    assert ec["ABIE"]["ABIE.Invoice"] == [{"Region": "Region.EU", "Channel": "Channel.B2B"}]
    assert ec["ASBIE"]["ASBIE.Line"] == [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}]
    assert ec["ABIE"]["ABIE.Line"] == [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}]
    assert ec["BBIE"]["BBIE.LineAmount"] == [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}]
    assert ec["BBIE"]["BBIE.InvoiceID"] == [{"Region": "Region.EU", "Channel": "Channel.B2B"}]
    assert ec["ABIE"]["ABIE.Standalone"] == [{"Region": "Region.US", "Channel": "Channel.B2C"}]


def test_step3_acyclic_is_deterministic() -> None:
    out_a = run_step3_ec(_oc(), _acyclic_graph(), _taxonomy(), _iuc())
    out_b = run_step3_ec(_oc(), _acyclic_graph(), _taxonomy(), _iuc())
    assert out_a == out_b


def test_step3_safe_returns_envelope_for_cycle_path() -> None:
    out = run_step3_ec_safe({"ABIE": {}, "ASBIE": {}, "BBIE": {}}, _cyclic_graph(), _taxonomy(), _iuc())
    assert set(out.keys()) == {"error", "reason", "details"}
    assert out["error"] == "Step3"
    assert out["reason"] == "EC_non_convergent_cycle"
