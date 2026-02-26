"""Validation layer for mission input contracts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class ValidationError(ValueError):
    """Raised when input contracts are violated."""


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def build_error_envelope(error: str, reason: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a Mission-EC §7-compliant error envelope."""
    _ensure(error in {"Validation", "Step1", "Step2", "Step3", "Step4"}, "error type is not allowed")
    _ensure(isinstance(reason, str) and reason != "", "reason must be non-empty string")
    payload: dict[str, Any] = {
        "error": error,
        "reason": reason,
        "details": details if details is not None else {},
    }
    return payload


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def _case_sensitive_from_taxonomy(taxonomy: dict[str, Any]) -> bool:
    rules = taxonomy.get("rules") or {}
    case_sensitive = rules.get("caseSensitive", True)
    _ensure(isinstance(case_sensitive, bool), "taxonomy.rules.caseSensitive must be boolean")
    return case_sensitive


def _delimiter_from_taxonomy(taxonomy: dict[str, Any]) -> str:
    rules = taxonomy.get("rules") or {}
    delimiter = rules.get("delimiter", ".")
    _ensure(isinstance(delimiter, str) and delimiter != "", "taxonomy.rules.delimiter must be non-empty string")
    return delimiter


def _norm(token: str, case_sensitive: bool) -> str:
    return token if case_sensitive else token.lower()


def _token_sets_for_key(
    taxonomy: dict[str, Any], key: str, case_sensitive: bool
) -> tuple[set[str], str]:
    categories = taxonomy["categories"][key]
    placeholder = taxonomy["placeholders"][key]
    category_set = {_norm(tok, case_sensitive) for tok in categories}
    return category_set, _norm(placeholder, case_sensitive)


def _validate_tuple_tokens(
    tuple_obj: dict[str, Any],
    taxonomy: dict[str, Any],
    *,
    context: str,
) -> None:
    keys = taxonomy["keys"]
    case_sensitive = _case_sensitive_from_taxonomy(taxonomy)
    allowed_keys = set(keys)
    _ensure(isinstance(tuple_obj, dict), f"{context}: tuple must be object")
    _ensure(set(tuple_obj.keys()).issubset(allowed_keys), f"{context}: tuple keys must be subset of taxonomy.keys")
    for key, token in tuple_obj.items():
        _ensure(isinstance(token, str), f"{context}: tuple token for key '{key}' must be string")
        category_set, placeholder = _token_sets_for_key(taxonomy, key, case_sensitive)
        normalized = _norm(token, case_sensitive)
        _ensure(
            normalized in category_set or normalized == placeholder,
            f"{context}: token '{token}' is not a valid CATEGORY or PLACEHOLDER for key '{key}'",
        )


def validate_taxonomy(taxonomy: dict[str, Any]) -> None:
    _ensure(isinstance(taxonomy, dict), "taxonomy must be an object")
    _ensure("keys" in taxonomy, "taxonomy.keys is required")
    _ensure("placeholders" in taxonomy, "taxonomy.placeholders is required")
    _ensure("categories" in taxonomy, "taxonomy.categories is required")
    _ensure(_is_str_list(taxonomy["keys"]), "taxonomy.keys must be an array of strings")
    keys = taxonomy["keys"]
    _ensure(len(keys) == len(set(keys)), "taxonomy.keys must be unique")

    placeholders = taxonomy["placeholders"]
    categories = taxonomy["categories"]
    defaults = taxonomy.get("defaults") or {}
    _ensure(isinstance(placeholders, dict), "taxonomy.placeholders must be an object")
    _ensure(isinstance(categories, dict), "taxonomy.categories must be an object")
    _ensure(isinstance(defaults, dict), "taxonomy.defaults must be an object if present")

    case_sensitive = _case_sensitive_from_taxonomy(taxonomy)
    delimiter = _delimiter_from_taxonomy(taxonomy)

    key_set = set(keys)
    _ensure(set(placeholders.keys()) == key_set, "taxonomy.placeholders must define one placeholder per taxonomy key")
    _ensure(set(categories.keys()) == key_set, "taxonomy.categories must define category list per taxonomy key")
    _ensure(set(defaults.keys()).issubset(key_set), "taxonomy.defaults keys must be subset of taxonomy.keys")

    for key in keys:
        ph = placeholders[key]
        _ensure(isinstance(ph, str) and ph != "", f"taxonomy.placeholders['{key}'] must be non-empty string")
        cats = categories[key]
        _ensure(_is_str_list(cats), f"taxonomy.categories['{key}'] must be an array of strings")
        norm_cats = {_norm(c, case_sensitive) for c in cats}
        _ensure(len(norm_cats) == len(cats), f"taxonomy.categories['{key}'] contains duplicates")
        _ensure(_norm(ph, case_sensitive) not in norm_cats, "Placeholders must not appear in taxonomy.categories")

        for token in cats:
            parts = token.split(delimiter)
            for idx in range(1, len(parts)):
                ancestor = delimiter.join(parts[:idx])
                _ensure(
                    _norm(ancestor, case_sensitive) in norm_cats,
                    f"taxonomy.categories for key '{key}' must be ancestor-closed",
                )

    for key, default_token in defaults.items():
        _ensure(isinstance(default_token, str), "taxonomy.defaults values must be strings")
        norm_cats = {_norm(c, case_sensitive) for c in categories[key]}
        _ensure(
            _norm(default_token, case_sensitive) in norm_cats,
            "taxonomy.defaults values must be concrete categories and not placeholders",
        )
        _ensure(
            _norm(default_token, case_sensitive) != _norm(placeholders[key], case_sensitive),
            "Placeholders must not appear in taxonomy.defaults",
        )


