"""Mission-EC Step 4: Profile Schema generation from EC."""

from __future__ import annotations

from typing import Any

from .validation import validate_component_graph


def run_step4_profile_schema(
    ec: dict[str, Any],
    component_graph: dict[str, Any],
    iuc: dict[str, Any],
) -> dict[str, Any]:
    """Generate Step 4 profile schema for one IUC from EC output."""
    validate_component_graph(component_graph)

    root_abie = component_graph["rootABIE"]
    profile_id = iuc["id"]

    abie_by_id = {x["id"]: x for x in component_graph["abies"]}
    asbie_by_id = {x["id"]: x for x in component_graph["asbies"]}
    bbie_by_id = {x["id"]: x for x in component_graph["bbies"]}

    ec_abie = ec.get("ABIE") or {}
    ec_asbie = ec.get("ASBIE") or {}
    ec_bbie = ec.get("BBIE") or {}

    included_abie_ids = {
        abie_id for abie_id, tuples in ec_abie.items() if isinstance(tuples, list) and len(tuples) > 0
    }
    included_asbie_ids = {
        asbie_id for asbie_id, tuples in ec_asbie.items() if isinstance(tuples, list) and len(tuples) > 0
    }
    included_bbie_ids = {
        bbie_id for bbie_id, tuples in ec_bbie.items() if isinstance(tuples, list) and len(tuples) > 0
    }

    # Closure rule: included ASBIE implies included target ABIE.
    for asbie_id in sorted(included_asbie_ids):
        target_abie = asbie_by_id[asbie_id]["targetABIE"]
        if target_abie in ec_abie and isinstance(ec_abie[target_abie], list) and len(ec_abie[target_abie]) > 0:
            included_abie_ids.add(target_abie)

    # Root realizability is determined by EC(rootABIE) non-empty.
    root_ec = ec_abie.get(root_abie, [])
    is_realizable = isinstance(root_ec, list) and len(root_ec) > 0
    if not is_realizable and root_abie in included_abie_ids:
        included_abie_ids.remove(root_abie)

    includes_abie = [
        {"id": abie_id, "ecTuples": ec_abie[abie_id]}
        for abie_id in sorted(included_abie_ids)
        if abie_id in abie_by_id
    ]
    includes_asbie = [
        {
            "id": asbie_id,
            "ecTuples": ec_asbie[asbie_id],
            "sourceABIE": asbie_by_id[asbie_id]["sourceABIE"],
            "targetABIE": asbie_by_id[asbie_id]["targetABIE"],
        }
        for asbie_id in sorted(included_asbie_ids)
        if asbie_id in asbie_by_id
    ]
    includes_bbie = [
        {
            "id": bbie_id,
            "ownerABIE": bbie_by_id[bbie_id]["ownerABIE"],
            "ecTuples": ec_bbie[bbie_id],
        }
        for bbie_id in sorted(included_bbie_ids)
        if bbie_id in bbie_by_id
    ]

    return {
        "version": "ProfileSchema-1.0",
        "profileId": profile_id,
        "rootABIE": root_abie,
        "includes": {
            "ABIE": includes_abie,
            "ASBIE": includes_asbie,
            "BBIE": includes_bbie,
        },
        "notes": [
            "seed: ancestor-preferred collapse",
            "emission: collapse per component",
            "exact-dedup inside steps",
        ],
        "trace": {"sourceEC": "Step3"},
        "isRealizable": is_realizable,
    }
