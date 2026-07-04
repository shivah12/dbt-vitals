from pathlib import Path

import pytest

from dbt_doctor.graph import build_model_graph
from dbt_doctor.modules import documentation, duplicates, incremental, lineage, testing
from dbt_doctor.parser import load_catalog, load_manifest
from dbt_doctor.scoring import compute_score

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.fixture
def project():
    return load_manifest(EXAMPLES_DIR / "sample_manifest.json")


@pytest.fixture
def project_with_catalog(project):
    load_catalog(EXAMPLES_DIR / "sample_catalog.json", project)
    return project


def test_load_manifest_parses_models(project):
    assert len(project.models) == 5
    assert "model.demo.fct_orders" in project.models


def test_load_manifest_parses_tests(project):
    assert len(project.tests) == 2


def test_graph_builds_correct_edges(project):
    graph = build_model_graph(project)
    assert graph.has_edge("model.demo.stg_orders", "model.demo.fct_orders")
    assert graph.has_edge("model.demo.stg_orders", "model.demo.dim_customer")


def test_lineage_flags_untested_dead_model(project):
    graph = build_model_graph(project)
    findings = lineage.analyze(project, graph)
    subjects = {f.subject for f in findings}
    # new_table2 has no downstream deps, isn't a mart -> should be flagged
    assert "new_table2" in subjects


def test_lineage_no_cycles_in_clean_project(project):
    graph = build_model_graph(project)
    findings = lineage.analyze(project, graph)
    assert not any("Circular" in f.message for f in findings)


def test_testing_flags_untested_models(project):
    findings = testing.analyze(project)
    subjects = {f.subject for f in findings}
    # dim_customer and stg_orders have no unique/not_null tests attached
    assert "dim_customer" in subjects
    assert "stg_orders" in subjects
    # fct_orders has both unique + not_null -> should not appear
    assert "fct_orders" not in subjects


def test_duplicates_detects_repeated_case_statement(project):
    findings = duplicates.analyze(project)
    assert len(findings) >= 1
    assert findings[0].meta["occurrence_count"] >= 2


def test_documentation_coverage_math(project):
    coverage, findings = documentation.analyze(project)
    assert coverage.total_models == 5
    assert coverage.documented_models == 2  # stg_orders, fct_orders have descriptions
    assert 0 <= coverage.model_coverage_pct <= 100


def test_incremental_requires_catalog(project):
    # No catalog loaded -> no findings, not an error
    findings = incremental.analyze(project, catalog_loaded=False)
    assert findings == []


def test_incremental_flags_large_table_model(project_with_catalog):
    findings = incremental.analyze(project_with_catalog, catalog_loaded=True)
    subjects = {f.subject for f in findings}
    assert "fct_orders" in subjects  # 54M rows, materialized=table
    assert "dim_customer" not in subjects  # only 120k rows


def test_score_is_between_0_and_100(project):
    graph = build_model_graph(project)
    findings = []
    findings += lineage.analyze(project, graph)
    findings += testing.analyze(project)
    findings += duplicates.analyze(project)
    _, doc_findings = documentation.analyze(project)
    findings += doc_findings

    result = compute_score(findings, model_count=len(project.models))
    assert 0 <= result.score <= 100


def test_score_is_100_for_empty_project():
    result = compute_score([], model_count=0)
    assert result.score == 100
