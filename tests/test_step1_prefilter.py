from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from air_ecmap.step1 import run_step1_prefilter, run_step1_prefilter_safe  # noqa: E402


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


def test_step1_keeps_multi_witness_with_defaults_and_dedup() -> None:
    assignments = [
        {"componentId": "BBIE.InvoiceID", "tuples": [{"Region": "Region.EU"}]},
    ]
    policy = {
        "policyKeys": ["Region", "Channel"],
        "legalTuples": [
            {"Region": "Region.<Any>", "Channel": "Channel.B2B"},
            {"Region": "Region.EU", "Channel": "Channel.<Any>"},
        ],
    }

    out = run_step1_prefilter(assignments, policy, _taxonomy())
    assert len(out["prefiltered"]) == 1
    assert out["prefiltered"][0]["componentId"] == "BBIE.InvoiceID"
    assert out["prefiltered"][0]["tuples"] == [{"Region": "Region.EU", "Channel": "Channel.B2B"}]
    log = out["log"][0]
    assert log["action"] == "kept-multi"
    assert log["witnesses"] == [0, 1]
    assert log["fills"] == {"Channel": "Channel.B2B"}
    assert list(out["prefiltered"][0]["tuples"][0].keys()) == ["Region", "Channel"]


def test_step1_drops_when_no_legal_match() -> None:
    assignments = [
        {"componentId": "BBIE.InvoiceID", "tuples": [{"Region": "Region.US", "Channel": "Channel.B2C"}]},
    ]
    policy = {
        "policyKeys": ["Region", "Channel"],
        "legalTuples": [
            {"Region": "Region.EU", "Channel": "Channel.B2B"},
        ],
    }
    out = run_step1_prefilter(assignments, policy, _taxonomy())
    assert out["prefiltered"] == []
    assert out["log"][0]["action"] == "dropped"
    assert out["log"][0]["reason"] == "no-legal-match"
    assert out["log"][0]["witnesses"] == []
    assert out["log"][0]["tuplesAfter"] == []


def test_step1_whole_tuple_matching_on_policy_keys() -> None:
    assignments = [
        {"componentId": "BBIE.InvoiceID", "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2C"}]},
    ]
    policy = {
        "policyKeys": ["Region", "Channel"],
        "legalTuples": [
            {"Region": "Region.EU", "Channel": "Channel.B2B"},
            {"Region": "Region.<Any>", "Channel": "Channel.B2C"},
        ],
    }
    out = run_step1_prefilter(assignments, policy, _taxonomy())
    assert out["log"][0]["witnesses"] == [1]
    assert out["prefiltered"][0]["tuples"] == [{"Region": "Region.EU", "Channel": "Channel.B2C"}]


def test_step1_is_deterministic_for_same_input() -> None:
    assignments = [
        {
            "componentId": "ASBIE.Line",
            "tuples": [
                {"Region": "Region.EU.DE"},
                {"Region": "Region.US", "Channel": "Channel.B2C"},
            ],
        }
    ]
    policy = {
        "policyKeys": ["Region", "Channel"],
        "legalTuples": [
            {"Region": "Region.EU", "Channel": "Channel.<Any>"},
            {"Region": "Region.<Any>", "Channel": "Channel.B2C"},
        ],
    }
    tax = _taxonomy()
    out_a = run_step1_prefilter(assignments, policy, tax)
    out_b = run_step1_prefilter(assignments, policy, tax)
    assert out_a == out_b


def test_step1_safe_wrapper_returns_normal_output_when_valid() -> None:
    assignments = [
        {"componentId": "BBIE.InvoiceID", "tuples": [{"Region": "Region.EU"}]},
    ]
    policy = {
        "policyKeys": ["Region", "Channel"],
        "legalTuples": [
            {"Region": "Region.<Any>", "Channel": "Channel.B2B"},
        ],
    }
    result = run_step1_prefilter_safe(assignments, policy, _taxonomy())
    assert "error" not in result
    assert "prefiltered" in result
    assert "log" in result


def test_step1_safe_wrapper_returns_step1_envelope_on_failure() -> None:
    assignments = [{"tuples": [{"Region": "Region.EU"}]}]  # componentId missing
    policy = {
        "policyKeys": ["Region", "Channel"],
        "legalTuples": [{"Region": "Region.<Any>", "Channel": "Channel.B2B"}],
    }
    result = run_step1_prefilter_safe(assignments, policy, _taxonomy())
    assert set(result.keys()) == {"error", "reason", "details"}
    assert result["error"] == "Step1"
    assert "componentId" in result["reason"]


def test_step1_safe_wrapper_failure_is_deterministic() -> None:
    assignments = [{"tuples": [{"Region": "Region.EU"}]}]  # componentId missing
    policy = {
        "policyKeys": ["Region", "Channel"],
        "legalTuples": [{"Region": "Region.<Any>", "Channel": "Channel.B2B"}],
    }
    tax = _taxonomy()
    out_a = run_step1_prefilter_safe(assignments, policy, tax)
    out_b = run_step1_prefilter_safe(assignments, policy, tax)
    assert out_a == out_b
