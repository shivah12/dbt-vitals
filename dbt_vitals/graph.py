"""Builds a directed dependency graph of models from a parsed DbtProject."""

from __future__ import annotations

import networkx as nx

from dbt_vitals.parser import DbtProject


def build_model_graph(project: DbtProject) -> nx.DiGraph:
    """Nodes = model unique_ids. Edge A -> B means B depends on A
    (A feeds into B), matching dbt's own lineage direction."""
    graph = nx.DiGraph()

    for uid, node in project.models.items():
        graph.add_node(uid, name=node.name, path=node.path)

    for uid, node in project.models.items():
        for dep in node.depends_on:
            if dep in project.models:
                graph.add_edge(dep, uid)

    return graph


def models_referenced_by_tests_or_exposures(project: DbtProject) -> set[str]:
    """Models that have at least one test attached to them - used as a
    signal that a model is intentionally a checked, "real" asset."""
    referenced = set()
    for test in project.tests.values():
        for dep in test.depends_on:
            referenced.add(dep)
    return referenced
