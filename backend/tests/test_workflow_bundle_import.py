"""import_bundle validation and sanitization."""

import os
import tempfile
import uuid
from unittest.mock import patch

import pytest

from app.models.project import ProjectManager
from app.services.graph_storage import JSONStorage, StorageError
from app.services import workflow_bundle as wb


def _bundle_base():
    return {
        "bundle_version": wb.BUNDLE_VERSION,
        "project": {"name": "T"},
    }


def test_import_chunk_size_out_of_range_raises():
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(wb.Config, "UPLOAD_FOLDER", tmp):
            b = _bundle_base()
            b["project"]["chunk_size"] = wb.CHUNK_SIZE_MAX + 1
            with pytest.raises(ValueError, match="chunk_size"):
                wb.import_bundle(b)


def test_import_chunk_overlap_out_of_range_raises():
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(wb.Config, "UPLOAD_FOLDER", tmp):
            b = _bundle_base()
            b["project"]["chunk_size"] = 100
            b["project"]["chunk_overlap"] = 100
            with pytest.raises(ValueError, match="chunk_overlap"):
                wb.import_bundle(b)


def test_import_malformed_chunk_fields_use_defaults():
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(wb.Config, "UPLOAD_FOLDER", tmp):
            b = _bundle_base()
            b["project"]["chunk_size"] = "not-an-int"
            b["project"]["chunk_overlap"] = {}
            pid, _ = wb.import_bundle(b)
            p = ProjectManager.get_project(pid)
            assert p.chunk_size == wb.DEFAULT_CHUNK_SIZE
            assert p.chunk_overlap == wb.DEFAULT_CHUNK_OVERLAP


def test_import_graph_data_not_object_raises():
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(wb.Config, "UPLOAD_FOLDER", tmp), patch.object(wb.Config, "GRAPH_BACKEND", "json"):
            b = _bundle_base()
            b["graph_data"] = []
            with pytest.raises(StorageError, match="graph_data must be an object"):
                wb.import_bundle(b)


def test_import_graph_node_missing_id_raises():
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(wb.Config, "UPLOAD_FOLDER", tmp), patch.object(wb.Config, "GRAPH_BACKEND", "json"):
            b = _bundle_base()
            b["graph_data"] = {
                "nodes": [{"name": "x"}],
                "edges": [],
            }
            with pytest.raises(StorageError, match="nodes\\[0\\]"):
                wb.import_bundle(b)


def test_import_graph_edge_missing_endpoints_raises():
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(wb.Config, "UPLOAD_FOLDER", tmp), patch.object(wb.Config, "GRAPH_BACKEND", "json"):
            b = _bundle_base()
            b["graph_data"] = {
                "nodes": [{"uuid": "n1", "name": "a"}],
                "edges": [
                    {
                        "uuid": "e1",
                        "source_node_uuid": "n1",
                    }
                ],
            }
            with pytest.raises(StorageError, match="target_node_uuid"):
                wb.import_bundle(b)


def test_import_graph_edge_invalid_weight_raises():
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(wb.Config, "UPLOAD_FOLDER", tmp), patch.object(wb.Config, "GRAPH_BACKEND", "json"):
            b = _bundle_base()
            b["graph_data"] = {
                "nodes": [{"uuid": "n1"}],
                "edges": [
                    {
                        "uuid": "e1",
                        "source_node_uuid": "n1",
                        "target_node_uuid": "n1",
                        "weight": "heavy",
                    }
                ],
            }
            with pytest.raises(StorageError, match="invalid weight"):
                wb.import_bundle(b)


def test_import_graph_node_count_limit():
    with tempfile.TemporaryDirectory() as tmp:
        with (
            patch.object(wb.Config, "UPLOAD_FOLDER", tmp),
            patch.object(wb.Config, "GRAPH_BACKEND", "json"),
            patch.object(wb, "IMPORT_MAX_GRAPH_NODES", 1),
        ):
            b = _bundle_base()
            b["graph_data"] = {
                "nodes": [{"uuid": "a"}, {"uuid": "b"}],
                "edges": [],
            }
            with pytest.raises(StorageError, match="exceeds import limit"):
                wb.import_bundle(b)


def test_import_minimal_graph_json_succeeds():
    with tempfile.TemporaryDirectory() as tmp:
        groot = os.path.join(tmp, "graphs")

        def fake_storage(gid):
            return JSONStorage(os.path.join(groot, gid))

        with (
            patch.object(wb.Config, "UPLOAD_FOLDER", tmp),
            patch.object(wb.Config, "GRAPH_BACKEND", "json"),
            patch.object(wb, "get_app_graph_storage", side_effect=fake_storage),
        ):
            b = _bundle_base()
            b["graph_data"] = {
                "nodes": [{"uuid": "n1", "name": "A", "labels": ["Entity"]}],
                "edges": [
                    {
                        "uuid": str(uuid.uuid4()),
                        "source_node_uuid": "n1",
                        "target_node_uuid": "n1",
                        "name": "REL",
                    }
                ],
            }
            pid, gid = wb.import_bundle(b)
            assert gid is not None
            p = ProjectManager.get_project(pid)
            assert p.graph_id == gid
