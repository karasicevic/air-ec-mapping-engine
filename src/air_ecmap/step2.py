"""Mission-EC Step 2: Overall Context (OC), acyclic core."""

from __future__ import annotations

from collections import deque
from typing import Any

from .validation import ValidationError, build_error_envelope, validate_component_graph, validate_taxonomy


class CycleDetectedError(RuntimeError):
    """Raised when ABIE dependency graph contains a cycle."""


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


def _intersect_tuple(
    left: dict[str, str],
    right: dict[str, str],
    taxonomy: dict[str, Any],
) -> dict[str, str] | None:
    keys = taxonomy["keys"]
    placeholders = taxonomy["placeholders"]
    rules = taxonomy.get("rules") or {}
    delimiter = rules.get("delimiter", ".")
    case_sensitive = rules.get("caseSensitive", True)
    out: dict[str, str] = {}
    for key in keys:
        tok = _intersect_token(
            left[key],
            right[key],
            placeholder=placeholders[key],
            delimiter=delimiter,
            case_sensitive=case_sensitive,
        )
        if tok is None:
            return None
        out[key] = tok
    return out


def _dedup_exact_ordered(tuples: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    out: list[dict[str, str]] = []
    for tup in tuples:
        key = tuple(tup.items())
        if key not in seen:
            seen.add(key)
            out.append(tup)
    return out


def _t_intersect(
    left_set: list[dict[str, str]],
    right_set: list[dict[str, str]],
    taxonomy: dict[str, Any],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for left in left_set:
        for right in right_set:
            inter = _intersect_tuple(left, right, taxonomy)
            if inter is not None:
                out.append(inter)
    return _dedup_exact_ordered(out)


def _topological_order_or_cycle(component_graph: dict[str, Any]) -> list[str]:
    abie_ids = [x["id"] for x in component_graph["abies"]]
    edges: dict[str, set[str]] = {abie_id: set() for abie_id in abie_ids}
    indeg: dict[str, int] = {abie_id: 0 for abie_id in abie_ids}

    asbie_by_id = {x["id"]: x for x in component_graph["asbies"]}
    for abie in component_graph["abies"]:
        source = abie["id"]
        for asbie_id in abie.get("childrenASBIE", []):
            target = asbie_by_id[asbie_id]["targetABIE"]
            if target not in edges[source]:
                edges[source].add(target)
                indeg[target] += 1

    queue = deque(sorted([n for n in abie_ids if indeg[n] == 0]))
    out: list[str] = []
    while queue:
        node = queue.popleft()
        out.append(node)
        for nxt in sorted(edges[node]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    if len(out) != len(abie_ids):
        raise CycleDetectedError("ABIE dependency graph has a cycle")
    return out


def run_step2_oc(
    prefiltered: list[dict[str, Any]],
    component_graph: dict[str, Any],
    taxonomy: dict[str, Any],
) -> dict[str, Any]:
    """Compute Step 2 OC for acyclic component graphs."""
    validate_taxonomy(taxonomy)
    validate_component_graph(component_graph)

    topo = _topological_order_or_cycle(component_graph)
    reverse_topo = list(reversed(topo))

    prefiltered_map: dict[str, list[dict[str, str]]] = {}
    for entry in prefiltered:
        cid = entry["componentId"]
        tuples = entry.get("tuples", [])
        prefiltered_map.setdefault(cid, [])
        prefiltered_map[cid].extend(tuples)
    for cid, tuples in list(prefiltered_map.items()):
        prefiltered_map[cid] = _dedup_exact_ordered(tuples)

    asbie_by_id = {x["id"]: x for x in component_graph["asbies"]}
    bbie_by_id = {x["id"]: x for x in component_graph["bbies"]}
    abie_by_id = {x["id"]: x for x in component_graph["abies"]}

    oc_bbie: dict[str, list[dict[str, str]]] = {
        bbie_id: prefiltered_map.get(bbie_id, [])
        for bbie_id in sorted(bbie_by_id.keys())
    }
    oc_asbie: dict[str, list[dict[str, str]]] = {}
    oc_abie: dict[str, list[dict[str, str]]] = {}

    for abie_id in reverse_topo:
        abie = abie_by_id[abie_id]
        for asbie_id in sorted(abie.get("childrenASBIE", [])):
            pref_l = prefiltered_map.get(asbie_id, [])
            target_abie = asbie_by_id[asbie_id]["targetABIE"]
            oc_target = oc_abie[target_abie]
            oc_asbie[asbie_id] = _t_intersect(pref_l, oc_target, taxonomy)

        child_sets: list[dict[str, str]] = []
        for asbie_id in sorted(abie.get("childrenASBIE", [])):
            child_sets.extend(oc_asbie.get(asbie_id, []))
        for bbie_id in sorted(abie.get("childrenBBIE", [])):
            child_sets.extend(oc_bbie.get(bbie_id, []))
        oc_abie[abie_id] = _dedup_exact_ordered(child_sets)

    return {
        "oc": {
            "ABIE": {k: oc_abie[k] for k in sorted(oc_abie.keys())},
            "ASBIE": {k: oc_asbie.get(k, []) for k in sorted(asbie_by_id.keys())},
            "BBIE": {k: oc_bbie.get(k, []) for k in sorted(bbie_by_id.keys())},
        }
    }


def run_step2_oc_safe(
    prefiltered: list[dict[str, Any]],
    component_graph: dict[str, Any],
    taxonomy: dict[str, Any],
) -> dict[str, Any]:
    """Run Step 2 and return Mission-EC §7 Step2 envelope on failures."""
    try:
        return run_step2_oc(prefiltered, component_graph, taxonomy)
    except CycleDetectedError:
        return build_error_envelope("Step2", "OC_non_convergent_cycle", {"stage": "cycle"})
    except ValidationError as exc:
        return build_error_envelope("Step2", str(exc), {"stage": "validation"})
    except KeyError as exc:
        return build_error_envelope("Step2", f"missing required field: {exc.args[0]}", {"stage": "runtime"})
    except Exception as exc:  # pragma: no cover
        return build_error_envelope("Step2", f"{exc.__class__.__name__}: {exc}", {"stage": "runtime"})
