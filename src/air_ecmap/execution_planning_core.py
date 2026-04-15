"""Execution Planning core: rule applicability and deterministic winner selection."""

from __future__ import annotations

from typing import Any

from .mapping import project_tuples
from .step3 import _t_intersect


def filter_contextual_mras(mras: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [m for m in mras if m.get("decision") == "CONTEXTUAL_TRANSFORM"]


def candidate_rules(rules: list[dict[str, Any]], component_id: str) -> list[dict[str, Any]]:
    return [r for r in rules if r.get("componentId") == component_id]


def _taxonomy_for_axes(taxonomy: dict[str, Any], axes: list[str]) -> dict[str, Any]:
    return {
        "keys": axes,
        "placeholders": {k: taxonomy["placeholders"][k] for k in axes},
        "rules": taxonomy.get("rules") or {},
    }


def _normalize_rule_token(token: str | None, placeholder: str) -> str:
    if token is None or token == "*" or token == placeholder:
        return placeholder
    return token


def _build_rule_tuple(rule_when: dict[str, str], axes: list[str], placeholders: dict[str, str]) -> dict[str, str]:
    return {axis: _normalize_rule_token(rule_when.get(axis), placeholders[axis]) for axis in axes}


def _build_runtime_tuple(runtime_side: dict[str, str], axes: list[str]) -> dict[str, str]:
    return {axis: runtime_side[axis] for axis in axes}


def _t_intersects(left: dict[str, str], right: dict[str, str], taxonomy: dict[str, Any]) -> bool:
    return len(_t_intersect([left], [right], taxonomy)) > 0


def _axes_match(rule: dict[str, Any], axes: list[str]) -> bool:
    rule_axes = rule.get("relevantAxes")
    if not rule_axes:
        return False
    return set(rule_axes) == set(axes)


def is_rule_applicable(
    rule: dict[str, Any],
    mra: dict[str, Any],
    runtime_context: dict[str, Any],
    taxonomy: dict[str, Any],
    runtime_values: dict[str, Any] | None = None,
) -> bool:
    axes = list(mra.get("relevantAxes") or [])
    if not axes:
        return False
    if not _axes_match(rule, axes):
        return False

    runtime_source = runtime_context.get("source") or {}
    runtime_target = runtime_context.get("target") or {}
    if any(axis not in runtime_source or axis not in runtime_target for axis in axes):
        return False

    sub_taxonomy = _taxonomy_for_axes(taxonomy, axes)
    placeholders = sub_taxonomy["placeholders"]

    rule_when = rule.get("when") or {}
    rule_source = _build_rule_tuple(rule_when.get("source") or {}, axes, placeholders)
    rule_target = _build_rule_tuple(rule_when.get("target") or {}, axes, placeholders)

    runtime_source_tuple = _build_runtime_tuple(runtime_source, axes)
    runtime_target_tuple = _build_runtime_tuple(runtime_target, axes)

    if not _t_intersects(runtime_source_tuple, rule_source, sub_taxonomy):
        return False
    if not _t_intersects(runtime_target_tuple, rule_target, sub_taxonomy):
        return False

    ec_source_rel = project_tuples(mra.get("EC_source", []), axes)
    ec_target_rel = project_tuples(mra.get("EC_target", []), axes)
    if not _t_intersect(ec_source_rel, [rule_source], sub_taxonomy):
        return False
    if not _t_intersect(ec_target_rel, [rule_target], sub_taxonomy):
        return False

    match_source = rule.get("matchSource")
    if match_source is not None:
        if runtime_values is None:
            return False
        input_path = match_source.get("sourcePath") or mra.get("mappingJson", {}).get("source_path")
        if not input_path or input_path not in runtime_values:
            return False
        value = runtime_values.get(input_path)
        kind = match_source.get("kind") or match_source.get("op")
        if kind == "equals" and value != match_source.get("value"):
            return False
        if kind == "in" and value not in (match_source.get("values") or match_source.get("equalsAny") or []):
            return False

    return True


def _is_wildcard(token: str | None, placeholder: str) -> bool:
    return token is None or token == "*" or token == placeholder


def _token_depth(token: str, delimiter: str) -> int:
    return len(token.split(delimiter)) if token else 0


def order_rules(rules: list[dict[str, Any]], axes: list[str], taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    placeholders = taxonomy["placeholders"]
    delimiter = (taxonomy.get("rules") or {}).get("delimiter", ".")

    def score(rule: dict[str, Any]) -> tuple[int, int, int, str]:
        wildcards = 0
        depth_sum = 0
        when = rule.get("when") or {}
        src = when.get("source") or {}
        tgt = when.get("target") or {}
        for axis in axes:
            ph = placeholders[axis]
            tok = src.get(axis)
            if _is_wildcard(tok, ph):
                wildcards += 1
            else:
                depth_sum += _token_depth(tok, delimiter)
            tok = tgt.get(axis)
            if _is_wildcard(tok, ph):
                wildcards += 1
            else:
                depth_sum += _token_depth(tok, delimiter)
        priority = rule.get("priority", 0)
        rule_id = rule.get("ruleId", "")
        return (wildcards, -depth_sum, -priority, rule_id)

    return sorted(rules, key=score)


def select_rule_for_mra(
    mra: dict[str, Any],
    rules: list[dict[str, Any]],
    runtime_context: dict[str, Any],
    taxonomy: dict[str, Any],
    runtime_values: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
    candidates = candidate_rules(rules, mra.get("componentId", ""))
    candidate_ids = [r.get("ruleId") for r in candidates if r.get("ruleId")]

    if not candidates:
        trace = {
            "candidateRuleIds": candidate_ids,
            "applicableRuleIds": [],
            "orderedRuleIds": [],
            "winner": None,
        }
        return None, trace, "no_rules_for_component"

    applicable = [
        r
        for r in candidates
        if is_rule_applicable(r, mra, runtime_context, taxonomy, runtime_values=runtime_values)
    ]
    applicable_ids = [r.get("ruleId") for r in applicable if r.get("ruleId")]

    if not applicable:
        trace = {
            "candidateRuleIds": candidate_ids,
            "applicableRuleIds": [],
            "orderedRuleIds": [],
            "winner": None,
        }
        return None, trace, "no_applicable_rule"

    ordered = order_rules(applicable, list(mra.get("relevantAxes") or []), taxonomy)
    ordered_ids = [r.get("ruleId") for r in ordered if r.get("ruleId")]
    winner = ordered[0]
    trace = {
        "candidateRuleIds": candidate_ids,
        "applicableRuleIds": applicable_ids,
        "orderedRuleIds": ordered_ids,
        "winner": winner.get("ruleId"),
    }
    return winner, trace, None
