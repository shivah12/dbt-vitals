"""Documentation coverage module. Reports coverage %, plus a finding per
undocumented model so the report can list them."""

from __future__ import annotations

from dataclasses import dataclass

from dbt_doctor.findings import Finding, Severity
from dbt_doctor.parser import DbtProject


@dataclass
class DocCoverage:
    model_coverage_pct: float
    column_coverage_pct: float
    total_models: int
    documented_models: int
    total_columns: int
    documented_columns: int


def compute_coverage(project: DbtProject) -> DocCoverage:
    models = project.models
    total_models = len(models)
    documented_models = sum(1 for m in models.values() if m.description.strip())

    total_columns = 0
    documented_columns = 0
    for m in models.values():
        for col in m.columns.values():
            total_columns += 1
            if col.description.strip():
                documented_columns += 1

    return DocCoverage(
        model_coverage_pct=_pct(documented_models, total_models),
        column_coverage_pct=_pct(documented_columns, total_columns),
        total_models=total_models,
        documented_models=documented_models,
        total_columns=total_columns,
        documented_columns=documented_columns,
    )


def _pct(part: int, whole: int) -> float:
    return round((part / whole) * 100, 1) if whole else 0.0


def analyze(project: DbtProject) -> tuple[DocCoverage, list[Finding]]:
    coverage = compute_coverage(project)
    findings: list[Finding] = []

    for uid, model in project.models.items():
        if not model.description.strip():
            findings.append(
                Finding(
                    module="documentation",
                    severity=Severity.INFO,
                    subject=model.name,
                    message="Model has no description.",
                    weight=0.25,
                )
            )

    return coverage, findings
