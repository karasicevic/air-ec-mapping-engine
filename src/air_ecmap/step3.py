"""Mission-EC Step 3: Effective Context (EC), acyclic core."""

from __future__ import annotations

from collections import deque
from typing import Any

from .validation import (
    ValidationError,
    build_error_envelope,
    validate_component_graph,
    validate_iucs,
    validate_taxonomy,
)


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


def _is_descendant_on_all_keys(
    maybe_descendant: dict[str, str],
    maybe_ancestor: dict[str, str],
    taxonomy: dict[str, Any],
) -> bool:
    rules = taxonomy.get("rules") or {}
    delimiter = rules.get("delimiter", ".")
    case_sensitive = rules.get("caseSensitive", True)
    strict = False
    for key in taxonomy["keys"]:
        anc = maybe_ancestor[key]
        desc = maybe_descendant[key]
        if not _is_ancestor(anc, desc, delimiter, case_sensitive):
            return False
        if _norm(anc, case_sensitive) != _norm(desc, case_sensitive):
            strict = True
    return strict


def _collapse_ancestor_preferred(tuples: list[dict[str, str]], taxonomy: dict[str, Any]) -> list[dict[str, str]]:
    deduped = _dedup_exact_ordered(tuples)
    out: list[dict[str, str]] = []
    for candidate in deduped:
        drop = False
        for other in deduped:
            if candidate is other:
                continue
            if _is_descendant_on_all_keys(candidate, other, taxonomy):
                drop = True
                break
        if not drop:
            out.append(candidate)
    return out


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


def run_step3_ec(
    oc: dict[str, Any],
    component_graph: dict[str, Any],
    taxonomy: dict[str, Any],
    iuc: dict[str, Any],
) -> dict[str, Any]:
    """Compute Step 3 EC for acyclic component graphs."""
    validate_taxonomy(taxonomy)
    validate_component_graph(component_graph)
    validate_iucs([iuc], taxonomy)

    topo = _topological_order_or_cycle(component_graph)
    root = component_graph["rootABIE"]

    oc_abie = dict(oc.get("ABIE") or {})
    oc_asbie = dict(oc.get("ASBIE") or {})
    oc_bbie = dict(oc.get("BBIE") or {})

    asbie_by_id = {x["id"]: x for x in component_graph["asbies"]}
    bbie_by_id = {x["id"]: x for x in component_graph["bbies"]}
    abie_by_id = {x["id"]: x for x in component_graph["abies"]}

    incoming: dict[str, list[str]] = {abie_id: [] for abie_id in abie_by_id}
    for asbie_id, asbie in asbie_by_id.items():
        incoming[asbie["targetABIE"]].append(asbie_id)
    for k in incoming:
        incoming[k] = sorted(incoming[k])

    profile_tuples = _dedup_exact_ordered(iuc["tuples"])
    seed = _t_intersect(oc_abie.get(root, []), profile_tuples, taxonomy)
    seed = _collapse_ancestor_preferred(seed, taxonomy)

    ec_abie: dict[str, list[dict[str, str]]] = {k: [] for k in abie_by_id}
    ec_asbie: dict[str, list[dict[str, str]]] = {k: [] for k in asbie_by_id}
    ec_bbie: dict[str, list[dict[str, str]]] = {k: [] for k in bbie_by_id}

    for abie_id in topo:
        if abie_id == root:
            gate = seed
        elif incoming[abie_id]:
            gate_union: list[dict[str, str]] = []
            for link_id in incoming[abie_id]:
                gate_union.extend(ec_asbie.get(link_id, []))
            gate = _dedup_exact_ordered(gate_union)
        else:
            gate = oc_abie.get(abie_id, [])

        ec_abie[abie_id] = _t_intersect(oc_abie.get(abie_id, []), gate, taxonomy)

        abie = abie_by_id[abie_id]
        for bbie_id in sorted(abie.get("childrenBBIE", [])):
            ec_bbie[bbie_id] = _t_intersect(oc_bbie.get(bbie_id, []), ec_abie[abie_id], taxonomy)
        for asbie_id in sorted(abie.get("childrenASBIE", [])):
            ec_asbie[asbie_id] = _t_intersect(oc_asbie.get(asbie_id, []), ec_abie[abie_id], taxonomy)

    for abie_id in list(ec_abie.keys()):
        ec_abie[abie_id] = _collapse_ancestor_preferred(ec_abie[abie_id], taxonomy)
    for asbie_id in list(ec_asbie.keys()):
        ec_asbie[asbie_id] = _collapse_ancestor_preferred(ec_asbie[asbie_id], taxonomy)
    for bbie_id in list(ec_bbie.keys()):
        ec_bbie[bbie_id] = _collapse_ancestor_preferred(ec_bbie[bbie_id], taxonomy)

    return {
        "ec": {
            "ABIE": {k: ec_abie[k] for k in sorted(ec_abie)},
            "ASBIE": {k: ec_asbie[k] for k in sorted(ec_asbie)},
            "BBIE": {k: ec_bbie[k] for k in sorted(ec_bbie)},
        }
    }


def run_step3_ec_safe(
    oc: dict[str, Any],
    component_graph: dict[str, Any],
    taxonomy: dict[str, Any],
    iuc: dict[str, Any],
) -> dict[str, Any]:
    """Run Step 3 and return Mission-EC §7 Step3 envelope on failures."""
    try:
        return run_step3_ec(oc, component_graph, taxonomy, iuc)
    except CycleDetectedError:
        return build_error_envelope("Step3", "EC_non_convergent_cycle", {"stage": "cycle"})
    except ValidationError as exc:
        return build_error_envelope("Step3", str(exc), {"stage": "validation"})
    except KeyError as exc:
        return build_error_envelope("Step3", f"missing required field: {exc.args[0]}", {"stage": "runtime"})
    except Exception as exc:  # pragma: no cover
        return build_error_envelope("Step3", f"{exc.__class__.__name__}: {exc}", {"stage": "runtime"})
