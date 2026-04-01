"""LLMResponseCache eviction and background scheduling."""

import json
import os
import time

from app.utils.llm_cache import LLMResponseCache


def test_evict_expired_empty(tmp_path):
    c = LLMResponseCache(cache_dir=str(tmp_path), max_age_seconds=60)
    assert c.evict_expired() == 0


def test_evict_expired_removes_stale_by_json_and_mtime(tmp_path):
    c = LLMResponseCache(cache_dir=str(tmp_path), max_age_seconds=60)
    old = time.time() - 120
    sub = tmp_path / "ab"
    sub.mkdir()
    p = sub / "ab.json"
    p.write_text(
        json.dumps({"key": "ab", "created_at": old, "response": "x"}),
        encoding="utf-8",
    )
    os.utime(p, (old, old))
    assert c.evict_expired() == 1
    assert not p.exists()


def test_evict_expired_skips_open_when_mtime_too_recent(tmp_path):
    """Stat fast path: recent mtime skips JSON read (mtime heuristic)."""
    c = LLMResponseCache(cache_dir=str(tmp_path), max_age_seconds=3600)
    sub = tmp_path / "cd"
    sub.mkdir()
    p = sub / "cd.json"
    # Stale JSON created_at but fresh mtime: stat fast path keeps file.
    ancient = time.time() - 86400 * 30
    p.write_text(
        json.dumps({"key": "cd", "created_at": ancient, "response": "y"}),
        encoding="utf-8",
    )
    assert c.evict_expired() == 0
    assert p.exists()


def test_start_eviction_thread_daemon_and_idempotent(tmp_path):
    c = LLMResponseCache(cache_dir=str(tmp_path), max_age_seconds=3600)
    c.start_eviction_thread(interval_seconds=600.0)
    t = c._eviction_thread
    assert t is not None
    assert t.daemon is True
    c.start_eviction_thread(interval_seconds=600.0)
    assert c._eviction_thread is t
    c.stop_eviction_thread(join_timeout=2.0)
    assert not t.is_alive()
    assert c._eviction_thread is None
