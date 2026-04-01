"""Batch create simulations from one request."""

from flask import request, jsonify

from .. import simulation_bp
from ...config import Config
from ...core.workbench_session import WorkbenchSession
from ...models.project import ProjectManager
from ...utils.api_auth import require_service_api_key

from .common import logger


@simulation_bp.route('/batch/create', methods=['POST'])
def batch_create_simulations():
    """
    Create multiple simulations sequentially.

    Body: { "items": [ { "project_id", "graph_id"?, "enable_twitter"?, "enable_reddit"? }, ... ] }

    Response JSON includes ``summary`` (total / succeeded / failed) and ``success`` true iff
    at least one item succeeded; per-item outcomes remain under ``data.results``.

    When MIROFISH_API_KEY is set, requires Authorization: Bearer <key>.
    """
    auth_err = require_service_api_key()
    if auth_err:
        return auth_err

    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        return jsonify({"success": False, "error": "items must be a non-empty list"}), 400

    max_items = max(1, Config.BATCH_SIM_MAX_ITEMS)
    if len(items) > max_items:
        return jsonify({"success": False, "error": f"At most {max_items} items"}), 400

    results = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            results.append({"index": i, "success": False, "error": "item must be object"})
            continue
        project_id = item.get("project_id")
        if not project_id:
            results.append({"index": i, "success": False, "error": "project_id required"})
            continue
        project = ProjectManager.get_project(project_id)
        if not project:
            results.append({"index": i, "success": False, "error": f"project not found: {project_id}"})
            continue
        graph_id = item.get("graph_id") or project.graph_id
        if not graph_id:
            results.append({"index": i, "success": False, "error": "graph_id required"})
            continue
        try:
            session = WorkbenchSession.open(
                project_id=project_id,
                graph_id=graph_id,
                metadata={"entrypoint": "api.simulation.batch_create"},
            )
            state = session.create_simulation(
                project_id=project_id,
                graph_id=graph_id,
                enable_twitter=item.get("enable_twitter", True),
                enable_reddit=item.get("enable_reddit", True),
            )
            to_dict_fn = getattr(state, "to_dict", None)
            if state is None or not callable(to_dict_fn):
                logger.error(
                    "batch item index=%s create_simulation returned invalid state "
                    "(project_id=%s graph_id=%s): %r",
                    i,
                    project_id,
                    graph_id,
                    state,
                )
                results.append(
                    {
                        "index": i,
                        "success": False,
                        "error": (
                            "create_simulation did not return a simulation state "
                            "with a callable to_dict()"
                        ),
                    }
                )
                continue
            wb_state = getattr(session, "state", None)
            if wb_state is None:
                logger.error(
                    "batch item index=%s workbench session has no state "
                    "(project_id=%s graph_id=%s)",
                    i,
                    project_id,
                    graph_id,
                )
                results.append(
                    {
                        "index": i,
                        "success": False,
                        "error": "workbench session state is missing",
                    }
                )
                continue
            wb_session_id = getattr(wb_state, "session_id", None)
            if isinstance(wb_session_id, str):
                wb_session_id = wb_session_id.strip()
            if not wb_session_id:
                logger.error(
                    "batch item index=%s workbench session_id missing or empty "
                    "(project_id=%s graph_id=%s)",
                    i,
                    project_id,
                    graph_id,
                )
                results.append(
                    {
                        "index": i,
                        "success": False,
                        "error": "workbench session_id is missing or empty",
                    }
                )
                continue
            row = to_dict_fn()
            row["session_id"] = wb_session_id
            results.append({"index": i, "success": True, "data": row})
        except Exception:  # pragma: no cover - integration path
            logger.exception("batch item %s failed", i)
            results.append(
                {
                    "index": i,
                    "success": False,
                    "error": "Internal error processing item",
                }
            )

    total = len(results)
    succeeded = sum(1 for r in results if r.get("success") is True)
    failed = total - succeeded
    overall_ok = succeeded > 0

    return jsonify(
        {
            "success": overall_ok,
            "summary": {
                "total": total,
                "succeeded": succeeded,
                "failed": failed,
            },
            "data": {"results": results},
        }
    )
