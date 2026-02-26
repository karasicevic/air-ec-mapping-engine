from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from air_ecmap.validation import (  # noqa: E402
    ValidationError,
    build_error_envelope,
    normalize_mapping_config,
    validate_ec_inputs,
    validate_assignments,
    validate_component_graph,
    validate_iucs,
    validate_mapping_config,
    validate_policy,
    validate_taxonomy,
)


def _taxonomy() -> dict:
    return {
        "keys": ["Region", "Channel"],
        "placeholders": {
            "Region": "Region.<Any>",
            "Channel": "Channel.<Any>",
        },
        "categories": {
            "Region": ["Region", "Region.EU", "Region.EU.DE"],
            "Channel": ["Channel", "Channel.B2B", "Channel.B2C"],
        },
        "defaults": {"Region": "Region.EU"},
        "rules": {"delimiter": ".", "caseSensitive": True},
    }


def _policy() -> dict:
    return {
        "policyKeys": ["Region", "Channel"],
        "legalTuples": [
            {"Region": "Region.EU", "Channel": "Channel.B2B"},
            {"Region": "Region.<Any>", "Channel": "Channel.B2C"},
        ],
    }


def _component_graph() -> dict:
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
            {
                "id": "ASBIE.Line",
                "sourceABIE": "ABIE.Invoice",
                "targetABIE": "ABIE.Line",
            }
        ],
        "bbies": [
            {"id": "BBIE.InvoiceID", "ownerABIE": "ABIE.Invoice"},
            {"id": "BBIE.LineAmount", "ownerABIE": "ABIE.Line"},
        ],
    }


def _assignments() -> list[dict]:
    return [
        {
            "componentId": "BBIE.InvoiceID",
            "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
        },
        {
            "componentId": "ASBIE.Line",
            "tuples": [{"Region": "Region.EU.DE", "Channel": "Channel.B2C"}],
        },
    ]


def _iucs() -> list[dict]:
    return [
        {
            "id": "Profile.Source",
            "description": "source profile",
            "tuples": [{"Region": "Region.EU", "Channel": "Channel.B2B"}],
            "evaluationRules": {"inheritDefaults": True, "independent": True},
            "trace": {"computedBy": "EC-Algorithm-2.0", "timestamp": "2026-01-01T00:00:00Z"},
        }
    ]


def _mapping_config() -> dict:
    return {
        "profilePairs": [
            {"sourceProfileId": "Profile.Source", "targetProfileId": "Profile.Target"}
        ],
        "bie_catalog": {
            "BBIE.InvoiceID": {"anchor": "InvoiceID_BBIE", "relevantAxes": ["Region"]},
            "BBIE.LineAmount": {"anchor": "LineAmount_BBIE"},
        },
        "schemaPaths": {
            "source": {
                "BBIE.InvoiceID": "$.invoice.id",
                "BBIE.LineAmount": "$.lines[i].amount",
            },
            "target": {
                "BBIE.InvoiceID": "/Invoice/cbc:ID",
                "BBIE.LineAmount": "/Invoice/cac:InvoiceLine[i+1]/cbc:LineExtensionAmount",
            },
        },
    }


def _ec_bundle() -> dict:
    return {
        "taxonomy": _taxonomy(),
        "policy": _policy(),
        "componentGraph": _component_graph(),
        "assignedBusinessContext": _assignments(),
    }


def test_validation_layer_accepts_valid_minimal_inputs() -> None:
    taxonomy = _taxonomy()
    graph = _component_graph()
    validate_taxonomy(taxonomy)
    validate_policy(_policy(), taxonomy)
    validate_component_graph(graph)
    validate_assignments(_assignments(), taxonomy, graph)
    validate_iucs(_iucs(), taxonomy)
    validate_mapping_config(_mapping_config())


def test_taxonomy_rejects_duplicate_keys() -> None:
    taxonomy = _taxonomy()
    taxonomy["keys"] = ["Region", "Region"]
    with pytest.raises(ValidationError, match="taxonomy.keys must be unique"):
        validate_taxonomy(taxonomy)


