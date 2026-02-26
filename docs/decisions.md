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
