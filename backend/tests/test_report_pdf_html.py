"""Tests for PDF export HTML sanitization."""

from app.api.report import _sanitize_report_html_for_pdf


def test_sanitize_strips_script_tags():
    dirty = '<p>Hello</p><script>alert(1)</script>'
    out = _sanitize_report_html_for_pdf(dirty)
    assert "<script>" not in out.lower()
    assert "Hello" in out
    assert "alert(1)" not in out


def test_sanitize_strips_javascript_hrefs():
    dirty = '<a href="javascript:alert(1)">x</a>'
    out = _sanitize_report_html_for_pdf(dirty)
    assert "javascript:" not in out.lower()
    assert "<a" in out
    assert "x" in out


def test_sanitize_strips_javascript_href_with_leading_whitespace():
    dirty = '<a href=" javascript:alert(1)">x</a>'
    out = _sanitize_report_html_for_pdf(dirty)
    assert "javascript:" not in out.lower()
    assert "<a" in out
    assert "x" in out


def test_sanitize_strips_onclick_attributes():
    dirty = '<p onclick="evil()">x</p>'
    out = _sanitize_report_html_for_pdf(dirty)
    assert "onclick" not in out
    assert "x" in out


def test_sanitize_strips_mixed_case_onclick():
    dirty = '<p ONCLICK="evil()">x</p>'
    out = _sanitize_report_html_for_pdf(dirty)
    assert "onclick" not in out.lower()
    assert "x" in out


def test_sanitize_strips_other_event_handlers_on_allowed_tags():
    dirty = (
        '<div onmouseover="evil()">a</div>'
        '<span onload="evil()">b</span>'
        '<p onerror="evil()">c</p>'
    )
    out = _sanitize_report_html_for_pdf(dirty)
    assert "onmouseover" not in out.lower()
    assert "onload" not in out.lower()
    assert "onerror" not in out.lower()
    assert "a" in out and "b" in out and "c" in out


def test_sanitize_strips_img_with_event_handlers():
    dirty = '<p>x</p><img src=x onerror="alert(1)">'
    out = _sanitize_report_html_for_pdf(dirty)
    assert "<img" not in out.lower()
    assert "onerror" not in out.lower()
    assert "x" in out


def test_sanitize_strips_mixed_case_script_tags():
    dirty = '<ScRiPt>alert(1)</ScRiPt><p>hi</p>'
    out = _sanitize_report_html_for_pdf(dirty)
    assert "<script" not in out.lower()
    assert "hi" in out


def test_sanitize_strips_data_hrefs():
    dirty = '<a href="data:text/html,<svg onload=alert(1)>">z</a>'
    out = _sanitize_report_html_for_pdf(dirty)
    assert "data:" not in out.lower()
    assert "<a" in out
    assert "z" in out


def test_sanitize_strips_data_href_mixed_case_scheme():
    dirty = '<a href="DaTa:text/html,foo">z</a>'
    out = _sanitize_report_html_for_pdf(dirty)
    assert "data:" not in out.lower()
    assert "z" in out


def test_sanitize_strips_vbscript_hrefs():
    dirty = '<a href="vbscript:msgbox(1)">z</a>'
    out = _sanitize_report_html_for_pdf(dirty)
    assert "vbscript:" not in out.lower()
    assert "z" in out


def test_sanitize_preserves_literal_onclick_in_text_content():
    """Do not strip the substring 'onclick=' when it appears in visible text, not as an attribute."""
    dirty = "<p>Documentation mentions onclick= handlers in prose.</p>"
    out = _sanitize_report_html_for_pdf(dirty)
    assert "onclick=" in out
    assert "Documentation" in out


def test_sanitize_preserves_safe_markdown_like_structure():
    dirty = (
        "<h2>Title</h2><p>Text with <strong>bold</strong> and "
        '<a href="https://example.com" title="t">link</a>.</p>'
    )
    out = _sanitize_report_html_for_pdf(dirty)
    assert "<h2>" in out
    assert "<strong>" in out
    assert "https://example.com" in out
