from __future__ import annotations

from dataclasses import dataclass

from dbt_doctor.findings import Finding, Severity

# How many score points a single unit of finding "weight" costs,
# scaled by severity. Tuned so a handful of warnings dents the score
# noticeably without small projects instantly cratering to 0.
SEVERITY_MULTIPLIER = {
    Severity.CRITICAL: 6.0,
    Severity.WARNING: 2.0,
    Severity.INFO: 0.5,
}


@dataclass
class ScoreResult:
    score: int
    critical_count: int
    warning_count: int
    info_count: int


def compute_score(findings: list[Finding], model_count: int) -> ScoreResult:
    if model_count == 0:
        return ScoreResult(score=100, critical_count=0, warning_count=0, info_count=0)

    raw_deduction = 0.0
    critical = warning = info = 0

    for f in findings:
        raw_deduction += f.weight * SEVERITY_MULTIPLIER[f.severity]
        if f.severity == Severity.CRITICAL:
            critical += 1
        elif f.severity == Severity.WARNING:
            warning += 1
        else:
            info += 1

    # Normalize deduction against project size so a 500-model project
    # isn't punished more harshly than a 20-model project for having
    # proportionally the same number of issues. The *4 factor was tuned
    # so a project where ~half the models have real, unaddressed issues
    # lands in the 60-80 range rather than flooring to 0.
    normalized_deduction = raw_deduction / max(1, model_count) * 4

    score = max(0, min(100, round(100 - normalized_deduction)))
    return ScoreResult(score=score, critical_count=critical, warning_count=warning, info_count=info)
