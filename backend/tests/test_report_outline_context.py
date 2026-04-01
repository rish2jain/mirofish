"""Tests for report agent outline-only context (parallel section mode)."""

from app.services.report_agent import ReportAgent
from app.services.report_models import ReportOutline, ReportSection


def test_outline_only_previous_sections_lists_titles():
    outline = ReportOutline(
        title="T",
        summary="S",
        sections=[
            ReportSection(title="Alpha"),
            ReportSection(title="Beta"),
        ],
    )
    ctx = ReportAgent._outline_only_previous_sections(outline)
    assert len(ctx) == 1
    assert "Parallel section generation" in ctx[0]
    assert "Alpha" in ctx[0]
    assert "Beta" in ctx[0]
    assert "Report: T" in ctx[0]
