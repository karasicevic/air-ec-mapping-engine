"""Execution Planning orchestrator: contextual-only execution planning."""

from __future__ import annotations

from typing import Any

from .execution_planning_core import filter_contextual_mras, select_rule_for_mra
from .execution_planning_execution import build_write_operations
from .validation import build_error_envelope


def infer_profile_ids(mapping_mra_filename: str, mras: list[dict[str, Any]]) -> tuple[str, str]:
    name = mapping_mra_filename
    if name.startswith("mapping.mra.") and name.endswith(".json"):
        core = name[len("mapping.mra.") : -len(".json")]
        if ".Profile." in core:
            left, right = core.split(".Profile.", 1)
            return left, f"Profile.{right}"
        if "." in core:
            parts = core.split(".")
            mid = len(parts) // 2
            return ".".join(parts[:mid]), ".".join(parts[mid:])
    for mra in mras:
        mapping_id = (mra.get("mappingJson") or {}).get("id")
        component_id = mra.get("componentId")
        if not mapping_id or not component_id:
            continue
        prefix = "map."
        suffix = f".{component_id}"
        if mapping_id.startswith(prefix) and mapping_id.endswith(suffix):
            inner = mapping_id[len(prefix) : -len(suffix)]
            if ".Profile." in inner:
                left, right = inner.split(".Profile.", 1)
                return left, f"Profile.{right}"
    return "", ""


def _extract_taxonomy(source_bundle: dict[str, Any], target_bundle: dict[str, Any]) -> dict[str, Any] | None:
    return source_bundle.get("taxonomy") or target_bundle.get("taxonomy")


def _taxonomy_missing_keys(taxonomy: dict[str, Any], axes: list[str]) -> list[str]:
    keys = set(taxonomy.get("keys") or [])
    return [axis for axis in axes if axis not in keys]


def run_execution_planning(
    mapping_mras: list[dict[str, Any]],
    source_bundle: dict[str, Any],
    target_bundle: dict[str, Any],
    transform_table: dict[str, Any],
    runtime_context: dict[str, Any],
    mapping_mra_filename: str = "",
) -> dict[str, Any]:
    taxonomy = _extract_taxonomy(source_bundle, target_bundle)
    if not isinstance(taxonomy, dict):
        return build_error_envelope("ExecutionPlanning", "missing_taxonomy", {})

    contextual = filter_contextual_mras(mapping_mras)
    axes_used = sorted({axis for m in contextual for axis in (m.get("relevantAxes") or [])})
    missing_axes = _taxonomy_missing_keys(taxonomy, axes_used)
    if missing_axes:
        return build_error_envelope("ExecutionPlanning", "missing_taxonomy_keys", {"axes": missing_axes})

    source_profile_id, target_profile_id = infer_profile_ids(mapping_mra_filename, contextual)

    runtime_values = runtime_context.get("values")
    rules = transform_table.get("rules", [])
    code_lists = transform_table.get("codeLists", {})

    plans: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for mra in contextual:
        winner, trace, unresolved_reason = select_rule_for_mra(
            mra,
            rules,
            runtime_context,
            taxonomy,
            runtime_values=runtime_values,
        )
        if winner is None:
            unresolved.append({"componentId": mra.get("componentId"), "reason": unresolved_reason})
            continue
        plan: dict[str, Any] = {
            "componentId": mra.get("componentId"),
            "decision": "CONTEXTUAL_TRANSFORM",
            "relevantAxes": mra.get("relevantAxes") or [],
            "selectedRuleId": winner.get("ruleId"),
            "writes": (winner.get("then") or {}).get("writes", []),
            "trace": trace,
        }
        for key in ("constraints", "tests", "references"):
            if key in winner:
                plan[key] = winner[key]
        plans.append(plan)

    write_ops, error = build_write_operations(plans, runtime_values, code_lists)
    if error is not None:
        return error

    summary = {
        "contextualMraCount": len(contextual),
        "resolvedPlanCount": len(plans),
        "unresolvedCount": len(unresolved),
        "uniqueWriteOperationCount": len(write_ops),
        "symbolicWriteCount": sum(1 for op in write_ops if op.get("status") == "symbolic"),
        "conflictCount": 0,
    }

    execution = {
        "version": "ExecutionPlanning-1.1",
        "sourceProfileId": source_profile_id,
        "targetProfileId": target_profile_id,
        "runtimeContext": runtime_context,
        "plans": plans,
        "writeOperations": write_ops,
        "conflicts": [],
        "unresolved": unresolved,
        "summary": summary,
    }

    validation = {
        "version": "ExecutionPlanningValidation-1.1",
        "sourceProfileId": source_profile_id,
        "targetProfileId": target_profile_id,
        "checks": {
            "contextualOnly": True,
            "singleWinnerPerComponent": True,
            "noConflictingWrites": True,
            "allContextualComponentsHaveRules": len(unresolved) == 0,
            "deterministicTieBreakStable": True,
        },
    }

    exec_name = f"execution-planning.{source_profile_id}.{target_profile_id}.json".strip(".")
    val_name = f"execution-planning-validation.{source_profile_id}.{target_profile_id}.json".strip(".")

    return {
        "execution": execution,
        "validation": validation,
        "execution_name": exec_name,
        "validation_name": val_name,
    }
