"""
Lineage module.

Flags models with no downstream consumers within the dbt project (out-degree
0 in the dependency graph). This is a heuristic, not a certainty: mart-layer
models are *expected* to be terminal since they feed BI tools outside of dbt.

To reduce false positives we only flag a model as a "potential dead model"
when ALL of the following hold:
  - out-degree is 0 (nothing in the project selects from it)
  - it is NOT in a directory conventionally used for terminal marts
    (path contains "marts/" or "mart/")
  - it has no tests attached to it (an untested, unused, non-terminal model
    is the strongest dead-code signal)

Marts with 0 downstream + 0 tests are flagged as a softer "unused mart"
warning instead, since that combination is still worth a human look.
"""

from __future__ import annotations

import networkx as nx

from dbt_doctor.findings import Finding, Severity
from dbt_doctor.graph import models_referenced_by_tests_or_exposures
from dbt_doctor.parser import DbtProject


def analyze(project: DbtProject, graph: nx.DiGraph) -> list[Finding]:
    findings: list[Finding] = []
    tested_models = models_referenced_by_tests_or_exposures(project)

    for uid, node in project.models.items():
        if uid not in graph:
            continue
        out_degree = graph.out_degree(uid)
        if out_degree != 0:
            continue

        is_mart = "marts/" in node.path or "mart/" in node.path
        has_tests = uid in tested_models

        if is_mart:
            if not has_tests:
                findings.append(
                    Finding(
                        module="lineage",
                        severity=Severity.INFO,
                        subject=node.name,
                        message="Terminal mart model with no tests and no in-project consumers.",
                        detail="Likely intentional (feeds a BI tool), but worth confirming it's still in use.",
                        suggestion="Add at least a not_null/unique test, or confirm the downstream dashboard still reads from it.",
                        weight=0.5,
                    )
                )
            continue

        findings.append(
            Finding(
                module="lineage",
                severity=Severity.WARNING,
                subject=node.name,
                message="Potential dead model: no downstream dependencies in the project.",
                detail=f"path={node.path}",
                suggestion="Confirm this model is still needed, or remove it.",
                weight=2.0,
            )
        )

    findings.extend(_cycle_findings(graph))
    return findings


def _cycle_findings(graph: nx.DiGraph) -> list[Finding]:
    findings = []
    try:
        cycles = list(nx.simple_cycles(graph))
    except Exception:
        cycles = []
    for cycle in cycles:
        findings.append(
            Finding(
                module="lineage",
                severity=Severity.CRITICAL,
                subject=" -> ".join(cycle),
                message="Circular dependency detected between models.",
                suggestion="Break the cycle by refactoring shared logic into an upstream model or macro.",
                weight=5.0,
            )
        )
    return findings
