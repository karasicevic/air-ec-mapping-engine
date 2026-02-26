from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from air_ecmap.step4 import run_step4_profile_schema  # noqa: E402


def _graph() -> dict:
    return {
        "rootABIE": "ABIE.Invoice",
        "rules": {"maxFixpointRounds": 8},
        "abies": [
            {"id": "ABIE.Invoice", "childrenBBIE": ["BBIE.InvoiceID"], "childrenASBIE": ["ASBIE.Line"]},
            {"id": "ABIE.Line", "childrenBBIE": ["BBIE.LineAmount"], "childrenASBIE": []},
            {"id": "ABIE.Empty", "childrenBBIE": [], "childrenASBIE": []},
        ],
        "asbies": [
            {"id": "ASBIE.Line", "sourceABIE": "ABIE.Invoice", "targetABIE": "ABIE.Line"},
            {"id": "ASBIE.Unused", "sourceABIE": "ABIE.Invoice", "targetABIE": "ABIE.Empty"},
        ],
        "bbies": [
            {"id": "BBIE.InvoiceID", "ownerABIE": "ABIE.Invoice"},
            {"id": "BBIE.LineAmount", "ownerABIE": "ABIE.Line"},
            {"id": "BBIE.Unused", "ownerABIE": "ABIE.Empty"},
        ],
    }


def _iuc() -> dict:
    return {"id": "Profile.Source", "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}]}


def test_step4_emits_only_components_with_non_empty_ec_and_expected_shape() -> None:
    ec = {
        "ABIE": {
            "ABIE.Invoice": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
            "ABIE.Line": [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}],
            "ABIE.Empty": [],
        },
        "ASBIE": {
            "ASBIE.Line": [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}],
            "ASBIE.Unused": [],
        },
        "BBIE": {
            "BBIE.InvoiceID": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
            "BBIE.LineAmount": [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}],
            "BBIE.Unused": [],
        },
    }
    out = run_step4_profile_schema(ec, _graph(), _iuc())
    assert out["version"] == "ProfileSchema-1.0"
    assert out["profileId"] == "Profile.Source"
    assert out["rootABIE"] == "ABIE.Invoice"
    assert [x["id"] for x in out["includes"]["ABIE"]] == ["ABIE.Invoice", "ABIE.Line"]
    assert [x["id"] for x in out["includes"]["ASBIE"]] == ["ASBIE.Line"]
    assert [x["id"] for x in out["includes"]["BBIE"]] == ["BBIE.InvoiceID", "BBIE.LineAmount"]
    assert out["trace"] == {"sourceEC": "Step3"}


def test_step4_root_realizability_rule() -> None:
    ec = {"ABIE": {"ABIE.Invoice": []}, "ASBIE": {}, "BBIE": {}}
    out = run_step4_profile_schema(ec, _graph(), _iuc())
    assert out["isRealizable"] is False
    assert all(entry["id"] != "ABIE.Invoice" for entry in out["includes"]["ABIE"])


def test_step4_asbie_target_closure_rule() -> None:
    ec = {
        "ABIE": {
            "ABIE.Invoice": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
            "ABIE.Line": [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}],
        },
        "ASBIE": {"ASBIE.Line": [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}]},
        "BBIE": {},
    }
    out = run_step4_profile_schema(ec, _graph(), _iuc())
    abie_ids = [x["id"] for x in out["includes"]["ABIE"]]
    assert "ABIE.Line" in abie_ids


def test_step4_deterministic_ordering() -> None:
    ec = {
        "ABIE": {
            "ABIE.Line": [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}],
            "ABIE.Invoice": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
        },
        "ASBIE": {"ASBIE.Line": [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}]},
        "BBIE": {
            "BBIE.LineAmount": [{"Region": "Region.EU.DE", "Channel": "Channel.B2B"}],
            "BBIE.InvoiceID": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
        },
    }
    out_a = run_step4_profile_schema(ec, _graph(), _iuc())
    out_b = run_step4_profile_schema(ec, _graph(), _iuc())
    assert out_a == out_b
    assert [x["id"] for x in out_a["includes"]["ABIE"]] == ["ABIE.Invoice", "ABIE.Line"]
    assert [x["id"] for x in out_a["includes"]["BBIE"]] == ["BBIE.InvoiceID", "BBIE.LineAmount"]
