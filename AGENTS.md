# AGENTS.md

## Mission Rules
- Mission files in `/spec` are the only source of truth. Do not invent semantics.
- Follow a test-first workflow: add or update tests before implementation.
- Always run `pytest -q` and show its output.
- Keep the deterministic core pure: no I/O and no global state.
- If anything is ambiguous, stop and write a `BLOCKER` note in `docs/decisions.md`.

## Naming
- `KCD` = Key Context Dimensions (axes used for mapping decisions per component).
- `MRA` = Mapping Rule Artifact (the final mapping artifact; contains `mappingJson` + `explanationJson`).