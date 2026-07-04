from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console

from dbt_doctor import __version__
from dbt_doctor.graph import build_model_graph
from dbt_doctor.modules import documentation, duplicates, incremental, lineage, testing
from dbt_doctor.parser import ManifestNotFoundError, load_catalog, load_manifest
from dbt_doctor.report import render, render_ci_comment
from dbt_doctor.scoring import compute_score

console = Console()


@click.group()
@click.version_option(__version__, prog_name="dbt-doctor")
def cli() -> None:
    """dbt-doctor: static analysis and health scoring for dbt projects."""


@cli.command()
@click.argument("target_dir", type=click.Path(exists=True, file_okay=False), default=".")
@click.option(
    "--manifest",
    "manifest_override",
    type=click.Path(exists=True, dir_okay=False),
    help="Explicit path to manifest.json (default: <target_dir>/target/manifest.json)",
)
@click.option(
    "--catalog",
    "catalog_override",
    type=click.Path(exists=True, dir_okay=False),
    help="Explicit path to catalog.json (default: <target_dir>/target/catalog.json)",
)
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON instead of the terminal report.")
@click.option("--ci-comment", is_flag=True, help="Print a markdown summary suitable for a PR comment.")
@click.option(
    "--fail-under",
    type=int,
    default=None,
    help="Exit with a non-zero status code if the health score is below this threshold (useful in CI).",
)
def analyze(
    target_dir: str,
    manifest_override: str | None,
    catalog_override: str | None,
    as_json: bool,
    ci_comment: bool,
    fail_under: int | None,
) -> None:
    """Analyze a dbt project and print its health report.

    TARGET_DIR is the root of your dbt project (the directory containing
    dbt_project.yml). Defaults to the current directory. Run `dbt compile`
    or `dbt docs generate` first so target/manifest.json exists.
    """
    root = Path(target_dir)
    manifest_path = Path(manifest_override) if manifest_override else root / "target" / "manifest.json"
    catalog_path = Path(catalog_override) if catalog_override else root / "target" / "catalog.json"

    try:
        project = load_manifest(manifest_path)
    except ManifestNotFoundError as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1)

    catalog_loaded = load_catalog(catalog_path, project)

    graph = build_model_graph(project)

    findings = []
    findings += lineage.analyze(project, graph)
    findings += testing.analyze(project)
    findings += duplicates.analyze(project)
    doc_coverage, doc_findings = documentation.analyze(project)
    findings += doc_findings
    findings += incremental.analyze(project, catalog_loaded)

    model_count = len(project.models)
    score = compute_score(findings, model_count)

    if as_json:
        payload = {
            "score": score.score,
            "critical_count": score.critical_count,
            "warning_count": score.warning_count,
            "info_count": score.info_count,
            "model_count": model_count,
            "documentation": {
                "model_coverage_pct": doc_coverage.model_coverage_pct,
                "column_coverage_pct": doc_coverage.column_coverage_pct,
            },
            "findings": [
                {
                    "module": f.module,
                    "severity": f.severity.value,
                    "subject": f.subject,
                    "message": f.message,
                    "detail": f.detail,
                    "suggestion": f.suggestion,
                }
                for f in findings
            ],
        }
        click.echo(json.dumps(payload, indent=2))
    elif ci_comment:
        click.echo(render_ci_comment(score, findings))
    else:
        render(console, score, findings, doc_coverage, model_count)

    if fail_under is not None and score.score < fail_under:
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
