"""Tests for InsightForge sub-query selection (risk/failure guarantee)."""

from app.services.graph_tools import select_sub_queries_with_risk_guarantee


def test_risk_query_outside_first_slice_is_included_by_replacing_last_slot():
    raw = [
        "What drives growth for X?",
        "What channels work best?",
        "What partnerships matter?",
        "What risks or failure modes threaten X?",
        "What segments matter?",
    ]
    out = select_sub_queries_with_risk_guarantee(raw, max_queries=3)
    assert len(out) == 3
    assert any("risk" in q.lower() or "failure" in q.lower() for q in out)


def test_fallback_order_small_max_queries_still_includes_risk_when_present():
    raw = [
        "main question",
        "strategies",
        "What risks or failures are associated with main question",
    ]
    out = select_sub_queries_with_risk_guarantee(raw, max_queries=1)
    assert len(out) == 1
    assert "risk" in out[0].lower() or "failure" in out[0].lower()


def test_no_risk_keyword_in_list_returns_slice_only():
    raw = ["a", "b", "c"]
    out = select_sub_queries_with_risk_guarantee(raw, max_queries=2)
    assert out == ["a", "b"]
