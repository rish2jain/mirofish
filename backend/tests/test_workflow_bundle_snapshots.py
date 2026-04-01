"""Snapshot index and diff loading for workflow_bundle."""

import json
import os
import tempfile
import uuid
from unittest.mock import patch

import pytest

from app.services import workflow_bundle as wb


def _fake_project_dir(tmp: str, project_id: str) -> str:
    d = os.path.join(tmp, "projects", project_id)
    os.makedirs(d, exist_ok=True)
    return d


def test_list_graph_snapshots_skips_index_file():
    with tempfile.TemporaryDirectory() as tmp:
        pid = "p_" + uuid.uuid4().hex[:8]
        snap_d = os.path.join(_fake_project_dir(tmp, pid), "graph_snapshots")
        os.makedirs(snap_d, exist_ok=True)
        rec = {
            "id": "snap_abc123",
            "label": "L1",
            "graph_id": "g1",
            "created_at": "2020-01-01T00:00:00",
            "node_ids": [],
            "edges": [],
        }
        with open(os.path.join(snap_d, "snap_abc123.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f)
        with open(os.path.join(snap_d, wb.SNAPSHOTS_INDEX_FILENAME), "w", encoding="utf-8") as f:
            json.dump({"by_id": {}, "by_label": {}}, f)

        with patch.object(wb.ProjectManager, "get_project_dir", return_value=os.path.join(tmp, "projects", pid)):
            out = wb.list_graph_snapshots(pid)
        assert len(out) == 1
        assert out[0]["id"] == "snap_abc123"


def test_diff_by_label_uses_index_without_directory_scan_count():
    with tempfile.TemporaryDirectory() as tmp:
        pid = "p_" + uuid.uuid4().hex[:8]
        snap_d = os.path.join(_fake_project_dir(tmp, pid), "graph_snapshots")
        os.makedirs(snap_d, exist_ok=True)
        for i, sid in enumerate(["snap_aaa111", "snap_bbb222"]):
            rec = {
                "id": sid,
                "label": f"label_{i}",
                "graph_id": "g1",
                "created_at": "2020-01-01T00:00:00",
                "node_ids": [str(i)],
                "edges": [],
            }
            with open(os.path.join(snap_d, f"{sid}.json"), "w", encoding="utf-8") as f:
                json.dump(rec, f)
        wb._write_snapshots_index(
            snap_d,
            {"snap_aaa111": "snap_aaa111.json", "snap_bbb222": "snap_bbb222.json"},
            {"label_0": "snap_aaa111.json", "label_1": "snap_bbb222.json"},
        )

        orig_listdir = os.listdir

        def wrapped_listdir(path):
            if path == snap_d:
                raise AssertionError("diff_graph_snapshots should not scan directory when index resolves labels")
            return orig_listdir(path)

        with (
            patch.object(wb.ProjectManager, "get_project_dir", return_value=os.path.join(tmp, "projects", pid)),
            patch("os.listdir", side_effect=wrapped_listdir),
        ):
            diff = wb.diff_graph_snapshots(pid, "label_0", "label_1")

        assert diff["snapshot_a"] == "snap_aaa111"
        assert diff["snapshot_b"] == "snap_bbb222"
        assert diff["nodes_added"] == ["1"]
        assert diff["nodes_removed"] == ["0"]


def test_save_graph_snapshot_updates_index():
    with tempfile.TemporaryDirectory() as tmp:
        pid = "p_" + uuid.uuid4().hex[:8]
        _fake_project_dir(tmp, pid)
        project = type("P", (), {})()
        project.project_id = pid
        project.graph_id = "graph_test123"

        with (
            patch.object(wb.ProjectManager, "get_project_dir", return_value=os.path.join(tmp, "projects", pid)),
            patch.object(wb.ProjectManager, "get_project", return_value=project),
            patch.object(wb.GraphBuilderService, "get_graph_data", return_value={"nodes": [], "edges": []}),
        ):
            rec = wb.save_graph_snapshot(pid, "my_label")

        snap_d = os.path.join(tmp, "projects", pid, "graph_snapshots")
        idx_path = os.path.join(snap_d, wb.SNAPSHOTS_INDEX_FILENAME)
        assert os.path.isfile(idx_path)
        with open(idx_path, encoding="utf-8") as f:
            idx = json.load(f)
        fn = f"{rec['id']}.json"
        assert idx["by_id"][rec["id"]] == fn
        assert idx["by_label"]["my_label"] == fn


def test_missing_index_rebuilt_on_diff():
    with tempfile.TemporaryDirectory() as tmp:
        pid = "p_" + uuid.uuid4().hex[:8]
        snap_d = os.path.join(_fake_project_dir(tmp, pid), "graph_snapshots")
        os.makedirs(snap_d, exist_ok=True)
        pairs = [("snap_x1", "Alpha"), ("snap_x2", "Beta")]
        for sid, lbl in pairs:
            rec = {
                "id": sid,
                "label": lbl,
                "graph_id": "g1",
                "created_at": "2020-01-01T00:00:00",
                "node_ids": [],
                "edges": [],
            }
            with open(os.path.join(snap_d, f"{sid}.json"), "w", encoding="utf-8") as f:
                json.dump(rec, f)

        with patch.object(wb.ProjectManager, "get_project_dir", return_value=os.path.join(tmp, "projects", pid)):
            wb.diff_graph_snapshots(pid, "Alpha", "Beta")

        assert os.path.isfile(os.path.join(snap_d, wb.SNAPSHOTS_INDEX_FILENAME))


def test_diff_corrupt_direct_path_json_raises_valueerror_with_sid_and_file():
    with tempfile.TemporaryDirectory() as tmp:
        pid = "p_" + uuid.uuid4().hex[:8]
        snap_d = os.path.join(_fake_project_dir(tmp, pid), "graph_snapshots")
        os.makedirs(snap_d, exist_ok=True)
        with open(os.path.join(snap_d, "snap_corrupt.json"), "w", encoding="utf-8") as f:
            f.write("{ not json")
        rec_ok = {
            "id": "snap_ok",
            "label": "ok",
            "graph_id": "g1",
            "created_at": "2020-01-01T00:00:00",
            "node_ids": [],
            "edges": [],
        }
        with open(os.path.join(snap_d, "snap_ok.json"), "w", encoding="utf-8") as f:
            json.dump(rec_ok, f)
        with patch.object(wb.ProjectManager, "get_project_dir", return_value=os.path.join(tmp, "projects", pid)):
            with pytest.raises(ValueError, match="snap_corrupt") as exc_info:
                wb.diff_graph_snapshots(pid, "snap_corrupt", "snap_ok")
        assert "snap_corrupt.json" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


def test_diff_corrupt_index_resolved_json_raises_valueerror_with_sid_and_file():
    with tempfile.TemporaryDirectory() as tmp:
        pid = "p_" + uuid.uuid4().hex[:8]
        snap_d = os.path.join(_fake_project_dir(tmp, pid), "graph_snapshots")
        os.makedirs(snap_d, exist_ok=True)
        with open(os.path.join(snap_d, "bad_body.json"), "w", encoding="utf-8") as f:
            f.write("not { valid")
        rec_ok = {
            "id": "snap_ok",
            "label": "ok",
            "graph_id": "g1",
            "created_at": "2020-01-01T00:00:00",
            "node_ids": [],
            "edges": [],
        }
        with open(os.path.join(snap_d, "snap_ok.json"), "w", encoding="utf-8") as f:
            json.dump(rec_ok, f)
        wb._write_snapshots_index(snap_d, {}, {"BrokenLabel": "bad_body.json"})
        with patch.object(wb.ProjectManager, "get_project_dir", return_value=os.path.join(tmp, "projects", pid)):
            with pytest.raises(ValueError, match="BrokenLabel") as exc_info:
                wb.diff_graph_snapshots(pid, "snap_ok", "BrokenLabel")
        assert "bad_body.json" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)
