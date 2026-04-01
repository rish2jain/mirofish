"""
Content-hash based LLM response cache.

Caches LLM responses keyed by SHA-256 hash of (prompt + model + temperature).
File-based storage under uploads/llm_cache/ for persistence across restarts.
"""

import hashlib
import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .logger import get_logger

logger = get_logger("mirofish.llm_cache")


@dataclass(frozen=True)
class CacheStats:
    """Cache usage statistics."""

    hits: int
    misses: int
    total_entries: int
    cache_dir: str

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 3),
            "total_entries": self.total_entries,
            "cache_dir": self.cache_dir,
        }


class LLMResponseCache:
    """
    File-based LLM response cache using content hashing.

    Keys are SHA-256 hashes of the serialized request (messages + model +
    temperature).  Values are stored as JSON files under ``cache_dir``.
    """

    def __init__(self, cache_dir: Optional[str] = None, max_age_seconds: int = 86400 * 7):
        default_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../uploads/llm_cache")
        )
        self.cache_dir = cache_dir or default_dir
        self.max_age_seconds = max_age_seconds
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()
        self._eviction_thread: Optional[threading.Thread] = None
        self._eviction_thread_lock = threading.Lock()
        self._eviction_stop_event = threading.Event()

        os.makedirs(self.cache_dir, exist_ok=True)

    @staticmethod
    def _make_key(
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Produce a deterministic SHA-256 cache key."""
        payload = json.dumps(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "response_format": response_format,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _path_for_key(self, key: str) -> str:
        # Two-level directory to avoid huge flat dirs
        return os.path.join(self.cache_dir, key[:2], f"{key}.json")

    def get(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        response_format: Optional[Dict] = None,
    ) -> Optional[str]:
        """Return cached response or ``None`` on miss."""
        key = self._make_key(messages, model, temperature, response_format)
        path = self._path_for_key(key)

        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            with self._lock:
                self._misses += 1
            return None

        # Check expiry
        created_at = entry.get("created_at", 0)
        if time.time() - created_at > self.max_age_seconds:
            with self._lock:
                self._misses += 1
            try:
                os.remove(path)
            except OSError:
                pass
            return None

        with self._lock:
            self._hits += 1
        logger.debug("Cache HIT for key %s (age %.0fs)", key[:12], time.time() - created_at)
        return entry.get("response")

    def put(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        response: str,
        response_format: Optional[Dict] = None,
    ) -> None:
        """Store a response in the cache."""
        key = self._make_key(messages, model, temperature, response_format)
        path = self._path_for_key(key)

        os.makedirs(os.path.dirname(path), exist_ok=True)

        entry = {
            "key": key,
            "created_at": time.time(),
            "model": model,
            "temperature": temperature,
            "response": response,
        }

        tmp_path: Optional[str] = None
        try:
            cache_subdir = os.path.dirname(path)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".json.tmp",
                dir=cache_subdir,
                delete=False,
            ) as f:
                tmp_path = f.name
                json.dump(entry, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
            tmp_path = None
            logger.debug("Cache PUT for key %s (%d chars)", key[:12], len(response))
        except OSError as exc:
            logger.warning("Failed to write cache entry %s: %s", key[:12], exc)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def stats(self) -> CacheStats:
        """Return cache statistics."""
        total = 0
        for dirpath, _dirnames, filenames in os.walk(self.cache_dir):
            total += sum(1 for f in filenames if f.endswith(".json"))
        with self._lock:
            hits, misses = self._hits, self._misses
        return CacheStats(
            hits=hits,
            misses=misses,
            total_entries=total,
            cache_dir=self.cache_dir,
        )

    def clear(self) -> int:
        """Remove all cached entries. Returns count of deleted files."""
        deleted = 0
        for dirpath, _dirnames, filenames in os.walk(self.cache_dir):
            for fname in filenames:
                if fname.endswith(".json"):
                    try:
                        os.remove(os.path.join(dirpath, fname))
                        deleted += 1
                    except OSError:
                        pass
        logger.info("Cache cleared: %d entries removed", deleted)
        return deleted

    def evict_expired(self) -> int:
        """Remove entries older than ``max_age_seconds``. Returns count of evicted.

        Uses ``os.stat`` mtime first: if ``now - st_mtime <= max_age_seconds``, the
        file cannot be expired yet for normal writes (``created_at`` is set at put
        time and is not after mtime), so JSON is not read.
        """
        evicted = 0
        now = time.time()
        max_age = self.max_age_seconds
        for dirpath, _dirnames, filenames in os.walk(self.cache_dir):
            for fname in filenames:
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    st = os.stat(fpath)
                except OSError:
                    continue
                if now - st.st_mtime <= max_age:
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        entry = json.load(f)
                    if now - entry.get("created_at", 0) > max_age:
                        os.remove(fpath)
                        evicted += 1
                except (json.JSONDecodeError, OSError):
                    pass
        if evicted:
            logger.info("Evicted %d expired cache entries", evicted)
        return evicted

    def start_eviction_thread(self, interval_seconds: float = 3600) -> None:
        """Start a daemon thread that periodically calls :meth:`evict_expired`.

        Non-blocking for the caller. Uses ``cache_dir`` and ``max_age_seconds``.
        If a background loop is already running for this instance, this is a no-op.
        """
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

        def runner() -> None:
            while not self._eviction_stop_event.is_set():
                try:
                    self.evict_expired()
                except Exception:
                    logger.exception(
                        "LLM cache evict_expired failed (cache_dir=%s)", self.cache_dir
                    )
                if self._eviction_stop_event.wait(timeout=interval_seconds):
                    break

        with self._eviction_thread_lock:
            if self._eviction_thread is not None and self._eviction_thread.is_alive():
                return
            self._eviction_stop_event.clear()
            t = threading.Thread(
                target=runner,
                name="mirofish-llm-cache-eviction",
                daemon=True,
            )
            self._eviction_thread = t
            t.start()

    def stop_eviction_thread(self, join_timeout: float = 5.0) -> None:
        """Signal the eviction loop to stop and wait for the thread to finish.

        Sets :attr:`_eviction_stop_event` (wakes :meth:`~threading.Event.wait` in the
        runner), then joins the thread. Clears the event and nulls
        :attr:`_eviction_thread` under :attr:`_eviction_thread_lock` after a clean exit.

        No-op if no thread was started. If the thread does not finish within
        ``join_timeout``, logs a warning and leaves the thread reference unchanged.
        """
        with self._eviction_thread_lock:
            t = self._eviction_thread
            if t is None:
                self._eviction_stop_event.clear()
                return
            self._eviction_stop_event.set()
        t.join(timeout=join_timeout)
        if t.is_alive():
            logger.warning(
                "LLM cache eviction thread did not stop within %.1fs (cache_dir=%s)",
                join_timeout,
                self.cache_dir,
            )
            return
        with self._eviction_thread_lock:
            if self._eviction_thread is t:
                self._eviction_thread = None
                self._eviction_stop_event.clear()

    def schedule_eviction(self, interval_seconds: float = 3600) -> None:
        """Alias for :meth:`start_eviction_thread` for callers that prefer this name."""
        self.start_eviction_thread(interval_seconds=interval_seconds)
