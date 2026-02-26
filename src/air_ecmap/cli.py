"""CLI for AIR EC+Mapping engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from .mapping_orchestrator import run_mapping_pipeline
from .orchestrator import run_ec_pipeline

app = typer.Typer(help="AIR EC+Mapping CLI.")


@app.command()
def version() -> None:
    """Show placeholder version output."""
    typer.echo("air-ecmap bootstrap 0.1.0")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )


def _is_envelope(payload: Any) -> bool:
    return isinstance(payload, dict) and set(payload.keys()) == {"error", "reason", "details"}


def _load_profiles_from_dir_and_pairs(profiles_dir: Path, pairs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for pair in pairs:
        for profile_id in (pair["sourceProfileId"], pair["targetProfileId"]):
            if profile_id in profiles:
                continue
            ec_path = profiles_dir / f"step3-ec.{profile_id}.json"
            schema_path = profiles_dir / f"step4-profile.{profile_id}.json"
            ec_payload = _load_json(ec_path)
            schema_payload = _load_json(schema_path)
            profiles[profile_id] = {
                "ec": ec_payload.get("ec", {}),
                "profileSchema": schema_payload,
            }
    return profiles


@app.command("run-ec")
def run_ec(
    bundle: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="Path to EC input bundle JSON"),
    iucs: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="Path to IUCs JSON array"),
    output_dir: Path = typer.Option(..., file_okay=False, dir_okay=True, help="Output directory for artifacts"),
) -> None:
    """Run EC pipeline and emit normative artifact files."""
    try:
        ec_bundle = _load_json(bundle)
        iuc_list = _load_json(iucs)
    except Exception as exc:  # pragma: no cover - defensive CLI parse path
        typer.echo(json.dumps({"error": "Validation", "reason": f"input-parse-error: {exc}", "details": {}}, separators=(",", ":")))
        raise typer.Exit(code=2) from exc

    result = run_ec_pipeline(ec_bundle, iuc_list)
    if _is_envelope(result):
        typer.echo(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        raise typer.Exit(code=2)

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = result["artifacts"]
    for filename, payload in artifacts.items():
        _dump_json(output_dir / filename, payload)
    typer.echo(f"Wrote {len(artifacts)} artifacts to {output_dir}")


@app.command("run-mapping")
def run_mapping(
    profiles_dir: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True, help="Directory containing step3/step4 profile artifacts"),
    mapping_config: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="Path to mapping config JSON"),
    output_dir: Path = typer.Option(..., file_okay=False, dir_okay=True, help="Output directory for mapping artifacts"),
) -> None:
    """Run mapping phase and emit mapping artifacts."""
    try:
        cfg = _load_json(mapping_config)
        pairs = cfg.get("profilePairs", [])
        profiles = _load_profiles_from_dir_and_pairs(profiles_dir, pairs)
    except Exception as exc:  # pragma: no cover
        typer.echo(json.dumps({"error": "Validation", "reason": f"mapping-input-parse-error: {exc}", "details": {}}, separators=(",", ":")))
        raise typer.Exit(code=2) from exc

    result = run_mapping_pipeline(profiles, cfg)
    if _is_envelope(result):
        typer.echo(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        raise typer.Exit(code=2)

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = result["artifacts"]
    for filename, payload in artifacts.items():
        _dump_json(output_dir / filename, payload)
    typer.echo(f"Wrote {len(artifacts)} artifacts to {output_dir}")


@app.command("run-all")
def run_all(
    bundle: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="Path to EC input bundle JSON"),
    iucs: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="Path to IUCs JSON array"),
    mapping_config: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, help="Path to mapping config JSON"),
    output_dir: Path = typer.Option(..., file_okay=False, dir_okay=True, help="Output directory for EC + mapping artifacts"),
) -> None:
    """Run EC phase then mapping phase, writing all normative artifacts."""
    try:
        ec_bundle = _load_json(bundle)
        iuc_list = _load_json(iucs)
        cfg = _load_json(mapping_config)
    except Exception as exc:  # pragma: no cover
        typer.echo(json.dumps({"error": "Validation", "reason": f"input-parse-error: {exc}", "details": {}}, separators=(",", ":")))
        raise typer.Exit(code=2) from exc

    ec_result = run_ec_pipeline(ec_bundle, iuc_list)
    if _is_envelope(ec_result):
        typer.echo(json.dumps(ec_result, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        raise typer.Exit(code=2)

    output_dir.mkdir(parents=True, exist_ok=True)
    ec_artifacts = ec_result["artifacts"]
    for filename, payload in ec_artifacts.items():
        _dump_json(output_dir / filename, payload)

    pairs = cfg.get("profilePairs", [])
    try:
        profiles = _load_profiles_from_dir_and_pairs(output_dir, pairs)
    except Exception as exc:
        typer.echo(json.dumps({"error": "Validation", "reason": f"mapping-input-parse-error: {exc}", "details": {}}, separators=(",", ":")))
        raise typer.Exit(code=2) from exc

    mapping_result = run_mapping_pipeline(profiles, cfg)
    if _is_envelope(mapping_result):
        typer.echo(json.dumps(mapping_result, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        raise typer.Exit(code=2)

    mapping_artifacts = mapping_result["artifacts"]
    for filename, payload in mapping_artifacts.items():
        _dump_json(output_dir / filename, payload)

    typer.echo(f"Wrote {len(ec_artifacts) + len(mapping_artifacts)} artifacts to {output_dir}")


def main() -> None:
    """Entrypoint for console scripts."""
    app()


if __name__ == "__main__":
    main()
