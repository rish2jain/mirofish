"""report_simulation_index persistence and ReportManager hooks."""

import json
import os
import tempfile
from unittest.mock import patch

from app.config import Config
from app.services.report_manager import ReportManager
from app.services.report_models import Report, ReportStatus
from app.services import report_simulation_index as rsi


def test_index_updates_on_save_and_delete():
    with tempfile.TemporaryDirectory() as tmp:
        reports = os.path.join(tmp, "reports")
        with patch.object(Config, "UPLOAD_FOLDER", tmp), patch.object(
            ReportManager, "REPORTS_DIR", reports
        ):
            r1 = Report(
                report_id="rep_old",
                simulation_id="sim_t",
                graph_id="g1",
                simulation_requirement="",
                status=ReportStatus.COMPLETED,
                created_at="2024-01-01T00:00:00",
            )
            r2 = Report(
                report_id="rep_new",
                simulation_id="sim_t",
                graph_id="g1",
                simulation_requirement="",
                status=ReportStatus.COMPLETED,
                created_at="2024-06-01T00:00:00",
            )
            ReportManager.save_report(r1)
            ReportManager.save_report(r2)
            idx_path = os.path.join(reports, rsi.REPORT_SIMULATION_INDEX_FILENAME)
            assert os.path.isfile(idx_path)
            entries = rsi.get_reports_for_simulation("sim_t")
            assert [e["report_id"] for e in entries] == ["rep_new", "rep_old"]

            ReportManager.delete_report("rep_old")
            entries2 = rsi.get_reports_for_simulation("sim_t")
            assert [e["report_id"] for e in entries2] == ["rep_new"]


def test_get_reports_falls_back_scan_when_index_missing():
    with tempfile.TemporaryDirectory() as tmp:
        reports = os.path.join(tmp, "reports")
        os.makedirs(os.path.join(reports, "rep_only"), exist_ok=True)
        meta = {
            "report_id": "rep_only",
            "simulation_id": "sim_z",
            "graph_id": "g",
            "simulation_requirement": "",
            "status": "completed",
            "created_at": "2025-01-01T00:00:00",
        }
        with open(os.path.join(reports, "rep_only", "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f)

        with patch.object(Config, "UPLOAD_FOLDER", tmp), patch.object(
            ReportManager, "REPORTS_DIR", reports
        ):
            assert not os.path.isfile(os.path.join(reports, rsi.REPORT_SIMULATION_INDEX_FILENAME))
            out = rsi.get_reports_for_simulation("sim_z")
            assert len(out) == 1
            assert out[0]["report_id"] == "rep_only"
            assert os.path.isfile(os.path.join(reports, rsi.REPORT_SIMULATION_INDEX_FILENAME))


def test_build_report_index_skips_index_file():
    with tempfile.TemporaryDirectory() as tmp:
        reports = os.path.join(tmp, "reports")
        os.makedirs(reports, exist_ok=True)
        with patch.object(Config, "UPLOAD_FOLDER", tmp), patch.object(
            ReportManager, "REPORTS_DIR", reports
        ):
            rsi.build_report_index()
        with open(os.path.join(reports, rsi.REPORT_SIMULATION_INDEX_FILENAME), encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("by_simulation") == {}
