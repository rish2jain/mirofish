"""Webhook registry: URL validation and secret encryption at rest."""

import json
import socket
import tempfile

import pytest

from app.config import Config
from app.services import webhook_service as ws


def test_validate_webhook_url_https_ok():
    # Numeric public IP avoids DNS in CI/offline.
    assert ws._validate_webhook_url("https://1.1.1.1/hooks") is None


def test_validate_webhook_url_localhost_http_ok():
    assert ws._validate_webhook_url("http://localhost:8080/cb") is None
    assert ws._validate_webhook_url("http://127.0.0.1:9/x") is None
    assert ws._validate_webhook_url("http://[::1]:8080/cb") is None


def test_validate_webhook_url_rejects_insecure_http():
    err = ws._validate_webhook_url("http://example.com/hook")
    assert err and "https" in err.lower()


def test_validate_webhook_url_rejects_bad_scheme():
    err = ws._validate_webhook_url("ftp://example.com/x")
    assert err and "http" in err.lower()


def test_validate_webhook_url_rejects_userinfo():
    err = ws._validate_webhook_url("https://user:pass@1.1.1.1/h")
    assert err and "credential" in err.lower()


def test_validate_webhook_url_rejects_private_literal():
    assert ws._validate_webhook_url("https://10.0.0.1/x") == (
        "url resolves to internal/private IP"
    )


def test_validate_webhook_url_rejects_non_allowlisted_loopback_literal():
    assert ws._validate_webhook_url("https://127.0.0.2/x") == (
        "url resolves to internal/private IP"
    )


def test_validate_webhook_url_rejects_ssrf_private_resolve(monkeypatch):
    def fake_gai(host, port, *args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("10.0.0.5", int(port)),
            )
        ]

    monkeypatch.setattr(ws.socket, "getaddrinfo", fake_gai)
    err = ws._validate_webhook_url("https://looks-public.example/hook")
    assert err == "url resolves to internal/private IP"


def test_validate_webhook_url_resolution_error(monkeypatch):
    def boom(*args, **kwargs):
        raise socket.gaierror("nxdomain")

    monkeypatch.setattr(ws.socket, "getaddrinfo", boom)
    err = ws._validate_webhook_url("https://does-not-exist.invalid/h")
    assert err == "url host could not be resolved"


def test_secret_encode_decode_roundtrip():
    plain = "whsec_test_value"
    enc = ws._encode_secret_for_storage(plain)
    assert enc.startswith(ws._SECRET_STORE_PREFIX)
    assert ws._decode_secret_from_storage(enc) == plain


def test_secret_legacy_plaintext_passthrough():
    assert ws._decode_secret_from_storage("legacy-plain") == "legacy-plain"


def test_register_encrypts_on_disk(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(Config, "UPLOAD_FOLDER", tmp)
        monkeypatch.setattr(Config, "SECRET_KEY", "test-secret-key-for-webhook-fernet")

        out = ws.register_subscription(
            "https://1.1.1.1/x",
            ["simulation.completed"],
            "mysecret",
        )
        assert out["secret"] == "mysecret"

        path = ws._registry_path()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        stored = data["subscriptions"][0]["secret"]
        assert stored.startswith(ws._SECRET_STORE_PREFIX)
        assert "mysecret" not in stored

        listed = ws.list_subscriptions()
        assert listed[0]["has_secret"] is True
        assert "secret" not in listed[0]


def test_register_invalid_url_raises():
    with pytest.raises(ValueError, match="https"):
        ws.register_subscription("http://evil.com/x", ["simulation.completed"], "")


def test_post_one_uses_single_resolve_and_connects_to_ip(monkeypatch):
    """No second DNS lookup: connect to validated IP, Host + TLS SNI = original name."""
    gai_calls: list[int] = []

    def fake_gai(host, port, *args, **kwargs):
        gai_calls.append(1)
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("1.1.1.1", int(port)),
            )
        ]

    class FakeResp:
        status = 204
        reason = "No Content"

        def read(self):
            return b""

    instances: list = []

    class FakeConnCapture:
        def __init__(self, connect_host, connect_port, **kwargs):
            self.connect_host = connect_host
            self.connect_port = connect_port
            self.server_hostname = kwargs.get("server_hostname")
            self._req = None
            instances.append(self)

        def request(self, method, path, body=None, headers=None):
            self._req = (method, path, body, dict(headers or {}))

        def getresponse(self):
            return FakeResp()

        def close(self):
            pass

    monkeypatch.setattr(ws.socket, "getaddrinfo", fake_gai)
    monkeypatch.setattr(ws.http.client, "HTTPSConnection", FakeConnCapture)

    ws._post_one("https://hooks.example.net/path?k=v", b"{}", "sha256=deadbeef")

    assert len(gai_calls) == 1
    assert len(instances) == 1
    c = instances[0]
    assert c.connect_host == "1.1.1.1"
    assert c.connect_port == 443
    assert c.server_hostname == "hooks.example.net"
    assert c._req[0] == "POST"
    assert c._req[1] == "/path?k=v"
    assert c._req[2] == b"{}"
    assert c._req[3].get("Host") == "hooks.example.net"


