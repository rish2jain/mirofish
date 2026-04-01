"""Versioned project + graph export/import and graph snapshots."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from ..config import Config
from ..models.project import ProjectManager, ProjectStatus
from .graph_builder import GraphBuilderService
from .graph_storage import get_app_graph_storage, JSONStorage, KuzuDBStorage, StorageError


BUNDLE_VERSION = 1

# Sidecar index: maps snapshot id and label to snapshot filename (not the index file itself).
SNAPSHOTS_INDEX_FILENAME = "snapshots_index.json"

# Bundle import limits (defense in depth for untrusted uploads).
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
CHUNK_SIZE_MIN = 1
CHUNK_SIZE_MAX = 10_000
IMPORT_MAX_GRAPH_NODES = 250_000
IMPORT_MAX_GRAPH_EDGES = 1_000_000


def _snapshots_dir(project_id: str) -> str:
    # Defensive check against path traversal
    if not project_id or ".." in project_id or "/" in project_id or "\\" in project_id:
        raise ValueError(f"Invalid project_id: {project_id}")
    d = os.path.join(ProjectManager.get_project_dir(project_id), "graph_snapshots")
    os.makedirs(d, exist_ok=True)
    return d


def build_export_bundle(project_id: str) -> Dict[str, Any]:
    project = ProjectManager.get_project(project_id)
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    pd = project.to_dict()
    bundle: Dict[str, Any] = {
        "bundle_version": BUNDLE_VERSION,
        "exported_at": datetime.now().isoformat(),
        "project": {k: v for k, v in pd.items() if k != "project_id"},
    }
    if project.graph_id:
        builder = GraphBuilderService()
        bundle["graph_data"] = builder.get_graph_data(project.graph_id)
    return bundle


def _node_from_api_dict(n: Dict[str, Any]) -> Dict[str, Any]:
    labels = n.get("labels") or ["Entity"]
    label = labels[-1] if labels else "Entity"
    nid = n.get("uuid") or n.get("id")
    return {
        "id": str(nid),
        "name": str(n.get("name", "")),
        "label": str(label),
        "summary": str(n.get("summary", "") or ""),
        "facts": n.get("facts") if isinstance(n.get("facts"), list) else [],
        "attributes": n.get("attributes") if isinstance(n.get("attributes"), dict) else {},
        "created_at": str(n.get("created_at", "") or ""),
        "updated_at": str(n.get("updated_at", "") or n.get("created_at", "") or ""),
    }


def _parse_import_chunk_size(raw: Any) -> int:
    if raw is None or raw == "":
        return DEFAULT_CHUNK_SIZE
    if isinstance(raw, bool):
        return DEFAULT_CHUNK_SIZE
    if isinstance(raw, float) and not raw.is_integer():
        return DEFAULT_CHUNK_SIZE
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_CHUNK_SIZE
    if v < CHUNK_SIZE_MIN or v > CHUNK_SIZE_MAX:
        raise ValueError(
            f"Imported bundle project.chunk_size must be between {CHUNK_SIZE_MIN} and {CHUNK_SIZE_MAX} (got {v})"
        )
    return v


def _parse_import_chunk_overlap(raw: Any, chunk_size: int) -> int:
    max_ov = max(0, chunk_size - 1)
    default = min(DEFAULT_CHUNK_OVERLAP, max_ov)
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool):
        return default
    if isinstance(raw, float) and not raw.is_integer():
        return default
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return default
    if v < 0 or v >= chunk_size:
        raise ValueError(
            f"Imported bundle project.chunk_overlap must be >= 0 and less than chunk_size ({chunk_size}); got {v}"
        )
    return v


def _nonempty_id(raw: Any) -> bool:
    if raw is None:
        return False
    if isinstance(raw, bool):
        return False
    return bool(str(raw).strip())


def _validate_bundle_graph_lists(graph_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    nodes = graph_data.get("nodes")
    edges = graph_data.get("edges")
    if nodes is None:
        nodes = []
    if edges is None:
        edges = []
    if not isinstance(nodes, list):
        raise StorageError("graph_data.nodes must be a list")
    if not isinstance(edges, list):
        raise StorageError("graph_data.edges must be a list")
    if len(nodes) > IMPORT_MAX_GRAPH_NODES:
        raise StorageError(
            f"graph_data.nodes exceeds import limit ({IMPORT_MAX_GRAPH_NODES} nodes, got {len(nodes)})"
        )
    if len(edges) > IMPORT_MAX_GRAPH_EDGES:
        raise StorageError(
            f"graph_data.edges exceeds import limit ({IMPORT_MAX_GRAPH_EDGES} edges, got {len(edges)})"
        )
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            raise StorageError(f"graph_data.nodes[{i}] must be an object")
        if not _nonempty_id(n.get("uuid") or n.get("id")):
            raise StorageError(f"graph_data.nodes[{i}] requires a non-empty id or uuid")
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            raise StorageError(f"graph_data.edges[{i}] must be an object")
        if not _nonempty_id(e.get("uuid") or e.get("id")):
            raise StorageError(f"graph_data.edges[{i}] requires a non-empty id or uuid")
        src = e.get("source_node_uuid") or e.get("source_id")
        tgt = e.get("target_node_uuid") or e.get("target_id")
        if not _nonempty_id(src):
            raise StorageError(f"graph_data.edges[{i}] requires source_node_uuid or source_id")
        if not _nonempty_id(tgt):
            raise StorageError(f"graph_data.edges[{i}] requires target_node_uuid or target_id")
        w = e.get("weight", 1.0)
        try:
            float(w if w is not None else 1.0)
        except (TypeError, ValueError):
            raise StorageError(f"graph_data.edges[{i}] has invalid weight (must be numeric)")
    return nodes, edges


def _edge_from_api_dict(e: Dict[str, Any]) -> Dict[str, Any]:
    eid = e.get("uuid") or e.get("id")
    raw_weight = e.get("weight")
    weight = 1.0 if raw_weight is None else float(raw_weight)
    return {
        "id": str(eid),
        "source_id": str(e.get("source_node_uuid") or e.get("source_id", "")),
        "target_id": str(e.get("target_node_uuid") or e.get("target_id", "")),
        "relation": str(e.get("name") or e.get("fact_type") or e.get("relation", "")),
        "weight": weight,
        "fact": str(e.get("fact", "") or ""),
        "attributes": e.get("attributes") if isinstance(e.get("attributes"), dict) else {},
        "created_at": str(e.get("created_at", "") or ""),
        "valid_at": e.get("valid_at"),
        "invalid_at": e.get("invalid_at"),
        "expired_at": e.get("expired_at"),
        "episodes": e.get("episodes") if isinstance(e.get("episodes"), list) else [],
    }


def _import_graph_to_storage(
    project: Any,
    graph_data: Dict[str, Any],
    expected_storage_type: Type[Union[KuzuDBStorage, JSONStorage]],
) -> str:
    """Validate bundle graph lists, create storage, import nodes/edges, persist project."""
    nodes, edges = _validate_bundle_graph_lists(graph_data)
    graph_id = f"graph_{uuid.uuid4().hex[:12]}"
    storage = get_app_graph_storage(graph_id)
    if not isinstance(storage, expected_storage_type):
        if expected_storage_type is KuzuDBStorage:
            raise StorageError("Import graph requires Kuzu backend")
        raise StorageError("JSON graph backend expected")
    for n in nodes:
        storage.add_node(_node_from_api_dict(n))
    for e in edges:
        storage.add_edge(_edge_from_api_dict(e))
    project.graph_id = graph_id
    project.status = ProjectStatus.GRAPH_COMPLETED
    ProjectManager.save_project(project)
    return graph_id


def import_bundle(data: Dict[str, Any], owner_user_id: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Create a new project from a bundle. Returns (project_id, graph_id or None).
    """
    ver = data.get("bundle_version")
    if ver != BUNDLE_VERSION:
        raise ValueError(f"Unsupported bundle_version (expected {BUNDLE_VERSION})")

    pd = data.get("project") or {}
    chunk_size = _parse_import_chunk_size(pd.get("chunk_size"))
    chunk_overlap = _parse_import_chunk_overlap(pd.get("chunk_overlap"), chunk_size)
    name = pd.get("name") or "Imported project"
    project = ProjectManager.create_project(name=name, owner_user_id=owner_user_id)

    project.ontology = pd.get("ontology")
    project.analysis_summary = pd.get("analysis_summary")
    project.simulation_requirement = pd.get("simulation_requirement")
    project.chunk_size = chunk_size
    project.chunk_overlap = chunk_overlap
    if project.ontology:
        project.status = ProjectStatus.ONTOLOGY_GENERATED
    ProjectManager.save_project(project)

    graph_data = data.get("graph_data")
    graph_id: Optional[str] = None
    if graph_data is not None:
        if not isinstance(graph_data, dict):
            raise StorageError("graph_data must be an object")
        if graph_data:
            if Config.GRAPH_BACKEND == "kuzu":
                graph_id = _import_graph_to_storage(project, graph_data, KuzuDBStorage)
            elif Config.GRAPH_BACKEND == "json":
                graph_id = _import_graph_to_storage(project, graph_data, JSONStorage)

    return project.project_id, graph_id


