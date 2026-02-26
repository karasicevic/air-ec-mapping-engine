"""End-to-end EC phase orchestration (validation -> Step1 -> Step2 -> Step3 -> Step4)."""

from __future__ import annotations

from typing import Any

from .step1 import run_step1_prefilter_safe
from .step2 import run_step2_oc_safe
from .step3 import run_step3_ec_safe
from .step4 import run_step4_profile_schema
from .validation import build_error_envelope, validate_ec_inputs


def _is_envelope(payload: dict[str, Any]) -> bool:
    return isinstance(payload, dict) and set(payload.keys()) == {"error", "reason", "details"}


def run_ec_pipeline(ec_bundle: dict[str, Any], iucs: list[dict[str, Any]]) -> dict[str, Any]:
    """Run EC pipeline in mission order and return in-memory artifacts or error envelope."""
    validation_envelope = validate_ec_inputs(ec_bundle, iucs)
    if validation_envelope is not None:
        return validation_envelope

    taxonomy = ec_bundle["taxonomy"]
    policy = ec_bundle["policy"]
    component_graph = ec_bundle["componentGraph"]
    assignments = ec_bundle["assignedBusinessContext"]

    step1 = run_step1_prefilter_safe(assignments, policy, taxonomy)
    if _is_envelope(step1):
        return step1

    step2 = run_step2_oc_safe(step1["prefiltered"], component_graph, taxonomy)
    if _is_envelope(step2):
        return step2

    artifacts: dict[str, Any] = {
        "step1-prefiltered.json": step1,
        "step2-oc.json": step2,
    }

    for iuc in iucs:
        step3 = run_step3_ec_safe(step2["oc"], component_graph, taxonomy, iuc)
        if _is_envelope(step3):
            return step3
        profile_id = iuc["id"]
        artifacts[f"step3-ec.{profile_id}.json"] = step3
        try:
            step4 = run_step4_profile_schema(step3["ec"], component_graph, iuc)
        except Exception as exc:  # pragma: no cover - defensive envelope guarantee
            return build_error_envelope("Step4", f"{exc.__class__.__name__}: {exc}", {"profileId": profile_id})
        artifacts[f"step4-profile.{profile_id}.json"] = step4

    return {
        "artifacts": artifacts,
        "profileIds": [i["id"] for i in iucs],
    }
