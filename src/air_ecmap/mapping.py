"""Mapping-phase core logic (KCD projection + classification + MRA shaping)."""

from __future__ import annotations

from typing import Any


def _dedup_exact_ordered(tuples: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    out: list[dict[str, str]] = []
    for tup in tuples:
        key = tuple(tup.items())
        if key not in seen:
            seen.add(key)
            out.append(tup)
    return out


def project_tuples(tuples: list[dict[str, str]], axes: list[str]) -> list[dict[str, str]]:
    projected = [{k: t[k] for k in axes if k in t} for t in tuples]
    return _dedup_exact_ordered(projected)


def intersect_projected(left: list[dict[str, str]], right: list[dict[str, str]]) -> list[dict[str, str]]:
    right_keys = {tuple(x.items()) for x in right}
    out = [x for x in left if tuple(x.items()) in right_keys]
    return _dedup_exact_ordered(out)


def classify_component(
    ec_source_full: list[dict[str, str]],
    ec_target_full: list[dict[str, str]],
    kcd_axes: list[str],
) -> tuple[str, list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    ec_source_rel = project_tuples(ec_source_full, kcd_axes)
    ec_target_rel = project_tuples(ec_target_full, kcd_axes)
    if len(ec_source_rel) == 0 or len(ec_target_rel) == 0:
        return "NO_MAPPING", ec_source_rel, ec_target_rel, []
    ec_common = intersect_projected(ec_source_rel, ec_target_rel)
    if len(ec_common) > 0:
        return "SEAMLESS", ec_source_rel, ec_target_rel, ec_common
    return "CONTEXTUAL_TRANSFORM", ec_source_rel, ec_target_rel, ec_common


def build_mra(
    component_id: str,
    anchor: str,
    relevant_axes: list[str],
    decision: str,
    ec_source_full: list[dict[str, str]],
    ec_target_full: list[dict[str, str]],
    ec_common_on_kcd: list[dict[str, str]],
    source_path: str,
    target_path: str,
) -> dict[str, Any]:
    mapping_json = {
        "componentId": component_id,
        "sourcePath": source_path,
        "targetPath": target_path,
        "decision": decision,
        "transform": "identity_or_direct" if decision == "SEAMLESS" else "contextual_transform",
    }
    explanation_json = {
        "componentId": component_id,
        "tldr": f"{decision} based on KCD comparison",
        "relevantAxes": relevant_axes,
        "decision": decision,
    }
    return {
        "componentId": component_id,
        "anchor": anchor,
        "relevantAxes": relevant_axes,
        "decision": decision,
        "EC_source": ec_source_full,
        "EC_target": ec_target_full,
        "EC_common_on_KCD": ec_common_on_kcd,
        "mappingJson": mapping_json,
        "explanationJson": explanation_json,
    }
