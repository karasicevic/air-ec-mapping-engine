# AIR EC + Mapping Engine (Prototype)

## Usage

Run commands from repository root.

### 1) Install CLI (one-time)

```powershell
.\.venv\Scripts\python -m pip install -e .
```

### 2) Run EC phase

Inputs:
- EC bundle JSON (must include: `taxonomy`, `policy`, `componentGraph`, `assignedBusinessContext`)
- IUCs JSON array

Command:

```powershell
air-ecmap run-ec --bundle .\fixtures\bundle.json --iucs .\fixtures\iucs.json --output-dir .\out\ec
```

Outputs:
- `step1-prefiltered.json`
- `step2-oc.json`
- `step3-ec.<profileId>.json` (per IUC)
- `step4-profile.<profileId>.json` (per IUC)

### 3) Run Mapping phase

Inputs:
- `profiles-dir` containing EC artifacts:
  - `step3-ec.<profileId>.json`
  - `step4-profile.<profileId>.json`
- mapping config JSON (must include: `profilePairs`, `bie_catalog`, `schemaPaths`)

Command:

```powershell
air-ecmap run-mapping --profiles-dir .\out\ec --mapping-config .\fixtures\mapping_config.json --output-dir .\out\mapping
```

Outputs:
- `mapping.mra.<sourceProfileId>.<targetProfileId>.json`
- `mapping.explanations.<sourceProfileId>.<targetProfileId>.json`

### 4) Run full protocol (EC + Mapping)

Inputs:
- EC bundle JSON
- IUCs JSON array
- mapping config JSON

Command:

```powershell
air-ecmap run-all --bundle .\fixtures\bundle.json --iucs .\fixtures\iucs.json --mapping-config .\fixtures\mapping_config.json --output-dir .\out\all
```

Outputs in one directory:
- EC artifacts (`step1-*`, `step2-*`, `step3-*`, `step4-*`)
- Mapping artifacts (`mapping.mra.*`, `mapping.explanations.*`)

## Notes

- On failure, commands print a uniform error envelope (`error`, `reason`, `details`) and exit non-zero.
- Mission files in `spec/` are the normative source of truth.
