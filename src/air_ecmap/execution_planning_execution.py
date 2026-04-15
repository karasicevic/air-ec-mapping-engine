"""Execution Planning: evaluate valueExpr and produce normalized write operations."""

from __future__ import annotations

import json
from typing import Any

from .validation import build_error_envelope


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _write_operation_dedup_key(op: dict[str, Any]) -> tuple[Any, ...]:
    status = op.get("status")
    key: tuple[Any, ...] = (
        op.get("targetPath"),
        _canonical_json(op.get("valueExpr")),
        status,
    )
    if status == "resolved":
        return key + (_canonical_json(op.get("value")),)
    return key + (op.get("missingReason"),)


def dedup_write_operations(write_ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for op in write_ops:
        key = _write_operation_dedup_key(op)
        if key in seen:
            continue
        seen.add(key)
        unique.append(op)
    return unique


def _code_list_map(code_lists: dict[str, Any], table_id: str | None) -> dict[Any, Any] | None:
    if not table_id:
        return None
    table = (code_lists or {}).get(table_id)
    if not isinstance(table, dict):
        return None
    if "entries" in table and isinstance(table["entries"], list):
        mapping: dict[Any, Any] = {}
        for entry in table["entries"]:
            if not isinstance(entry, dict):
                continue
            if "source" not in entry or "target" not in entry:
                continue
            mapping[entry["source"]] = entry["target"]
        return mapping
    if "mapping" in table and isinstance(table["mapping"], dict):
        return dict(table["mapping"])
    return None


def _lookup_default(value_expr: dict[str, Any]) -> tuple[bool, Any]:
    if "default" in value_expr:
        return True, value_expr.get("default")
    on_missing = value_expr.get("onMissing")
    if isinstance(on_missing, dict) and on_missing.get("action") == "default":
        if "default" in on_missing:
            return True, on_missing.get("default")
    return False, None


def evaluate_value_expr(
    value_expr: dict[str, Any],
    runtime_values: dict[str, Any] | None,
    code_lists: dict[str, Any],
) -> tuple[str, Any | None, str | None]:
    kind = value_expr.get("kind")
    if kind == "literal":
        return "resolved", value_expr.get("value"), None
    if kind == "source_value":
        source_path = value_expr.get("sourcePath")
        if runtime_values and source_path in runtime_values:
            return "resolved", runtime_values.get(source_path), None
        return "symbolic", None, "missing_runtime_value"
    if kind == "lookup":
        input_expr = value_expr.get("input")
        if not isinstance(input_expr, dict):
            return "symbolic", None, "missing_runtime_value"
        status, input_value, missing = evaluate_value_expr(input_expr, runtime_values, code_lists)
        if status != "resolved":
            return "symbolic", None, missing or "missing_runtime_value"
        mapping = _code_list_map(code_lists, value_expr.get("tableId"))
        if mapping is None:
            has_default, default_value = _lookup_default(value_expr)
            if has_default:
                return "resolved", default_value, None
            return "symbolic", None, "missing_lookup_table"
        if input_value in mapping:
            return "resolved", mapping[input_value], None
        has_default, default_value = _lookup_default(value_expr)
        if has_default:
            return "resolved", default_value, None
        return "symbolic", None, "missing_lookup_mapping"
    return "symbolic", None, "invalid_value_expr"


def build_write_operations(
    plans: list[dict[str, Any]],
    runtime_values: dict[str, Any] | None,
    code_lists: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    operations: list[dict[str, Any]] = []
    for plan in plans:
        component_id = plan.get("componentId")
        rule_id = plan.get("selectedRuleId") or plan.get("ruleId")
        for write in plan.get("writes", []):
            if not isinstance(write, dict):
                continue
            target_path = write.get("targetPath")
            value_expr = write.get("value") or write.get("valueExpr")
            if not isinstance(value_expr, dict):
                continue
            status, value, missing = evaluate_value_expr(value_expr, runtime_values, code_lists)
            op: dict[str, Any] = {
                "componentId": component_id,
                "ruleId": rule_id,
                "targetPath": target_path,
                "valueExpr": value_expr,
                "status": status,
            }
            if status == "resolved":
                op["value"] = value
            else:
                op["missingReason"] = missing or "missing_runtime_value"
            operations.append(op)

    resolved_by_target: dict[str, Any] = {}
    conflicts: dict[str, list[Any]] = {}
    for op in operations:
        if op.get("status") != "resolved":
            continue
        target_path = op.get("targetPath")
        value = op.get("value")
        if target_path in resolved_by_target:
            if resolved_by_target[target_path] != value:
                conflicts[target_path] = [resolved_by_target[target_path], value]
        else:
            resolved_by_target[target_path] = value

    if conflicts:
        details = {"conflicts": conflicts}
        return [], build_error_envelope("ExecutionPlanning", "conflicting_writes", details)

    return dedup_write_operations(operations), None
