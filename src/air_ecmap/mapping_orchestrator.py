"""End-to-end mapping phase orchestration."""

from __future__ import annotations

from typing import Any

from .mapping import build_mra, classify_component
from .validation import build_error_envelope, normalize_mapping_config, validate_mapping_config


def _component_ec(ec_payload: dict[str, Any], component_id: str) -> list[dict[str, str]]:
    for kind in ("ABIE", "ASBIE", "BBIE"):
        bucket = ec_payload.get(kind) or {}
        if component_id in bucket:
            value = bucket[component_id]
            if isinstance(value, list):
                return value
            return []
    return []


def run_mapping_pipeline(profiles: dict[str, dict[str, Any]], mapping_config: dict[str, Any]) -> dict[str, Any]:
    """Run mapping phase for configured profile pairs and emit artifacts."""
    try:
        validate_mapping_config(mapping_config)
    except Exception as exc:
        return build_error_envelope("Validation", str(exc), {"stage": "mapping-config"})

    cfg = normalize_mapping_config(mapping_config)
    artifacts: dict[str, Any] = {}

    profile_pairs = cfg["profilePairs"]
    bie_catalog = cfg["bie_catalog"]
    schema_paths = cfg["schemaPaths"]

    for pair in profile_pairs:
        source_id = pair["sourceProfileId"]
        target_id = pair["targetProfileId"]
        if source_id not in profiles or target_id not in profiles:
            return build_error_envelope(
                "Validation",
                f"profile not found in mapping inputs: {source_id}->{target_id}",
                {"stage": "profiles"},
            )

        source_profile = profiles[source_id]
        target_profile = profiles[target_id]
        source_ec = source_profile["ec"]
        target_ec = target_profile["ec"]

        mras: list[dict[str, Any]] = []
        explanations: list[dict[str, Any]] = []

        for component_id in sorted(bie_catalog.keys()):
            ec_source_full = _component_ec(source_ec, component_id)
            ec_target_full = _component_ec(target_ec, component_id)
            if len(ec_source_full) == 0 or len(ec_target_full) == 0:
                continue

            entry = bie_catalog[component_id]
            axes = entry.get("relevantAxes", [])
            decision, ec_source_rel, ec_target_rel, ec_common = classify_component(
                ec_source_full,
                ec_target_full,
                axes,
            )
            if decision == "NO_MAPPING":
                continue

            _ = ec_source_rel, ec_target_rel  # maintained for explicitness/debug parity
            source_path = (schema_paths.get("source") or {}).get(component_id, "")
            target_path = (schema_paths.get("target") or {}).get(component_id, "")
            mra = build_mra(
                component_id=component_id,
                anchor=entry["anchor"],
                relevant_axes=axes,
                decision=decision,
                ec_source_full=ec_source_full,
                ec_target_full=ec_target_full,
                ec_common_on_kcd=ec_common,
                source_path=source_path,
                target_path=target_path,
            )
            mras.append(mra)
            explanations.append(mra["explanationJson"])

        artifacts[f"mapping.mra.{source_id}.{target_id}.json"] = mras
        artifacts[f"mapping.explanations.{source_id}.{target_id}.json"] = explanations

    return {"artifacts": artifacts}
