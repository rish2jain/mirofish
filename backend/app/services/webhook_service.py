"""Outbound webhooks for simulation lifecycle (registry on disk)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import io
import ipaddress
import json
import os
import socket
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List

from cryptography.fernet import Fernet, InvalidToken

from ..config import Config
from ..utils.background_tasks import BackgroundTaskRegistry
from ..utils.logger import get_logger

logger = get_logger("mirofish.webhooks")

# Stored secret prefix: Fernet token (urlsafe base64) after this marker.
_SECRET_STORE_PREFIX = "mf1:"

_REGISTRY_LOCK = threading.Lock()
_LAST_SIM_TERMINAL_LOCK = threading.Lock()
_LAST_SIM_TERMINAL: Dict[str, float] = {}
_TERMINAL_DEBOUNCE_SEC = 8.0


def _registry_path() -> str:
    base = os.path.join(Config.UPLOAD_FOLDER, "webhooks")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "registry.json")


def _dlq_path(subscription_id: str) -> str:
    base = os.path.join(Config.UPLOAD_FOLDER, "webhooks", "dlq")
    os.makedirs(base, exist_ok=True)
    safe = "".join(c for c in subscription_id if c.isalnum() or c in ("-", "_"))[:64] or "unknown"
    return os.path.join(base, f"{safe}.jsonl")


def _append_dlq(subscription_id: str, url: str, envelope: Dict[str, Any], error: str) -> None:
    """Append one dead-letter record (per subscription) after retries are exhausted."""
    row = {
        "ts": datetime.now().isoformat(),
        "subscription_id": subscription_id,
        "url": url,
        "error": error,
        "envelope": envelope,
    }
    path = _dlq_path(subscription_id)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_raw() -> Dict[str, Any]:
    path = _registry_path()
    if not os.path.isfile(path):
        return {"subscriptions": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"subscriptions": []}
        data.setdefault("subscriptions", [])
        return data
    except (json.JSONDecodeError, OSError):
        return {"subscriptions": []}


def _save_raw(data: Dict[str, Any]) -> None:
    path = _registry_path()
    directory = os.path.dirname(path)
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix="registry.",
            suffix=".tmp",
            delete=False,
        ) as f:
            tmp_path = f.name
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if os.path.isfile(path):
            os.chmod(tmp_path, os.stat(path).st_mode & 0o777)
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _webhook_fernet() -> Fernet:
    """Deterministic Fernet key from app SECRET_KEY (encrypt-at-rest for subscriber secrets)."""
    digest = hashlib.sha256(Config.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _encode_secret_for_storage(plain: str) -> str:
    if not plain:
        return ""
    token = _webhook_fernet().encrypt(plain.encode("utf-8"))
    return _SECRET_STORE_PREFIX + token.decode("ascii")


def _decode_secret_from_storage(stored: str) -> str:
    """Decrypt stored token, or return legacy plaintext entries unchanged."""
    if not stored:
        return ""
    if not stored.startswith(_SECRET_STORE_PREFIX):
        return stored
    try:
        raw = stored[len(_SECRET_STORE_PREFIX) :].encode("ascii")
        return _webhook_fernet().decrypt(raw).decode("utf-8")
    except (InvalidToken, OSError, ValueError, UnicodeError) as e:
        logger.warning("Could not decrypt webhook subscriber secret: %s", e)
        return ""


_HTTP_ALLOWED_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})


def _webhook_ip_flags_non_public(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """True if the address is not suitable for a public webhook target."""
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validated_webhook_addrinfos(
    host: str, scheme: str, port: int | None
) -> tuple[list[tuple[int, tuple]], str | None]:
    """
    Resolve once and return (family, sockaddr) rows that pass SSRF checks.

    On error returns ([], message). Every resolved address must be allowed (public
    global, or loopback only when host is localhost / 127.0.0.1 / ::1).
    """
    portnum = port if port is not None else (443 if scheme == "https" else 80)
    allowed_loopback_name = host in _HTTP_ALLOWED_LOOPBACK

    try:
        infos = socket.getaddrinfo(
            host,
            portnum,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        logger.info("Webhook URL host resolve failed for %r: %s", host, exc)
        return [], "url host could not be resolved"
    except OSError as exc:
        logger.info("Webhook URL host resolve OS error for %r: %s", host, exc)
        return [], "url host could not be resolved"

    if not infos:
        return [], "url host could not be resolved"

    validated: list[tuple[int, tuple]] = []
    saw_ip = False
    for fa, _socktype, _proto, _canon, sockaddr in infos:
        addr = sockaddr[0]
        if not isinstance(addr, str):
            continue
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            logger.warning("Webhook URL unexpected sockaddr address %r", addr)
            return [], "url host could not be resolved"

        saw_ip = True
        if not _webhook_ip_flags_non_public(ip):
            validated.append((fa, sockaddr))
            continue
        if allowed_loopback_name and ip.is_loopback:
            validated.append((fa, sockaddr))
            continue
        return [], "url resolves to internal/private IP"

    if not saw_ip:
        return [], "url host could not be resolved"
    if not validated:
        return [], "url host could not be resolved"
    return validated, None


def _validate_webhook_resolved_ips(
    host: str, scheme: str, port: int | None
) -> str | None:
    """
    Reject URLs whose host resolves only to disallowed addresses.
    Allows loopback resolves only when host is localhost / 127.0.0.1 / ::1.
    """
    _rows, err = _validated_webhook_addrinfos(host, scheme, port)
    return err


def _webhook_request_host_header(parsed: urllib.parse.ParseResult) -> str:
    """Value for the Host header (bracket IPv6; include port if non-default)."""
    hostname = parsed.hostname or ""
    scheme = (parsed.scheme or "").lower()
    port = parsed.port
    default_port = 443 if scheme == "https" else 80
    if ":" in hostname and not hostname.startswith("["):
        display = f"[{hostname}]"
    else:
        display = hostname
    if port is not None and port != default_port:
        return f"{display}:{port}"
    return display


def _webhook_request_target_path(parsed: urllib.parse.ParseResult) -> str:
    path = parsed.path or "/"
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


def _webhook_post_via_resolved_ip(
    url: str,
    parsed: urllib.parse.ParseResult,
    scheme: str,
    body: bytes,
    headers: dict[str, str],
    validated: list[tuple[int, tuple]],
) -> None:
    """
    POST via a validated sockaddr without a second DNS lookup.

    Tries each validated resolved address until TCP connect succeeds, then POSTs
    to that numeric IP; sets Host to the original host and uses
    server_hostname=SNI for HTTPS certificate verification.
    """
    path = _webhook_request_target_path(parsed)
    host_header = _webhook_request_host_header(parsed)
    hdrs = {**headers, "Host": host_header}
    sni_name = parsed.hostname

    timeout = 15
    last_connect_exc: OSError | TimeoutError | None = None
    connect_host: str
    connect_port: int
    for _family, sockaddr in validated:
        connect_host = sockaddr[0]
        connect_port = sockaddr[1]
        try:
            with socket.socket(_family, socket.SOCK_STREAM) as probe:
                probe.settimeout(timeout)
                probe.connect(sockaddr)
        except (OSError, TimeoutError) as exc:
            logger.warning(
                "Webhook TCP connect failed for %s:%s: %s",
                connect_host,
                connect_port,
                exc,
            )
            last_connect_exc = exc
            continue
        break
    else:
        if last_connect_exc is not None:
            raise last_connect_exc
        raise OSError("webhook could not connect to any validated address")

    if scheme == "https":
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(
            connect_host,
            connect_port,
            context=ctx,
            timeout=timeout,
            server_hostname=sni_name,
        )
    else:
        conn = http.client.HTTPConnection(connect_host, connect_port, timeout=timeout)

    try:
        conn.request("POST", path, body=body, headers=hdrs)
        resp = conn.getresponse()
        resp.read()
        if resp.status >= 400:
            raise urllib.error.HTTPError(
                url,
                resp.status,
                resp.reason,
                resp.headers,
                io.BytesIO(),
            )
    finally:
        conn.close()


def _validate_webhook_url(url: str) -> str | None:
    """Return an error message if URL is not allowed, else None."""
    parsed = urllib.parse.urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return "url must use http or https"
    if not parsed.hostname:
        return "url is malformed (missing host)"
    host = parsed.hostname.lower()
    if scheme == "http" and host not in _HTTP_ALLOWED_LOOPBACK:
        return (
            "only https URLs are allowed "
            "(http permitted for localhost, 127.0.0.1, and ::1 only)"
        )
    if "@" in parsed.netloc:
        return "url must not embed user credentials"

    resolved_err = _validate_webhook_resolved_ips(host, scheme, parsed.port)
    if resolved_err:
        return resolved_err
    return None


def list_subscriptions() -> List[Dict[str, Any]]:
    with _REGISTRY_LOCK:
        subs = list(_load_raw().get("subscriptions", []))
    redacted: List[Dict[str, Any]] = []
    for s in subs:
        item = {k: v for k, v in s.items() if k != "secret"}
        item["has_secret"] = bool(s.get("secret"))
        redacted.append(item)
    return redacted


def register_subscription(url: str, events: List[str], secret: str = "") -> Dict[str, Any]:
    err = _validate_webhook_url(url)
    if err:
        raise ValueError(err)

    stored_secret = _encode_secret_for_storage(secret or "")
    entry = {
        "id": hashlib.sha256(f"{url}:{datetime.now().isoformat()}".encode()).hexdigest()[:16],
        "url": url,
        "events": events,
        "secret": stored_secret,
        "created_at": datetime.now().isoformat(),
    }
    with _REGISTRY_LOCK:
        data = _load_raw()
        data.setdefault("subscriptions", []).append(entry)
        _save_raw(data)
    # Return plaintext secret once for the client; disk only holds ciphertext.
    return {
        "id": entry["id"],
        "url": entry["url"],
        "events": entry["events"],
        "secret": secret or "",
        "created_at": entry["created_at"],
    }


def unregister_subscription(sub_id: str) -> bool:
    with _REGISTRY_LOCK:
        data = _load_raw()
        subs = data.get("subscriptions", [])
        new_subs = [s for s in subs if s.get("id") != sub_id]
        if len(new_subs) == len(subs):
            return False
        data["subscriptions"] = new_subs
        _save_raw(data)
    return True


class _WebhookDispatchBlockedError(Exception):
    """Dispatch-time URL/DNS policy rejected the target (do not retry)."""


def _post_one(url: str, body: bytes, sig_header: str) -> None:
    parsed = urllib.parse.urlparse(url)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    if not host:
        err = "url is malformed (missing host)"
        logger.error(
            "Webhook dispatch blocked (resolved IP check): url=%s error=%s",
            url,
            err,
        )
        raise _WebhookDispatchBlockedError(err)
    validated, resolved_err = _validated_webhook_addrinfos(host, scheme, parsed.port)
    if resolved_err:
        logger.error(
            "Webhook dispatch blocked (resolved IP check): url=%s error=%s",
            url,
            resolved_err,
        )
        raise _WebhookDispatchBlockedError(resolved_err)

    hdrs = {
        "Content-Type": "application/json",
        "X-MiroFish-Signature": sig_header,
        "User-Agent": "MiroFish-Webhook/1.0",
    }
    _webhook_post_via_resolved_ip(url, parsed, scheme, body, hdrs, validated)


_CLEANUP_INTERVAL = 300.0  # 5 minutes
_LAST_CLEANUP = 0.0


def dispatch_event(event: str, payload: Dict[str, Any]) -> None:
    """Fire webhooks in a background thread (best-effort)."""
    global _LAST_CLEANUP
    with _LAST_SIM_TERMINAL_LOCK:
        now = time.monotonic()

        # Periodic cleanup: purge debounce entries older than _TERMINAL_DEBOUNCE_SEC.
        if now - _LAST_CLEANUP > _CLEANUP_INTERVAL:
            cutoff = now - _TERMINAL_DEBOUNCE_SEC
            stale_keys = [k for k, ts in _LAST_SIM_TERMINAL.items() if ts < cutoff]
            for k in stale_keys:
                del _LAST_SIM_TERMINAL[k]
            _LAST_CLEANUP = now

        sid = payload.get("simulation_id")
        if sid and event in ("simulation.completed", "simulation.failed"):
            key = f"{event}:{sid}"
            prev = _LAST_SIM_TERMINAL.get(key, 0.0)
            if now - prev < _TERMINAL_DEBOUNCE_SEC:
                return
            _LAST_SIM_TERMINAL[key] = now

    with _REGISTRY_LOCK:
        subs = list(_load_raw().get("subscriptions", []))
    if not subs:
        return

    def _run():
        for sub in subs:
            if event not in (sub.get("events") or []):
                continue
            url = sub.get("url") or ""
            if not url:
                continue
            plain_secret = _decode_secret_from_storage(sub.get("secret") or "")
            secret = plain_secret.encode("utf-8")
            envelope = {"event": event, "payload": payload, "sent_at": datetime.now().isoformat()}
            body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
            sig = (
                hmac.new(secret, body, hashlib.sha256).hexdigest()
                if secret
                else ""
            )
            last_exc: Exception | None = None
            sub_id = str(sub.get("id") or "unknown")
            for attempt in range(3):
                try:
                    _post_one(url, body, f"sha256={sig}")
                    last_exc = None
                    break
                except _WebhookDispatchBlockedError as exc:
                    last_exc = exc
                    break
                except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
                    last_exc = exc
                    if attempt < 2:
                        time.sleep(0.4 * (2**attempt))
            if last_exc is not None:
                logger.warning("Webhook delivery failed after retries %s: %s", url, last_exc)
                try:
                    _append_dlq(sub_id, url, envelope, str(last_exc))
                except OSError as ose:
                    logger.warning("Could not write webhook DLQ: %s", ose)

    BackgroundTaskRegistry.start(name="webhook-dispatch", target=_run)
