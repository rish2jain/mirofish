"""PUT /api/templates/<id>: URL id must match body id when body sets id."""

import json

import pytest

from app.api import templates as tpl


@pytest.fixture()
def templates_write_client(monkeypatch, tmp_path):
    monkeypatch.setattr(tpl, "TEMPLATES_DIR", str(tmp_path))
    tpl.invalidate_templates_cache()
    monkeypatch.setattr("app.config.Config.MIROFISH_API_KEY", "test-api-key")
    monkeypatch.setattr("app.config.Config.MIROFISH_ALLOW_TEMPLATE_WRITE", True)

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _put(templates_write_client, url_id: str, body: dict):
    return templates_write_client.put(
        f"/api/templates/{url_id}",
        data=json.dumps(body),
        content_type="application/json",
        headers={"Authorization": "Bearer test-api-key"},
    )


def test_put_rejects_mismatched_url_and_body_id(templates_write_client):
    res = _put(
        templates_write_client,
        "regulatory_impact",
        {"id": "other_template", "name": "x"},
    )
    assert res.status_code == 400
    assert res.get_json() == {
        "success": False,
        "error": "URL id and body id must match",
    }


def test_put_accepts_matching_url_and_body_id(templates_write_client):
    res = _put(
        templates_write_client,
        "regulatory_impact",
        {"id": "regulatory_impact", "title": "T"},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body.get("success") is True
    assert body.get("data", {}).get("id") == "regulatory_impact"


def test_put_auto_fills_id_from_url_when_body_omits_id(
    templates_write_client,
):
    res = _put(
        templates_write_client,
        "regulatory_impact",
        {"title": "Only title"},
    )
    assert res.status_code == 200
    assert res.get_json().get("data", {}).get("id") == "regulatory_impact"
