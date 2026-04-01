"""Helpers for tracking non-request background threads."""

from __future__ import annotations

import atexit
import os
import signal
import threading
from typing import Callable, ClassVar, Iterable

from .logger import get_logger

logger = get_logger("mirofish.background_tasks")


class BackgroundTaskRegistry:
    """Track best-effort background threads so shutdown can wait briefly for them.

    **Class-level (process-wide) state:** ``_threads``, ``_lock``,
    ``_cleanup_registered``, and ``_cleanup_done`` live on the class, not on
    instances. Every ``BackgroundTaskRegistry`` reference shares the same
    ``_threads`` map and lock—there is no per-instance registry. That is
    intentional: background work is registered from many call sites; a single
    global set allows ``atexit`` and signal handlers (see ``register_cleanup``)
    to discover and ``join`` all threads exactly once for the process.

    **How to use:** Call the ``@classmethod`` APIs on ``BackgroundTaskRegistry``
    itself (e.g. ``BackgroundTaskRegistry.start(...)``). Do not assume distinct
    instances carry separate thread sets; instantiating the class is unnecessary
    for normal use.
    """

    _lock: ClassVar[threading.Lock] = threading.Lock()
    _threads: ClassVar[dict[str, set[threading.Thread]]] = {}
    _cleanup_registered: ClassVar[bool] = False
    _cleanup_done: ClassVar[bool] = False

    @classmethod
    def start(
        cls,
        *,
        name: str,
        target: Callable,
        args: Iterable | None = None,
        kwargs: dict | None = None,
        daemon: bool = True,
    ) -> threading.Thread:
        thread = threading.Thread(
            name=name,
            target=cls._wrap_target,
            args=(name, target, tuple(args or ()), kwargs or {}),
            daemon=daemon,
        )
        with cls._lock:
            cls._threads.setdefault(name, set()).add(thread)
        thread.start()
        return thread

    @classmethod
    def _wrap_target(cls, group: str, target: Callable, args: tuple, kwargs: dict) -> None:
        try:
            target(*args, **kwargs)
        finally:
            current = threading.current_thread()
            with cls._lock:
                threads = cls._threads.get(group)
                if not threads:
                    return
                threads.discard(current)
                if not threads:
                    cls._threads.pop(group, None)

    @classmethod
    def join_all(cls, timeout_per_thread: float = 2.0) -> None:
        with cls._lock:
            if cls._cleanup_done:
                return
            cls._cleanup_done = True
            all_threads = [thread for threads in cls._threads.values() for thread in list(threads)]
        for thread in all_threads:
            if not thread.is_alive():
                continue
            logger.info("Waiting for background task %s to finish", thread.name)
            thread.join(timeout=timeout_per_thread)

    @classmethod
    def register_cleanup(cls) -> None:
        with cls._lock:
            if cls._cleanup_registered:
                return
            debug_mode = os.environ.get("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
            is_reloader_process = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
            if debug_mode and not is_reloader_process:
                cls._cleanup_registered = True
                return
            cls._cleanup_registered = True

        _previous_handlers: dict[int, object] = {}

        def cleanup_handler(signum, frame):  # noqa: ARG001
            cls.join_all()
            old = _previous_handlers.get(signum)
            if old is None:
                return
            if old is signal.SIG_IGN:
                return
            if old is signal.SIG_DFL:
                try:
                    signal.signal(signum, signal.SIG_DFL)
                except (ValueError, OSError):
                    return
                try:
                    signal.raise_signal(signum)
                except (AttributeError, ValueError, OSError):
                    try:
                        os.kill(os.getpid(), signum)
                    except OSError:
                        pass
                return
            if callable(old):
                old(signum, frame)

        atexit.register(cls.join_all)
        for sig in (signal.SIGTERM, signal.SIGINT, getattr(signal, "SIGHUP", None)):
            if sig is None:
                continue
            try:
                _previous_handlers[sig] = signal.signal(sig, cleanup_handler)
            except (ValueError, OSError):
                continue
