"""Tests for refined report section persistence validation."""

import os
from unittest.mock import MagicMock

import pytest

from app.services.report_agent import ReportAgent
from app.services.report_manager import ReportManager
from app.services.report_models import ReportOutline, ReportSection


def test_save_refined_sections_rejects_title_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path))
    report_id = "r1"
    os.makedirs(tmp_path / report_id, exist_ok=True)

    agent = ReportAgent("g1", "sim1", "question", graph_tools=MagicMock())
    outline = ReportOutline(
        title="T",
        summary="S",
        sections=[
            ReportSection(title="Section One", content=""),
            ReportSection(title="Section Two", content=""),
        ],
    )
    bad_md = (
        "# T\n\n> S\n\n---\n\n## Wrong Title\n\nx\n\n## Section Two\n\ny\n"
    )
    with pytest.raises(ValueError, match="title mismatch"):
        agent._save_refined_sections(report_id, bad_md, outline)


def test_save_refined_sections_rejects_section_count_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path))
    report_id = "r2"
    os.makedirs(tmp_path / report_id, exist_ok=True)

    agent = ReportAgent("g1", "sim1", "question", graph_tools=MagicMock())
    outline = ReportOutline(
        title="T",
        summary="S",
        sections=[ReportSection(title="Only", content="")],
    )
    bad_md = "# T\n\n> S\n\n---\n\n## Only\n\na\n\n## Extra\n\nb\n"
    with pytest.raises(ValueError, match="outline expects"):
        agent._save_refined_sections(report_id, bad_md, outline)
