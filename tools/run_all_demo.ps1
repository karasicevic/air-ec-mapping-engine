param(
  [string]$SourceBundle = ".\\fixtures\\source_bundle.json",
  [string]$TargetBundle = ".\\fixtures\\target_bundle.json",
  [string]$SourceIucs = ".\\fixtures\\iucs_source.json",
  [string]$TargetIucs = ".\\fixtures\\iucs_target.json",
  [string]$MappingConfig = ".\\fixtures\\mapping_config.json",
  [string]$OutDir = ".\\out\\all"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path ".\\.venv\\Scripts\\air-ecmap.exe")) {
  Write-Host "Installing editable package..." -ForegroundColor Yellow
  .\\.venv\\Scripts\\python -m pip install -e .
}

Write-Host "Running end-to-end EC + Mapping..." -ForegroundColor Cyan
& .\\.venv\\Scripts\\air-ecmap.exe run-all-pair --source-bundle $SourceBundle --target-bundle $TargetBundle --source-iucs $SourceIucs --target-iucs $TargetIucs --mapping-config $MappingConfig --output-dir $OutDir

Write-Host "Done. Artifacts in $OutDir" -ForegroundColor Green
