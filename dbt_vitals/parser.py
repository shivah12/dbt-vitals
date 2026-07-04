"""
Loads dbt's manifest.json and catalog.json artifacts and normalizes them
into simple, version-agnostic Python objects that the rest of dbt-doctor
works with.

Both files are produced by:
    dbt compile   -> manifest.json (always)
    dbt docs generate -> manifest.json + catalog.json (catalog needs a
                          warehouse connection since it introspects
                          actual table stats/columns)

catalog.json is optional. Modules that depend on it (e.g. incremental
candidate detection, which needs row counts) degrade gracefully if it's
missing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class ManifestNotFoundError(FileNotFoundError):
    pass


@dataclass
class Column:
    name: str
    description: str = ""
    data_type: Optional[str] = None


@dataclass
class Node:
    unique_id: str
    name: str
    resource_type: str  # "model", "test", "source", "seed", "snapshot", etc.
    package_name: str = ""
    path: str = ""
    description: str = ""
    materialized: Optional[str] = None
    raw_code: str = ""
    compiled_code: str = ""
    depends_on: list[str] = field(default_factory=list)
    columns: dict[str, Column] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    # test-specific
    test_metadata_name: Optional[str] = None  # e.g. "unique", "not_null"
    tested_column: Optional[str] = None
    attached_node: Optional[str] = None
    # catalog-derived (optional)
    row_count: Optional[int] = None
    size_bytes: Optional[int] = None


@dataclass
class DbtProject:
    nodes: dict[str, Node] = field(default_factory=dict)
    sources: dict[str, Node] = field(default_factory=dict)

    @property
    def models(self) -> dict[str, Node]:
        return {k: v for k, v in self.nodes.items() if v.resource_type == "model"}

    @property
    def tests(self) -> dict[str, Node]:
        return {k: v for k, v in self.nodes.items() if v.resource_type == "test"}

    @property
    def macros(self) -> dict[str, Node]:
        return {k: v for k, v in self.nodes.items() if v.resource_type == "macro"}


def _extract_columns(raw_columns: dict[str, Any]) -> dict[str, Column]:
    cols = {}
    for col_name, col_data in (raw_columns or {}).items():
        cols[col_name] = Column(
            name=col_data.get("name", col_name),
            description=col_data.get("description", "") or "",
            data_type=col_data.get("data_type"),
        )
    return cols


def load_manifest(manifest_path: Path) -> DbtProject:
    if not manifest_path.exists():
        raise ManifestNotFoundError(
            f"No manifest.json found at {manifest_path}. "
            "Run `dbt compile` or `dbt docs generate` first."
        )

    raw = json.loads(manifest_path.read_text())
    project = DbtProject()

    raw_nodes = {**raw.get("nodes", {}), **raw.get("macros", {})}
    for uid, data in raw_nodes.items():
        depends_on = data.get("depends_on", {}).get("nodes", [])
        test_metadata = data.get("test_metadata") or {}
        node = Node(
            unique_id=uid,
            name=data.get("name", uid),
            resource_type=data.get("resource_type", "unknown"),
            package_name=data.get("package_name", ""),
            path=data.get("path", ""),
            description=data.get("description", "") or "",
            materialized=(data.get("config") or {}).get("materialized"),
            raw_code=data.get("raw_code", "") or data.get("raw_sql", "") or "",
            compiled_code=data.get("compiled_code", "") or data.get("compiled_sql", "") or "",
            depends_on=depends_on,
            columns=_extract_columns(data.get("columns", {})),
            tags=data.get("tags", []) or [],
            test_metadata_name=test_metadata.get("name"),
            tested_column=(test_metadata.get("kwargs") or {}).get("column_name"),
            attached_node=data.get("attached_node"),
        )
        project.nodes[uid] = node

    for uid, data in raw.get("sources", {}).items():
        project.sources[uid] = Node(
            unique_id=uid,
            name=data.get("name", uid),
            resource_type="source",
            description=data.get("description", "") or "",
        )

    return project


def load_catalog(catalog_path: Path, project: DbtProject) -> bool:
    """Enriches `project` nodes in-place with catalog stats (row counts,
    byte size) when available. Returns True if catalog data was applied."""
    if not catalog_path.exists():
        return False

    raw = json.loads(catalog_path.read_text())
    catalog_nodes = raw.get("nodes", {})

    for uid, data in catalog_nodes.items():
        node = project.nodes.get(uid)
        if node is None:
            continue
        stats = data.get("stats", {})
        row_count_stat = stats.get("row_count") or stats.get("num_rows")
        size_stat = stats.get("num_bytes") or stats.get("bytes")
        if row_count_stat and isinstance(row_count_stat, dict):
            node.row_count = _safe_int(row_count_stat.get("value"))
        if size_stat and isinstance(size_stat, dict):
            node.size_bytes = _safe_int(size_stat.get("value"))

    return True


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
