from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "spec"
PLACEHOLDER = "PASTE THE NORMATIVE TEXT HERE; DO NOT GUESS."


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_spec_files_exist_and_nonempty() -> None:
    required = [
        SPEC_DIR / "Mission-EC-2.0.txt",
        SPEC_DIR / "Mission-Mapping-2.0.txt",
        SPEC_DIR / "Mission-Execution-Protocol-2.0.txt",
    ]
    for path in required:
        assert path.exists(), f"Missing spec file: {path}"
        assert path.stat().st_size > 0, f"Empty spec file: {path}"


def test_spec_files_are_not_placeholder_templates() -> None:
    for path in SPEC_DIR.glob("*.txt"):
        content = _read(path)
        assert PLACEHOLDER not in content, f"Placeholder content still present in: {path}"


def test_ec_spec_has_steps_and_normative_filenames() -> None:
    content = _read(SPEC_DIR / "Mission-EC-2.0.txt")
    for required in [
        "Step 1",
        "Step 2",
        "Step 3",
        "Step 4",
        "step1-prefiltered.json",
        "step2-oc.json",
        "step3-ec.<profileId>.json",
        "step4-profile.<profileId>.json",
        "Error Envelope",
        "Determinism",
    ]:
        assert required in content, f"Expected EC marker missing: {required}"


def test_mapping_spec_has_kcd_mra_and_outputs() -> None:
    content = _read(SPEC_DIR / "Mission-Mapping-2.0.txt")
    for required in [
        "Key Context Dimensions (KCD)",
        "MRA",
        "mapping.mra.<S>.<T>.json",
        "mapping.explanations.<S>.<T>.json",
        "SEAMLESS",
        "CONTEXTUAL_TRANSFORM",
        "NO_MAPPING",
    ]:
        assert required in content, f"Expected mapping marker missing: {required}"


def test_execution_protocol_has_precedence_and_phase_order() -> None:
    content = _read(SPEC_DIR / "Mission-Execution-Protocol-2.0.txt")
    for required in [
        "Normative precedence",
        "MUST NOT add steps",
        "Run Mission-EC",
        "Run Mission-Mapping",
        "Step 1",
        "Step 2",
        "Step 3",
        "Step 4",
    ]:
        assert required in content, f"Expected execution protocol marker missing: {required}"

