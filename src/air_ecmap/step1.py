"""Mission-EC Step 1: policy filtering (multi-witness)."""

from __future__ import annotations

from typing import Any

from .validation import ValidationError, build_error_envelope, validate_policy, validate_taxonomy


def _norm(token: str, case_sensitive: bool) -> str:
    return token if case_sensitive else token.lower()


def _is_ancestor(ancestor: str, descendant: str, delimiter: str, case_sensitive: bool) -> bool:
    a = _norm(ancestor, case_sensitive)
    d = _norm(descendant, case_sensitive)
    return d == a or d.startswith(f"{a}{delimiter}")


def _intersect_token(
    left: str,
    right: str,
    *,
    placeholder: str,
    delimiter: str,
    case_sensitive: bool,
) -> str | None:
    if _norm(left, case_sensitive) == _norm(placeholder, case_sensitive):
        return right
    if _norm(right, case_sensitive) == _norm(placeholder, case_sensitive):
        return left
    if _norm(left, case_sensitive) == _norm(right, case_sensitive):
        return left
    if _is_ancestor(left, right, delimiter, case_sensitive):
        return right
    if _is_ancestor(right, left, delimiter, case_sensitive):
        return left
    return None


def _dedup_exact_ordered(tuples: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    out: list[dict[str, str]] = []
    for tup in tuples:
        key = tuple(tup.items())
        if key not in seen:
            seen.add(key)
            out.append(tup)
    return out


def _normalize_tuple(
    tuple_before: dict[str, Any],
    taxonomy: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str], str | None]:
    keys = taxonomy["keys"]
    defaults = taxonomy.get("defaults") or {}
    normalized: dict[str, str] = {}
    fills: dict[str, str] = {}
    for key in keys:
        if key in tuple_before:
            value = tuple_before[key]
            if not isinstance(value, str):
                return {}, {}, f"invalid-token-type:{key}"
            normalized[key] = value
        elif key in defaults:
            normalized[key] = defaults[key]
            fills[key] = defaults[key]
        else:
            return {}, {}, f"missing-key-no-default:{key}"
    return normalized, fills, None


def _intersect_tuple(
    normalized_tuple: dict[str, str],
    legal_tuple: dict[str, str],
    taxonomy: dict[str, Any],
) -> dict[str, str] | None:
    keys = taxonomy["keys"]
    placeholders = taxonomy["placeholders"]
    rules = taxonomy.get("rules") or {}
    delimiter = rules.get("delimiter", ".")
    case_sensitive = rules.get("caseSensitive", True)
    out: dict[str, str] = {}

    for key in keys:
        left = normalized_tuple[key]
        right = legal_tuple.get(key, left)
        intersected = _intersect_token(
            left,
            right,
            placeholder=placeholders[key],
            delimiter=delimiter,
            case_sensitive=case_sensitive,
        )
        if intersected is None:
            return None
        out[key] = intersected
    return out


def run_step1_prefilter(
    assignments: list[dict[str, Any]],
    policy: dict[str, Any],
    taxonomy: dict[str, Any],
) -> dict[str, Any]:
    """Run Step 1 and return deterministic prefiltered tuples + log."""
    validate_taxonomy(taxonomy)
    validate_policy(policy, taxonomy)

    policy_keys = policy["policyKeys"]
    legal_tuples = policy["legalTuples"]
    prefiltered_by_component: dict[str, list[dict[str, str]]] = {}
    component_order: list[str] = []
    logs: list[dict[str, Any]] = []

    for component_entry in assignments:
        component_id = component_entry["componentId"]
        tuples = component_entry.get("tuples", [])
        if component_id not in prefiltered_by_component:
            prefiltered_by_component[component_id] = []
            component_order.append(component_id)

        for tuple_index, tuple_before in enumerate(tuples):
            normalized, fills, normalize_error = _normalize_tuple(tuple_before, taxonomy)
            if normalize_error is not None:
                logs.append(
                    {
                        "componentId": component_id,
                        "tupleIndex": tuple_index,
                        "action": "dropped",
                        "fills": fills,
                        "witnesses": [],
                        "tupleBefore": tuple_before,
                        "tuplesAfter": [],
                        "reason": normalize_error,
                    }
                )
                continue

            witnesses: list[int] = []
            narrowed: list[dict[str, str]] = []
            for witness_index, legal_tuple in enumerate(legal_tuples):
                matched = True
                for key in policy_keys:
                    intersected = _intersect_token(
                        normalized[key],
                        legal_tuple[key],
                        placeholder=taxonomy["placeholders"][key],
                        delimiter=(taxonomy.get("rules") or {}).get("delimiter", "."),
                        case_sensitive=(taxonomy.get("rules") or {}).get("caseSensitive", True),
                    )
                    if intersected is None:
                        matched = False
                        break
                if not matched:
                    continue
                narrowed_tuple = _intersect_tuple(normalized, legal_tuple, taxonomy)
                if narrowed_tuple is None:
                    continue
                witnesses.append(witness_index)
                narrowed.append(narrowed_tuple)

            narrowed = _dedup_exact_ordered(narrowed)
            if not narrowed:
                logs.append(
                    {
                        "componentId": component_id,
                        "tupleIndex": tuple_index,
                        "action": "dropped",
                        "fills": fills,
                        "witnesses": [],
                        "tupleBefore": tuple_before,
                        "tuplesAfter": [],
                        "reason": "no-legal-match",
                    }
                )
                continue

            prefiltered_by_component[component_id].extend(narrowed)
            logs.append(
                {
                    "componentId": component_id,
                    "tupleIndex": tuple_index,
                    "action": "kept-multi",
                    "fills": fills,
                    "witnesses": witnesses,
                    "tupleBefore": tuple_before,
                    "tuplesAfter": narrowed,
                }
            )

    prefiltered_list: list[dict[str, Any]] = []
    for component_id in component_order:
        deduped = _dedup_exact_ordered(prefiltered_by_component[component_id])
        if deduped:
            prefiltered_list.append({"componentId": component_id, "tuples": deduped})

    return {"prefiltered": prefiltered_list, "log": logs}


def run_step1_prefilter_safe(
    assignments: list[dict[str, Any]],
    policy: dict[str, Any],
    taxonomy: dict[str, Any],
) -> dict[str, Any]:
    """Run Step 1 and return Mission-EC §7 Step1 envelope on failures."""
    try:
        return run_step1_prefilter(assignments, policy, taxonomy)
    except ValidationError as exc:
        return build_error_envelope("Step1", str(exc), {"stage": "validation"})
    except KeyError as exc:
        return build_error_envelope("Step1", f"missing required field: {exc.args[0]}", {"stage": "runtime"})
    except Exception as exc:  # pragma: no cover - defensive envelope guarantee
        return build_error_envelope("Step1", f"{exc.__class__.__name__}: {exc}", {"stage": "runtime"})