def validate_policy(policy: dict[str, Any], taxonomy: dict[str, Any]) -> None:
    validate_taxonomy(taxonomy)
    _ensure(isinstance(policy, dict), "policy must be an object")
    _ensure("policyKeys" in policy and "legalTuples" in policy, "policy must define policyKeys and legalTuples")
    _ensure(_is_str_list(policy["policyKeys"]), "policy.policyKeys must be an array of strings")
    _ensure(isinstance(policy["legalTuples"], list), "policy.legalTuples must be an array")
    policy_keys = policy["policyKeys"]
    taxonomy_keys = set(taxonomy["keys"])
    _ensure(len(policy_keys) == len(set(policy_keys)), "policy.policyKeys must be unique")
    _ensure(set(policy_keys).issubset(taxonomy_keys), "policyKeys must be subset of taxonomy.keys")

    required = set(policy_keys)
    for idx, tup in enumerate(policy["legalTuples"]):
        _validate_tuple_tokens(tup, taxonomy, context=f"policy.legalTuples[{idx}]")
        _ensure(required.issubset(set(tup.keys())), "policy.legalTuples entries must include all policyKeys")


def validate_component_graph(component_graph: dict[str, Any]) -> None:
    _ensure(isinstance(component_graph, dict), "componentGraph must be an object")
    for field in ("rootABIE", "abies", "asbies", "bbies"):
        _ensure(field in component_graph, f"componentGraph.{field} is required")

    root = component_graph["rootABIE"]
    abies = component_graph["abies"]
    asbies = component_graph["asbies"]
    bbies = component_graph["bbies"]
    _ensure(isinstance(root, str) and root != "", "componentGraph.rootABIE must be non-empty string")
    _ensure(isinstance(abies, list) and isinstance(asbies, list) and isinstance(bbies, list), "componentGraph lists must be arrays")

    rules = component_graph.get("rules") or {}
    _ensure(isinstance(rules, dict), "componentGraph.rules must be object")
    rounds = rules.get("maxFixpointRounds", 8)
    _ensure(isinstance(rounds, int) and rounds > 0, "componentGraph.rules.maxFixpointRounds must be positive integer")

    abie_ids = []
    asbie_ids = []
    bbie_ids = []

    for idx, abie in enumerate(abies):
        _ensure(isinstance(abie, dict), f"componentGraph.abies[{idx}] must be object")
        abie_id = abie.get("id")
        _ensure(isinstance(abie_id, str) and abie_id != "", f"componentGraph.abies[{idx}].id is required")
        abie_ids.append(abie_id)
        for field in ("childrenBBIE", "childrenASBIE"):
            if field in abie:
                _ensure(_is_str_list(abie[field]), f"componentGraph.abies[{idx}].{field} must be array of strings")

    for idx, asbie in enumerate(asbies):
        _ensure(isinstance(asbie, dict), f"componentGraph.asbies[{idx}] must be object")
        asbie_id = asbie.get("id")
        _ensure(isinstance(asbie_id, str) and asbie_id != "", f"componentGraph.asbies[{idx}].id is required")
        asbie_ids.append(asbie_id)
        _ensure(isinstance(asbie.get("sourceABIE"), str), f"componentGraph.asbies[{idx}].sourceABIE is required")
        _ensure(isinstance(asbie.get("targetABIE"), str), f"componentGraph.asbies[{idx}].targetABIE is required")

    for idx, bbie in enumerate(bbies):
        _ensure(isinstance(bbie, dict), f"componentGraph.bbies[{idx}] must be object")
        bbie_id = bbie.get("id")
        _ensure(isinstance(bbie_id, str) and bbie_id != "", f"componentGraph.bbies[{idx}].id is required")
        bbie_ids.append(bbie_id)
        _ensure(isinstance(bbie.get("ownerABIE"), str), f"componentGraph.bbies[{idx}].ownerABIE is required")

    all_ids = abie_ids + asbie_ids + bbie_ids
    _ensure(len(all_ids) == len(set(all_ids)), "component graph IDs are globally unique")

    abie_set = set(abie_ids)
    asbie_set = set(asbie_ids)
    bbie_set = set(bbie_ids)
    _ensure(root in abie_set, "componentGraph.rootABIE must reference an ABIE id")

    for idx, asbie in enumerate(asbies):
        _ensure(asbie["sourceABIE"] in abie_set, f"componentGraph.asbies[{idx}].sourceABIE must resolve to ABIE id")
        _ensure(asbie["targetABIE"] in abie_set, f"componentGraph.asbies[{idx}].targetABIE must resolve to ABIE id")

    for idx, bbie in enumerate(bbies):
        _ensure(bbie["ownerABIE"] in abie_set, f"componentGraph.bbies[{idx}].ownerABIE must resolve to ABIE id")

    for idx, abie in enumerate(abies):
        for child in abie.get("childrenASBIE", []):
            _ensure(child in asbie_set, f"componentGraph.abies[{idx}].childrenASBIE must resolve to ASBIE ids")
        for child in abie.get("childrenBBIE", []):
            _ensure(child in bbie_set, f"componentGraph.abies[{idx}].childrenBBIE must resolve to BBIE ids")


