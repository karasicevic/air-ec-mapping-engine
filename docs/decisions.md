# Spec ambiguities / decisions

## BLOCKER-2026-02-26-001: Mission version labeling mismatch

- Status: `BLOCKER`
- Observed in repository:
  - Filenames are `spec/Mission-EC-2.0.txt`, `spec/Mission-Mapping-2.0.txt`, and `spec/Mission-Execution-Protocol-2.0.txt`.
  - Pasted normative content inside those files repeatedly references `Mission-EC-2.1` and `Mission-Mapping-2.1`.
- Why this blocks deterministic implementation:
  - Cross-file references are version-sensitive and can change semantics.
  - We cannot safely assume whether `2.0` filenames are intended containers for `2.1` text, or whether a `2.0` normative text set is still expected.
- Required clarification:
  - Confirm that the current pasted text (internally labeled `2.1`) is the normative source of truth to implement.

### Resolution (2026-02-26)

- Status changed to: `RESOLVED`
- Decision:
  - Treat the currently pasted mission text (internally labeled `2.1`) as normative,
    even though repository filenames remain `*-2.0.txt`.
- Operational rule:
- Implement behavior from file content, not filename suffix.
- Keep existing filenames unchanged unless explicitly requested.

## BLOCKER-2026-02-26-002: Separate IUCs per source/target bundle

- Status: `RESOLVED`
- Observed:
  - Mission files do not explicitly state whether source and target IUCs are separate files.
  - Latest testing requires separate IUCs for each bundle to ensure independent EC execution.
- Decision:
  - Support separate IUCs inputs for source and target bundles in pair execution.
  - Pair commands will accept `source-iucs` and `target-iucs` explicitly.
- Reason:
  - Enables independent EC computation per bundle and matches current testing practice.

## Note-2026-04-08: Phase-3 attachments override pasted text

Phase-3 mission+schema were provided as attachments and copied verbatim; attachments override any earlier pasted instructions.


## BLOCKER-2026-04-08-003: Phase-3 schema/fixture mismatches

- Status: BLOCKER`n- Observed:
  - TransformTable schema requires codeLists.entries + rule.tests/references shapes that differ from fixtures (fixtures use codeLists.mapping and tests with type/description).
  - Mission file requires ExecutionPlanningValidation-1.1, but fixture uses ExecutionPlanningValidation-1.0.
- Impact:
  - Strict models aligned to schema will reject fixture data; fixture-driven tests imply accepting current fixture shapes.
- Required clarification:
  - Confirm whether fixtures should be updated to match schema/mission, or models should accept fixture shapes as normative for now.


## Note-2026-04-08: Phase-3 optional flags in run-all-pair

Decision: if exactly one of --transform-table or --runtime-context is provided, treat it as a Validation error (execution-planning-inputs-incomplete) to avoid silently skipping Execution Planning.


## OVERRIDE-2026-04-08-004: Rename Phase 3 to Execution Planning

- Status: APPROVED`n- User directive: rename Phase 3 terminology to Execution Planning everywhere, including artifacts, CLI, and specs.
- Action: applied global rename from prior Phase 3 terminology to Execution Planning across code, specs, tests, and fixtures.