def test_taxonomy_rejects_non_ancestor_closed_categories() -> None:
    taxonomy = _taxonomy()
    taxonomy["categories"]["Region"] = ["Region.EU.DE"]
    with pytest.raises(ValidationError, match="ancestor-closed"):
        validate_taxonomy(taxonomy)


def test_policy_rejects_key_outside_taxonomy() -> None:
    with pytest.raises(ValidationError, match="policyKeys"):
        validate_policy(
            {"policyKeys": ["Region", "UnknownKey"], "legalTuples": []},
            _taxonomy(),
        )


def test_component_graph_rejects_unresolved_references() -> None:
    graph = _component_graph()
    graph["asbies"][0]["targetABIE"] = "ABIE.Missing"
    with pytest.raises(ValidationError, match="targetABIE"):
        validate_component_graph(graph)


def test_assignments_reject_unknown_component_id() -> None:
    bad = [{"componentId": "BBIE.DoesNotExist", "tuples": []}]
    with pytest.raises(ValidationError, match="componentId"):
        validate_assignments(bad, _taxonomy(), _component_graph())


def test_iucs_reject_tuple_keys_outside_taxonomy() -> None:
    iucs = _iucs()
    iucs[0]["tuples"] = [{"Region": "Region.EU", "NotAKcd": "X"}]
    with pytest.raises(ValidationError, match="taxonomy.keys"):
        validate_iucs(iucs, _taxonomy())


def test_mapping_config_normalizes_missing_relevant_axes_to_empty_list() -> None:
    cfg = _mapping_config()
    norm = normalize_mapping_config(cfg)
    assert norm["bie_catalog"]["BBIE.LineAmount"]["relevantAxes"] == []


def test_error_envelope_shape() -> None:
    env = build_error_envelope("Validation", "bad input", {"section": "taxonomy"})
    assert set(env.keys()) == {"error", "reason", "details"}
    assert env["error"] == "Validation"
    assert env["reason"] == "bad input"
    assert env["details"] == {"section": "taxonomy"}


def test_validate_ec_inputs_returns_none_when_valid() -> None:
    result = validate_ec_inputs(_ec_bundle(), _iucs())
    assert result is None


@pytest.mark.parametrize(
    ("mutate", "section_hint"),
    [
        (lambda b, i: b["taxonomy"].update({"keys": ["Region", "Region"]}), "taxonomy"),
        (lambda b, i: b["policy"].update({"policyKeys": ["Region", "Missing"]}), "policy"),
        (lambda b, i: b["componentGraph"]["asbies"][0].update({"targetABIE": "ABIE.Missing"}), "componentGraph"),
        (lambda b, i: b.update({"assignedBusinessContext": [{"componentId": "BBIE.Missing", "tuples": []}]}), "assignedBusinessContext"),
        (lambda b, i: i[0].update({"tuples": [{"Region": "Region.EU", "UnknownAxis": "X"}]}), "iucs"),
    ],
)
def test_validate_ec_inputs_maps_failures_to_validation_envelope(mutate, section_hint) -> None:
    bundle = _ec_bundle()
    iucs = _iucs()
    mutate(bundle, iucs)
    env = validate_ec_inputs(bundle, iucs)
    assert isinstance(env, dict)
    assert set(env.keys()) == {"error", "reason", "details"}
    assert env["error"] == "Validation"
    assert section_hint in env["reason"]
    assert env["details"]["section"] == section_hint


def test_validate_ec_inputs_envelope_is_deterministic_for_same_invalid_input() -> None:
    bundle = _ec_bundle()
    bundle["taxonomy"]["keys"] = ["Region", "Region"]
    iucs = _iucs()
    env_a = validate_ec_inputs(bundle, iucs)
    env_b = validate_ec_inputs(bundle, iucs)
    assert env_a == env_b
