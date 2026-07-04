"""
Testing coverage module.

For every model, checks whether it has at least a `unique` + `not_null`
test on what looks like its primary key column (a column literally named
`id`, or ending in `_id` that matches the model's own name, e.g.
`customer_id` on `dim_customer`). This is a heuristic — dbt has no
first-class concept of "the" primary key in the manifest, so we infer it.
"""

from __future__ import annotations

from dbt_vitals.findings import Finding, Severity
from dbt_vitals.parser import DbtProject

RECOMMENDED_TESTS = ("unique", "not_null")


def _guess_pk_column(model_name: str, columns: dict) -> str | None:
    if "id" in columns:
        return "id"
    stripped = model_name.split("__")[-1]  # handle stg_source__table naming
    for suffix in (stripped, model_name):
        candidate = f"{suffix}_id"
        if candidate in columns:
            return candidate
    for col_name in columns:
        if col_name.endswith("_id"):
            return col_name
    return None


def analyze(project: DbtProject) -> list[Finding]:
    findings: list[Finding] = []

    tests_by_model: dict[str, set[tuple[str, str]]] = {}
    for test in project.tests.values():
        if not test.test_metadata_name or not test.depends_on:
            continue
        for model_uid in test.depends_on:
            tests_by_model.setdefault(model_uid, set()).add(
                (test.test_metadata_name, test.tested_column or "")
            )

    for uid, model in project.models.items():
        existing = tests_by_model.get(uid, set())
        existing_test_names = {t[0] for t in existing}

        pk_col = _guess_pk_column(model.name, model.columns)

        if not existing:
            findings.append(
                Finding(
                    module="testing",
                    severity=Severity.WARNING,
                    subject=model.name,
                    message="No tests defined on this model.",
                    suggestion=(
                        f"Add unique + not_null tests on `{pk_col}`."
                        if pk_col
                        else "Add unique + not_null tests on the primary key column."
                    ),
                    weight=2.0,
                )
            )
            continue

        missing = [t for t in RECOMMENDED_TESTS if t not in existing_test_names]
        if missing and pk_col:
            findings.append(
                Finding(
                    module="testing",
                    severity=Severity.WARNING,
                    subject=model.name,
                    message=f"Missing recommended test(s): {', '.join(missing)} on `{pk_col}`.",
                    weight=1.0 * len(missing),
                )
            )

    return findings
