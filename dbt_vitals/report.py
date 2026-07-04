from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dbt_vitals.findings import Finding, Severity
from dbt_vitals.modules.documentation import DocCoverage
from dbt_vitals.scoring import ScoreResult

SEVERITY_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.WARNING: "yellow",
    Severity.INFO: "dim cyan",
}
SEVERITY_ICON = {
    Severity.CRITICAL: "\u274c",  # ❌
    Severity.WARNING: "\u26a0",  # ⚠
    Severity.INFO: "\u2139",     # ℹ
}


def render(
    console: Console,
    score: ScoreResult,
    findings: list[Finding],
    doc_coverage: DocCoverage,
    model_count: int,
) -> None:
    console.print()
    console.print(
        Panel(
            Text(f"{score.score}/100", style="bold", justify="center"),
            title="Overall Health",
            subtitle=f"{model_count} models analyzed",
            expand=False,
        )
    )
    console.print(
        f"  [bold red]Critical:[/] {score.critical_count}   "
        f"[yellow]Warnings:[/] {score.warning_count}   "
        f"[dim cyan]Info:[/] {score.info_count}\n"
    )

    console.print(
        f"[bold]Documentation[/]  models {doc_coverage.model_coverage_pct}% "
        f"({doc_coverage.documented_models}/{doc_coverage.total_models})   "
        f"columns {doc_coverage.column_coverage_pct}% "
        f"({doc_coverage.documented_columns}/{doc_coverage.total_columns})\n"
    )

    by_module: dict[str, list[Finding]] = {}
    for f in findings:
        by_module.setdefault(f.module, []).append(f)

    module_titles = {
        "lineage": "Lineage",
        "testing": "Testing",
        "duplicates": "Duplicate Logic",
        "documentation": "Documentation",
        "incremental": "Incremental Candidates",
    }

    for module_key, title in module_titles.items():
        items = sorted(by_module.get(module_key, []), key=lambda f: f.severity.value)
        if not items:
            continue

        table = Table(title=title, show_lines=False, expand=True)
        table.add_column("", width=2)
        table.add_column("Subject", style="bold", overflow="fold")
        table.add_column("Finding", overflow="fold")
        table.add_column("Suggestion", style="dim", overflow="fold")

        for f in items:
            table.add_row(
                SEVERITY_ICON[f.severity],
                f.subject,
                f.message,
                f.suggestion or "",
            )
        console.print(table)
        console.print()

    if not findings:
        console.print("[bold green]No issues found. Nice project.[/]")


def render_ci_comment(score: ScoreResult, findings: list[Finding], previous_score: int | None = None) -> str:
    """Renders a compact markdown summary suitable for a GitHub PR comment."""
    lines = [f"### dbt-doctor health score: {score.score}"]
    if previous_score is not None:
        delta = score.score - previous_score
        arrow = "\u2191" if delta > 0 else ("\u2193" if delta < 0 else "\u2192")
        lines.append(f"{arrow} from {previous_score}")
    lines.append("")
    lines.append(f"- Critical: {score.critical_count}")
    lines.append(f"- Warnings: {score.warning_count}")
    lines.append(f"- Info: {score.info_count}")

    top = sorted(findings, key=lambda f: SEVERITY_STYLE.get(f.severity, ""), reverse=True)[:10]
    if top:
        lines.append("")
        lines.append("<details><summary>Top findings</summary>\n")
        for f in top:
            lines.append(f"- **[{f.module}]** {f.subject}: {f.message}")
        lines.append("\n</details>")

    return "\n".join(lines)