def validate_assignments(
    assignments: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    component_graph: dict[str, Any],
) -> None:
    validate_taxonomy(taxonomy)
    validate_component_graph(component_graph)
    _ensure(isinstance(assignments, list), "assignedBusinessContext must be an array")

    allowed_components = {
        entry["id"] for entry in component_graph["asbies"]
    } | {
        entry["id"] for entry in component_graph["bbies"]
    }

    for idx, item in enumerate(assignments):
        _ensure(isinstance(item, dict), f"assignedBusinessContext[{idx}] must be object")
        component_id = item.get("componentId")
        _ensure(isinstance(component_id, str) and component_id != "", f"assignedBusinessContext[{idx}].componentId is required")
        _ensure(component_id in allowed_components, f"assignedBusinessContext[{idx}].componentId must resolve to BBIE/ASBIE id")
        tuples = item.get("tuples")
        _ensure(isinstance(tuples, list), f"assignedBusinessContext[{idx}].tuples must be an array")
        for t_idx, tup in enumerate(tuples):
            _validate_tuple_tokens(tup, taxonomy, context=f"assignedBusinessContext[{idx}].tuples[{t_idx}]")


def validate_iucs(iucs: list[dict[str, Any]], taxonomy: dict[str, Any]) -> None:
    validate_taxonomy(taxonomy)
    _ensure(isinstance(iucs, list), "iucs must be an array")
    ids: list[str] = []

    for idx, iuc in enumerate(iucs):
        _ensure(isinstance(iuc, dict), f"iucs[{idx}] must be object")
        iuc_id = iuc.get("id")
        _ensure(isinstance(iuc_id, str) and iuc_id != "", f"iucs[{idx}].id is required")
        ids.append(iuc_id)
        tuples = iuc.get("tuples")
        _ensure(isinstance(tuples, list), f"iucs[{idx}].tuples must be an array")
        for t_idx, tup in enumerate(tuples):
            _validate_tuple_tokens(tup, taxonomy, context=f"iucs[{idx}].tuples[{t_idx}]")

    _ensure(len(ids) == len(set(ids)), "iucs ids must be unique")


def normalize_mapping_config(mapping_config: dict[str, Any]) -> dict[str, Any]:
    _ensure(isinstance(mapping_config, dict), "mappingConfig must be an object")
    cfg = deepcopy(mapping_config)
    bie_catalog = cfg.get("bie_catalog", {})
    if isinstance(bie_catalog, dict):
        for component_id, entry in bie_catalog.items():
            if isinstance(entry, dict):
                entry.setdefault("relevantAxes", [])
            else:
                raise ValidationError(f"mappingConfig.bie_catalog['{component_id}'] must be object")
    return cfg


