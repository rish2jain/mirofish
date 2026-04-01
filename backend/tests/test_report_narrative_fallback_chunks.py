"""Unit tests for SSE-sized splitting of one-shot narrative chat responses."""

from app.api.report import _iter_narrative_fallback_chunks


def test_iter_narrative_fallback_chunks_empty():
    assert list(_iter_narrative_fallback_chunks("")) == []


def test_iter_narrative_fallback_chunks_short_single_chunk():
    assert list(_iter_narrative_fallback_chunks("hello", max_chars=1024)) == ["hello"]


def test_iter_narrative_fallback_chunks_fixed_size_when_no_newlines():
    s = "a" * 2500
    parts = list(_iter_narrative_fallback_chunks(s, max_chars=1000))
    assert parts == ["a" * 1000, "a" * 1000, "a" * 500]
    assert "".join(parts) == s


def test_iter_narrative_fallback_chunks_prefers_newline_boundary():
    s = ("x" * 30 + "\n") * 3 + "y" * 80
    parts = list(_iter_narrative_fallback_chunks(s, max_chars=50))
    assert "".join(parts) == s
    assert all(len(p) <= 50 for p in parts)
