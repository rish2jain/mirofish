"""Template write path validation (path traversal prevention)."""

import os

import pytest

from app.api import templates as tpl


def test_safe_path_accepts_letters_and_json_stem():
    fp, err = tpl._resolve_safe_template_write_path("regulatory_impact")
    assert err is None
    assert fp.endswith(os.path.join("templates", "regulatory_impact.json"))


@pytest.mark.parametrize(
    "bad_id",
    [
        "../x",
        "..\\x",
        "a/b",
        "",
        " space",
        "x/y",
        "../../../etc/passwd",
    ],
)
def test_safe_path_rejects_traversal_or_invalid(bad_id):
    fp, err = tpl._resolve_safe_template_write_path(bad_id)
    assert fp is None
    assert err