def test_post_one_tries_next_validated_on_tcp_connect_failure(monkeypatch):
    """When the first resolved IP refuses TCP, fall back to the next validated sockaddr."""

    def fake_gai(host, port, *args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("8.8.8.8", int(port)),
            ),
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("1.1.1.1", int(port)),
            ),
        ]

    class ProbeSocket:
        def __init__(self, family, socktype):
            self._family = family

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def settimeout(self, _t):
            pass

        def connect(self, sockaddr):
            if sockaddr[0] == "8.8.8.8":
                raise ConnectionRefusedError(111, "Connection refused")

        def close(self):
            pass

    class FakeResp:
        status = 204
        reason = "No Content"

        def read(self):
            return b""

    instances: list = []

    class FakeConnCapture:
        def __init__(self, connect_host, connect_port, **kwargs):
            self.connect_host = connect_host
            self.connect_port = connect_port
            self.server_hostname = kwargs.get("server_hostname")
            self._req = None
            instances.append(self)

        def request(self, method, path, body=None, headers=None):
            self._req = (method, path, body, dict(headers or {}))

        def getresponse(self):
            return FakeResp()

        def close(self):
            pass

    monkeypatch.setattr(ws.socket, "getaddrinfo", fake_gai)
    monkeypatch.setattr(ws.socket, "socket", ProbeSocket)
    monkeypatch.setattr(ws.http.client, "HTTPSConnection", FakeConnCapture)

    ws._post_one("https://hooks.example.net/path", b"{}", "sha256=deadbeef")

    assert len(instances) == 1
    assert instances[0].connect_host == "1.1.1.1"
    assert instances[0].connect_port == 443


def test_dispatch_event_purge_debounce_stale_only(monkeypatch, tmp_path):
    """Purge removes only _LAST_SIM_TERMINAL keys past _TERMINAL_DEBOUNCE_SEC."""
    prev_terminal = dict(ws._LAST_SIM_TERMINAL)
    prev_cleanup = ws._LAST_CLEANUP
    try:
        monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
        ws._LAST_SIM_TERMINAL.clear()
        ws._LAST_CLEANUP = 0.0
        now = 10_000.0
        monkeypatch.setattr(ws.time, "monotonic", lambda: now)
        cutoff = now - ws._TERMINAL_DEBOUNCE_SEC
        ws._LAST_SIM_TERMINAL["simulation.completed:old"] = cutoff - 1.0
        ws._LAST_SIM_TERMINAL["simulation.failed:fresh"] = cutoff + 1.0

        ws.dispatch_event("noop", {})

        assert "simulation.completed:old" not in ws._LAST_SIM_TERMINAL
        assert ws._LAST_SIM_TERMINAL.get("simulation.failed:fresh") == cutoff + 1.0
        assert ws._LAST_CLEANUP == now
    finally:
        ws._LAST_SIM_TERMINAL.clear()
        ws._LAST_SIM_TERMINAL.update(prev_terminal)
        ws._LAST_CLEANUP = prev_cleanup
