"""
Persistent index: simulation_id -> report summaries (report_id, created_at, status).

Keeps lookups O(k) per simulation instead of scanning every report folder.
Index is updated after each meta.json write via update_report_index; removed on delete.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[misc, assignment]

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger("mirofish.report_simulation_index")

REPORT_SIMULATION_INDEX_FILENAME = "report_simulation_index.json"
_INDEX_VERSION = 1

# Serialize in-process full index rebuilds triggered from get_reports_for_simulation.
_index_rebuild_lock = threading.Lock()


def _serialized_rebuild_report_index() -> None:
    """
    Run build_report_index at most once concurrently. The first caller performs the rebuild;
    others block until it finishes, then return without a second rebuild (callers re-read the file).
    """
    if _index_rebuild_lock.acquire(blocking=False):
        try:
            build_report_index()
        finally:
            _index_rebuild_lock.release()
    else:
        with _index_rebuild_lock:
            pass


def _reports_dir() -> str:
    return os.path.join(Config.UPLOAD_FOLDER, "reports")


def _index_path() -> str:
    return os.path.join(_reports_dir(), REPORT_SIMULATION_INDEX_FILENAME)


@contextmanager
def _report_index_file_lock() -> Iterator[None]:
    """Process-level exclusive lock for index read-modify-write (Unix fcntl)."""
    if fcntl is None:
        yield
        return
    os.makedirs(_reports_dir(), exist_ok=True)
    lock_path = _index_path() + ".lock"
    with open(lock_path, "a+", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def _should_skip_reports_dir_entry(name: str) -> bool:
    return name == REPORT_SIMULATION_INDEX_FILENAME


def _atomic_write_json(target_path: str, obj: Any) -> None:
    directory = os.path.dirname(target_path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp", prefix=".rsi_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(obj, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, target_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_index() -> Optional[Dict[str, Any]]:
    path = _index_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("report simulation index unreadable (%s): %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    return data


def _meta_exists(report_id: str) -> bool:
    root = _reports_dir()
    if os.path.isfile(os.path.join(root, report_id, "meta.json")):
        return True
    return os.path.isfile(os.path.join(root, f"{report_id}.json"))


def _scan_reports_dir_for_simulation(simulation_id: str) -> List[Dict[str, Any]]:
    """Full directory scan (fallback when index is missing)."""
    root = _reports_dir()
    if not os.path.isdir(root):
        return []
    matching: List[Dict[str, Any]] = []
    try:
        for name in os.listdir(root):
            if _should_skip_reports_dir_entry(name):
                continue
            folder = os.path.join(root, name)
            meta_path = os.path.join(folder, "meta.json")
            if not os.path.isdir(folder):
                if name.endswith(".json"):
                    meta_path = os.path.join(root, name)
                else:
                    continue
            if not os.path.isfile(meta_path):
                continue
            try:
                with open(meta_path, "r", encoding="utf-8") as handle:
                    meta = json.load(handle)
            except (json.JSONDecodeError, OSError):
                continue
            if meta.get("simulation_id") != simulation_id:
                continue
            matching.append(
                {
                    "report_id": meta.get("report_id"),
                    "created_at": meta.get("created_at", ""),
                    "status": meta.get("status", ""),
                }
            )
    except OSError as exc:
        logger.warning("scan reports dir for simulation %s: %s", simulation_id, exc)
        return []
    return [m for m in matching if m.get("report_id")]


def build_report_index() -> Dict[str, Any]:
    """
    Rebuild the full index by scanning the reports directory.
    Uses ReportManager.get_report to respect folder + legacy flat layout.
    """
    from .report_manager import ReportManager

    ReportManager._ensure_reports_dir()
    by_simulation: Dict[str, List[Dict[str, Any]]] = {}
    root = _reports_dir()
    try:
        names = os.listdir(root)
    except OSError:
        names = []

    for item in names:
        if _should_skip_reports_dir_entry(item):
            continue
        item_path = os.path.join(root, item)
        report_id: Optional[str] = None
        if os.path.isdir(item_path):
            report_id = item
        elif item.endswith(".json"):
            report_id = item[:-5]
        else:
            continue
        if not report_id:
            continue
        try:
            report = ReportManager.get_report(report_id)
        except Exception as exc:
            logger.debug("Skipping report %s during index rebuild: %s", report_id, exc)
            continue
        if not report or not report.simulation_id:
            continue
        sid = report.simulation_id
        entry = {
            "report_id": report.report_id,
            "created_at": report.created_at or "",
            "status": report.status.value if hasattr(report.status, "value") else str(report.status),
        }
        by_simulation.setdefault(sid, []).append(entry)

    for sid in list(by_simulation.keys()):
        lst = by_simulation[sid]
        by_id: Dict[str, Dict[str, Any]] = {}
        for e in lst:
            rid = e.get("report_id")
            if not rid:
                continue
            rid = str(rid)
            prev = by_id.get(rid)
            if prev is None or (e.get("created_at", "") >= prev.get("created_at", "")):
                by_id[rid] = e
        by_simulation[sid] = sorted(by_id.values(), key=lambda x: x.get("created_at", ""), reverse=True)

    payload = {"version": _INDEX_VERSION, "by_simulation": by_simulation}
    _atomic_write_json(_index_path(), payload)
    return payload


def update_report_index(report_id: str, meta: Dict[str, Any]) -> None:
    """
    Upsert one report in the index from meta (same shape as meta.json / Report.to_dict()).
    Call immediately after a successful meta.json write.
    """
    with _report_index_file_lock():
        rid = meta.get("report_id") or report_id
        sid = meta.get("simulation_id")
        data = _read_index()
        if data is None:
            by_simulation: Dict[str, List[Dict[str, Any]]] = {}
        else:
            by_simulation = {
                k: [dict(x) for x in (v or [])]
                for k, v in (data.get("by_simulation") or {}).items()
                if isinstance(v, list)
            }

        for lst in by_simulation.values():
            lst[:] = [e for e in lst if str(e.get("report_id")) != str(rid)]

        if sid:
            entry = {
                "report_id": str(rid),
                "created_at": meta.get("created_at", ""),
                "status": meta.get("status", ""),
            }
            cur = [
                e
                for e in by_simulation.get(str(sid), [])
                if str(e.get("report_id")) != str(rid)
            ]
            cur.append(entry)
            cur.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            by_simulation[str(sid)] = cur

        payload = {"version": _INDEX_VERSION, "by_simulation": by_simulation}
        _atomic_write_json(_index_path(), payload)


def remove_report_from_index(report_id: str) -> None:
    """Remove report_id from all simulation buckets. Call when deleting a report."""
    with _report_index_file_lock():
        data = _read_index()
        if data is None:
            return
        by_simulation = {
            k: [dict(x) for x in (v or [])]
            for k, v in (data.get("by_simulation") or {}).items()
            if isinstance(v, list)
        }
        changed = False
        for lst in by_simulation.values():
            before = len(lst)
            lst[:] = [e for e in lst if str(e.get("report_id")) != str(report_id)]
            if len(lst) != before:
                changed = True
        if not changed:
            return
        by_simulation = {k: v for k, v in by_simulation.items() if v}
        payload = {"version": _INDEX_VERSION, "by_simulation": by_simulation}
        _atomic_write_json(_index_path(), payload)


def get_reports_for_simulation(simulation_id: str) -> List[Dict[str, Any]]:
    """
    Return report summary dicts for simulation_id, newest created_at first.
    Uses the index when present; if missing, scans disk once and rebuilds the index.
    If the index lists reports that no longer exist on disk, rebuilds the index once.
    """
    idx = _read_index()
    if idx is None:
        matches = _scan_reports_dir_for_simulation(simulation_id)
        try:
            _serialized_rebuild_report_index()
        except Exception as exc:
            logger.warning("build_report_index after missing index failed: %s", exc)
        return sorted(matches, key=lambda x: x.get("created_at", ""), reverse=True)

    raw = idx.get("by_simulation", {}).get(simulation_id)
    if not isinstance(raw, list):
        raw = []
    entries = [
        dict(x) for x in raw if isinstance(x, dict) and x.get("report_id")
    ]
    filtered = [e for e in entries if _meta_exists(str(e["report_id"]))]
    if len(filtered) != len(entries):
        try:
            _serialized_rebuild_report_index()
            idx2 = _read_index()
            if idx2:
                raw2 = idx2.get("by_simulation", {}).get(simulation_id)
                if isinstance(raw2, list):
                    entries = [
                        dict(x)
                        for x in raw2
                        if isinstance(x, dict) and x.get("report_id")
                    ]
                    filtered = [e for e in entries if _meta_exists(str(e["report_id"]))]
                else:
                    filtered = []
            else:
                filtered = _scan_reports_dir_for_simulation(simulation_id)
        except Exception as exc:
            logger.warning("rebuild index after stale entries failed: %s", exc)
            filtered = [e for e in entries if _meta_exists(str(e["report_id"]))]

    return sorted(filtered, key=lambda x: x.get("created_at", ""), reverse=True)
