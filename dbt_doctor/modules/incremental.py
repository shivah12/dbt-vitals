"""
Incremental-model candidate detection.

Requires catalog.json (row counts come from the warehouse, not the
manifest). If catalog data wasn't loaded, this module returns no findings
rather than guessing.

Heuristic: any model materialized as "table" (not "incremental" or "view")
with a row count above ROW_COUNT_THRESHOLD is flagged. This is intentionally
simple — a true cost/runtime estimate needs warehouse-specific query plans,
which is out of scope for a static analyzer.
"""

from __future__ import annotations

from dbt_doctor.findings import Finding, Severity
from dbt_doctor.parser import DbtProject

ROW_COUNT_THRESHOLD = 10_000_000


def analyze(project: DbtProject, catalog_loaded: bool) -> list[Finding]:
    if not catalog_loaded:
        return []

    findings: list[Finding] = []
    for uid, model in project.models.items():
        if model.materialized not in ("table", None):
            continue
        if model.row_count is None or model.row_count < ROW_COUNT_THRESHOLD:
            continue
        findings.append(
            Finding(
                module="incremental",
                severity=Severity.WARNING,
                subject=model.name,
                message=f"Large table model ({model.row_count:,} rows) materialized as full table rebuild.",
                suggestion="Consider materialized='incremental' with an appropriate unique_key and is_incremental() filter.",
                weight=1.5,
            )
        )
    return findings
