"""ReportAgent.plan_outline with mocked LLM and graph context."""

from unittest.mock import MagicMock

from app.services.report_agent import ReportAgent


def test_plan_outline_from_chat_json():
    mock_ctx = {
        "graph_statistics": {
            "total_nodes": 4,
            "total_edges": 2,
            "entity_types": {"Person": 2},
        },
        "total_entities": 4,
        "related_facts": [{"x": 1}],
    }
    mock_gt = MagicMock()
    mock_gt.get_simulation_context.return_value = mock_ctx

    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = {
        "title": "Custom Outline Title",
        "summary": "One-line summary",
        "sections": [{"title": "First"}, {"title": "Second"}],
    }

    agent = ReportAgent(
        graph_id="g1",
        simulation_id="s1",
        simulation_requirement="Forecast retail sentiment",
        llm_client=mock_llm,
        graph_tools=mock_gt,
    )
    outline = agent.plan_outline()

    assert outline.title == "Custom Outline Title"
    assert outline.summary == "One-line summary"
    assert len(outline.sections) == 2
    assert outline.sections[0].title == "First"

    mock_gt.get_simulation_context.assert_called_once_with(
        graph_id="g1",
        simulation_requirement="Forecast retail sentiment",
    )
    mock_llm.chat_json.assert_called_once()


def test_chat_stream_narrative_yields_empty_stream_when_streaming_disabled():
    from app.services.report_agent import EMPTY_STREAM

    mock_llm = MagicMock()
    mock_llm.supports_streaming = False

    agent = ReportAgent(
        graph_id="g1",
        simulation_id="s1",
        simulation_requirement="Test",
        llm_client=mock_llm,
        graph_tools=MagicMock(),
    )
    parts = list(agent.chat_stream_narrative("hello"))
    assert parts == [EMPTY_STREAM]
    mock_llm.chat_stream_text.assert_not_called()


def test_chat_stream_narrative_yields_string_deltas_when_streaming_enabled():
    mock_llm = MagicMock()
    mock_llm.supports_streaming = True

    def _fake_gen():
        yield "a"
        yield "b"

    mock_llm.chat_stream_text.return_value = _fake_gen()

    agent = ReportAgent(
        graph_id="g1",
        simulation_id="s1",
        simulation_requirement="Test",
        llm_client=mock_llm,
        graph_tools=MagicMock(),
    )
    parts = list(agent.chat_stream_narrative("hello"))
    assert parts == ["a", "b"]
    mock_llm.chat_stream_text.assert_called_once()
