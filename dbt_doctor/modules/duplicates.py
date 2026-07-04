"""
Duplicate logic module — the module that differentiates dbt-doctor from a
plain linter.

Parses each model's raw SQL into an AST with sqlglot, extracts every
CASE-WHEN expression, normalizes it (whitespace/case-insensitive, literal
values kept since they carry business meaning e.g. status='paid'), and
hashes it. Any normalized expression that shows up 2+ times across the
project is flagged as logic that should probably live in a macro.

sqlglot is used as a *best-effort* parser: dbt SQL often contains Jinja
({{ ref(...) }}, {% if %} etc.) that isn't valid raw SQL. We strip common
Jinja patterns before parsing, and any model that still fails to parse is
silently skipped rather than raising — this module is a heuristic aid,
not a correctness guarantee.
"""

from __future__ import annotations

import re
from collections import defaultdict

import sqlglot
from sqlglot import expressions as exp

from dbt_doctor.findings import Finding, Severity
from dbt_doctor.parser import DbtProject

MIN_OCCURRENCES = 2
JINJA_PATTERN = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)


def _strip_jinja(sql: str) -> str:
    # Replace {{ ref('x') }} / {{ source(...) }} / config blocks etc. with
    # a harmless placeholder identifier so the surrounding SQL still parses.
    return JINJA_PATTERN.sub("__jinja__", sql)


def _extract_case_fingerprints(sql: str) -> list[str]:
    cleaned = _strip_jinja(sql)
    try:
        tree = sqlglot.parse_one(cleaned, error_level=None)
    except Exception:
        return []
    if tree is None:
        return []

    fingerprints = []
    for case_expr in tree.find_all(exp.Case):
        try:
            normalized = case_expr.sql(dialect=None, normalize=True).lower()
            normalized = re.sub(r"\s+", " ", normalized).strip()
        except Exception:
            continue
        if len(normalized) < 20:
            # trivial one-branch CASE statements aren't worth flagging
            continue
        fingerprints.append(normalized)
    return fingerprints


def analyze(project: DbtProject) -> list[Finding]:
    occurrences: dict[str, list[str]] = defaultdict(list)  # fingerprint -> [model names]

    for uid, model in project.models.items():
        sql = model.raw_code or model.compiled_code
        if not sql.strip():
            continue
        for fingerprint in _extract_case_fingerprints(sql):
            occurrences[fingerprint].append(model.name)

    findings: list[Finding] = []
    for fingerprint, model_names in occurrences.items():
        if len(model_names) < MIN_OCCURRENCES:
            continue
        preview = fingerprint if len(fingerprint) <= 90 else fingerprint[:87] + "..."
        findings.append(
            Finding(
                module="duplicates",
                severity=Severity.WARNING,
                subject=", ".join(sorted(set(model_names))),
                message=f"Repeated CASE expression found in {len(model_names)} models.",
                detail=preview,
                suggestion="Move this into a macro and reference it instead of repeating the logic.",
                weight=min(3.0, 0.5 * len(model_names)),
                meta={"occurrence_count": len(model_names)},
            )
        )

    findings.sort(key=lambda f: f.meta.get("occurrence_count", 0), reverse=True)
    return findings