def validate_mapping_config(mapping_config: dict[str, Any]) -> None:
    cfg = normalize_mapping_config(mapping_config)
    _ensure("profilePairs" in cfg, "mappingConfig.profilePairs is required")
    _ensure("bie_catalog" in cfg, "mappingConfig.bie_catalog is required")
    _ensure("schemaPaths" in cfg, "mappingConfig.schemaPaths is required")

    profile_pairs = cfg["profilePairs"]
    bie_catalog = cfg["bie_catalog"]
    schema_paths = cfg["schemaPaths"]

    _ensure(isinstance(profile_pairs, list), "mappingConfig.profilePairs must be an array")
    _ensure(isinstance(bie_catalog, dict), "mappingConfig.bie_catalog must be an object")
    _ensure(isinstance(schema_paths, dict), "mappingConfig.schemaPaths must be an object")

    for idx, pair in enumerate(profile_pairs):
        _ensure(isinstance(pair, dict), f"mappingConfig.profilePairs[{idx}] must be object")
        _ensure(
            isinstance(pair.get("sourceProfileId"), str) and pair["sourceProfileId"] != "",
            f"mappingConfig.profilePairs[{idx}].sourceProfileId is required",
        )
        _ensure(
            isinstance(pair.get("targetProfileId"), str) and pair["targetProfileId"] != "",
            f"mappingConfig.profilePairs[{idx}].targetProfileId is required",
        )

    for component_id, entry in bie_catalog.items():
        _ensure(isinstance(component_id, str) and component_id != "", "mappingConfig.bie_catalog keys must be non-empty strings")
        _ensure(isinstance(entry, dict), f"mappingConfig.bie_catalog['{component_id}'] must be object")
        _ensure(isinstance(entry.get("anchor"), str) and entry["anchor"] != "", f"mappingConfig.bie_catalog['{component_id}'].anchor is required")
        axes = entry.get("relevantAxes", [])
        _ensure(_is_str_list(axes), f"mappingConfig.bie_catalog['{component_id}'].relevantAxes must be array of strings")
        _ensure(len(axes) == len(set(axes)), f"mappingConfig.bie_catalog['{component_id}'].relevantAxes must be unique")

    _ensure(set(schema_paths.keys()) == {"source", "target"}, "mappingConfig.schemaPaths must contain source and target")
    for side in ("source", "target"):
        side_obj = schema_paths[side]
        _ensure(isinstance(side_obj, dict), f"mappingConfig.schemaPaths.{side} must be object")
        for component_id, path in side_obj.items():
            _ensure(isinstance(component_id, str) and component_id != "", f"mappingConfig.schemaPaths.{side} keys must be non-empty strings")
            _ensure(isinstance(path, str) and path != "", f"mappingConfig.schemaPaths.{side}['{component_id}'] must be non-empty string")


def validate_ec_inputs(ec_bundle: dict[str, Any], iucs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Validate EC input sections in mission order and return validation envelope on failure."""
    try:
        _ensure(isinstance(ec_bundle, dict), "ec bundle must be object")
        required = ("taxonomy", "policy", "componentGraph", "assignedBusinessContext")
        for section in required:
            _ensure(section in ec_bundle, f"missing required section: {section}")
    except ValidationError as exc:
        return build_error_envelope("Validation", f"bundle: {exc}", {"section": "bundle"})

    taxonomy = ec_bundle["taxonomy"]
    policy = ec_bundle["policy"]
    component_graph = ec_bundle["componentGraph"]
    assignments = ec_bundle["assignedBusinessContext"]

    try:
        validate_taxonomy(taxonomy)
    except ValidationError as exc:
        return build_error_envelope("Validation", f"taxonomy: {exc}", {"section": "taxonomy"})

    try:
        validate_policy(policy, taxonomy)
    except ValidationError as exc:
        return build_error_envelope("Validation", f"policy: {exc}", {"section": "policy"})

    try:
        validate_component_graph(component_graph)
    except ValidationError as exc:
        return build_error_envelope("Validation", f"componentGraph: {exc}", {"section": "componentGraph"})

    try:
        validate_assignments(assignments, taxonomy, component_graph)
    except ValidationError as exc:
        return build_error_envelope(
            "Validation",
            f"assignedBusinessContext: {exc}",
            {"section": "assignedBusinessContext"},
        )

    try:
        validate_iucs(iucs, taxonomy)
    except ValidationError as exc:
        return build_error_envelope("Validation", f"iucs: {exc}", {"section": "iucs"})

    return None