def _snapshots_index_path(d: str) -> str:
    return os.path.join(d, SNAPSHOTS_INDEX_FILENAME)


def _read_snapshots_index_raw(d: str) -> Optional[Dict[str, Any]]:
    p = _snapshots_index_path(d)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_snapshots_index(d: str, by_id: Dict[str, str], by_label: Dict[str, str]) -> None:
    data = {
        "by_id": by_id,
        "by_label": by_label,
        "updated_at": datetime.now().isoformat(),
    }
    with open(_snapshots_index_path(d), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _rebuild_snapshots_index(d: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    by_id: Dict[str, str] = {}
    by_label: Dict[str, str] = {}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json") or fn == SNAPSHOTS_INDEX_FILENAME:
            continue
        path = os.path.join(d, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        sid = doc.get("id")
        if sid:
            by_id[str(sid)] = fn
        lbl = doc.get("label")
        if lbl is not None and str(lbl) != "":
            by_label[str(lbl)] = fn
    _write_snapshots_index(d, by_id, by_label)
    return by_id, by_label


def _upsert_snapshot_index(d: str, snap_id: str, label: str, filename: str) -> None:
    raw = _read_snapshots_index_raw(d)
    if raw is None:
        by_id, by_label = _rebuild_snapshots_index(d)
    else:
        by_id = dict(raw.get("by_id") or {})
        by_label = dict(raw.get("by_label") or {})
    by_id[snap_id] = filename
    by_label[str(label)] = filename
    _write_snapshots_index(d, by_id, by_label)


def _scan_find_snapshot_doc(d: str, sid: str) -> Optional[Dict[str, Any]]:
    for fn in os.listdir(d):
        if not fn.endswith(".json") or fn == SNAPSHOTS_INDEX_FILENAME:
            continue
        try:
            with open(os.path.join(d, fn), "r", encoding="utf-8") as f:
                doc = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if doc.get("id") == sid or doc.get("label") == sid:
            return doc
    return None


def save_graph_snapshot(project_id: str, label: str) -> Dict[str, Any]:
    project = ProjectManager.get_project(project_id)
    if not project:
        raise ValueError(f"Project not found: {project_id}")
    if not project.graph_id:
        raise ValueError("Project has no graph_id")

    builder = GraphBuilderService()
    data = builder.get_graph_data(project.graph_id)
    node_ids = sorted(str(n.get("uuid") or n.get("id", "")) for n in data.get("nodes", []))
    edges_compact = []
    for e in data.get("edges", []):
        edges_compact.append(
            [
                str(e.get("source_node_uuid") or e.get("source_id", "")),
                str(e.get("target_node_uuid") or e.get("target_id", "")),
                str(e.get("name") or e.get("relation", "")),
            ]
        )
    edges_compact.sort()
    snap_id = f"snap_{uuid.uuid4().hex[:10]}"
    record = {
        "id": snap_id,
        "label": label,
        "graph_id": project.graph_id,
        "created_at": datetime.now().isoformat(),
        "node_ids": node_ids,
        "edges": edges_compact,
    }
    d = _snapshots_dir(project_id)
    path = os.path.join(d, f"{snap_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    _upsert_snapshot_index(d, snap_id, label, f"{snap_id}.json")
    return record


def list_graph_snapshots(project_id: str) -> List[Dict[str, Any]]:
    d = _snapshots_dir(project_id)
    out = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json") or fn == SNAPSHOTS_INDEX_FILENAME:
            continue
        try:
            with open(os.path.join(d, fn), "r", encoding="utf-8") as f:
                out.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def diff_graph_snapshots(project_id: str, snapshot_a: str, snapshot_b: str) -> Dict[str, Any]:
    d = _snapshots_dir(project_id)

    def _load(sid: str) -> Dict[str, Any]:
        path = os.path.join(d, f"{sid}.json")
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid snapshot JSON for snapshot {sid!r} (file: {os.path.basename(path)!r})"
                ) from e
        raw = _read_snapshots_index_raw(d)
        if raw:
            by_id = raw.get("by_id") or {}
            by_label = raw.get("by_label") or {}
            fn = by_id.get(sid) or by_label.get(sid)
            if fn and fn != SNAPSHOTS_INDEX_FILENAME:
                ip = os.path.join(d, fn)
                if os.path.isfile(ip):
                    try:
                        with open(ip, "r", encoding="utf-8") as f:
                            return json.load(f)
                    except json.JSONDecodeError as e:
                        raise ValueError(
                            f"Invalid snapshot JSON for snapshot {sid!r} (file: {fn!r})"
                        ) from e
        doc = _scan_find_snapshot_doc(d, sid)
        if doc is None:
            raise ValueError(f"Snapshot not found: {sid}")
        _rebuild_snapshots_index(d)
        return doc

    a = _load(snapshot_a)
    b = _load(snapshot_b)
    set_a, set_b = set(a.get("node_ids", [])), set(b.get("node_ids", []))
    ea = {tuple(x) for x in (a.get("edges") or [])}
    eb = {tuple(x) for x in (b.get("edges") or [])}
    return {
        "snapshot_a": a.get("id"),
        "snapshot_b": b.get("id"),
        "nodes_added": sorted(set_b - set_a),
        "nodes_removed": sorted(set_a - set_b),
        "edges_added": [list(x) for x in sorted(eb - ea)],
        "edges_removed": [list(x) for x in sorted(ea - eb)],
    }
