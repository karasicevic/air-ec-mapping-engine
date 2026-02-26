# Fixture Normalization Notes

These fixture files were normalized from user-provided sources:

- `EC-Input-2.1.updated.json` -> `fixtures/bundle.json`
- `IUCs.updated.json` -> `fixtures/iucs.json`
- `mappingConfig.updated.json` -> `fixtures/mapping_config.json`

## Exact normalizations applied

1. `assignedBussinesContext` renamed to `assignedBusinessContext`.
Reason:
- Engine input contract uses `assignedBusinessContext` exactly.

2. `taxonomy.categories` converted from one flat token list to per-key category lists.
Reason:
- Current validator expects `taxonomy.categories` as an object keyed by taxonomy axis.

3. `IUCs.updated.json` top-level object `{ "IUCs": [...] }` converted to plain array in `fixtures/iucs.json`.
Reason:
- CLI `--iucs` currently expects a JSON array of IUC objects.

4. Optional metadata wrappers (`version`, `meta`) removed from runtime fixture bundle/config.
Reason:
- Runtime contract consumes core sections only and ignores metadata for deterministic execution.

No semantic values were invented. Normalization was shape/key adaptation only for repository runtime compatibility.
