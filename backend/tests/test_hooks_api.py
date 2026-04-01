"""POST /api/hooks/webhooks — URL scheme checks at API boundary."""

import pytest


@pytest.fixture()
def hooks_client(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.Config.MIROFISH_API_KEY", "test-api-key")
    monkeypatch.setattr("app.config.Config.UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(
        "app.config.Config.SECRET_KEY",
        "test-secret-key-for-webhook-fernet",
    )

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post_register(hooks_client, url: str, **extra):
    body = {"url": url, "events": ["simulation.completed"], **extra}
    return hooks_client.post(
        "/api/hooks/webhooks",
        json=body,
        headers={"Authorization": "Bearer test-api-key"},
    )


def test_register_hook_rejects_missing_events(hooks_client):
    res = hooks_client.post(
        "/api/hooks/webhooks",
        json={"url": "https://example.com/h"},
        headers={"Authorization": "Bearer test-api-key"},
    )
    assert res.status_code == 400
    assert res.get_json() == {"success": False, "error": "events field is required"}


def test_register_hook_rejects_empty_events_list(hooks_client):
    res = _post_register(hooks_client, "https://example.com/h", events=[])
    assert res.status_code == 400
    assert res.get_json() == {"success": False, "error": "events must be a non-empty list"}


def test_register_hook_rejects_missing_scheme(hooks_client):
    res = _post_register(hooks_client, "example.com/hook")
    assert res.status_code == 400
    assert res.get_json() == {
        "success": False,
        "error": "url must use http or https",
    }


def test_register_hook_rejects_ftp_scheme(hooks_client):
    res = _post_register(hooks_client, "ftp://example.com/x")
    assert res.status_code == 400
    assert res.get_json() == {
        "success": False,
        "error": "url must use http or https",
    }


def test_register_hook_rejects_http_non_localhost(hooks_client):
    res = _post_register(hooks_client, "http://evil.com/x")
    assert res.status_code == 400
    body = res.get_json()
    assert body == {
        "success": False,
        "error": (
            "only https URLs are allowed "
            "(http permitted for localhost, 127.0.0.1, and ::1 only)"
        ),
    }


def test_register_hook_accepts_https(hooks_client):
    res = _post_register(hooks_client, "https://1.1.1.1/x")
    assert res.status_code == 200
    body = res.get_json()
    assert body.get("success") is True
    assert body.get("data", {}).get("url") == "https://1.1.1.1/x"


def test_register_hook_accepts_http_localhost(hooks_client):
    res = _post_register(hooks_client, "http://localhost:9999/cb")
    assert res.status_code == 200
    body = res.get_json()
    assert body.get("success") is True
    assert body.get("data", {}).get("url") == "http://localhost:9999/cb"


def test_register_hook_accepts_http_ipv6_loopback(hooks_client):
    res = _post_register(hooks_client, "http://[::1]:9999/cb")
    assert res.status_code == 200
    body = res.get_json()
    assert body.get("success") is True
    assert body.get("data", {}).get("url") == "http://[::1]:9999/cb"
