"""Graph-related API routes
Uses project context mechanism with server-side persistent state
"""

import json
import os
import re
import time
from typing import Optional

from flask import Response, jsonify, request

from . import graph_bp
from ..config import Config
from ..core.workbench_session import WorkbenchSession
from ..models.project import ProjectManager, ProjectStatus
from ..models.task import TaskManager
from ..services.graph_builder import GraphBuilderService
from ..services.graph_storage import KuzuDBStorage, StorageError, get_app_graph_storage
from ..services.workflow_bundle import (
    build_export_bundle,
    diff_graph_snapshots,
    import_bundle,
    list_graph_snapshots,
    save_graph_snapshot,
)
from ..utils.api_auth import optional_user_id, require_service_api_key, require_user_header
from ..utils.logger import get_logger

# Get logger
logger = get_logger('mirofish.api')


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


_TASK_ID_SAFE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")


def _reject_unsafe_task_id(task_id: str) -> Optional[str]:
    """Return an error message if task_id is unsafe for filesystem use, else None."""
    if not isinstance(task_id, str):
        return "task_id must be a string"
    if len(task_id) > 256:
        return "Invalid task_id"
    if ".." in task_id or "/" in task_id or "\\" in task_id:
        return "Invalid task_id"
    if not _TASK_ID_SAFE_RE.match(task_id):
        return "Invalid task_id"
    return None


def _resolve_graph_id(graph_id: Optional[str] = None) -> Optional[str]:
    """Resolve a graph_id from the request or the most recent built project."""
    if graph_id:
        return graph_id

    query_graph_id = request.args.get("graph_id")
    if query_graph_id:
        return query_graph_id

    for project in ProjectManager.list_projects(limit=50):
        if project.graph_id:
            return project.graph_id
    return None


# ============== Project Management API ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """
    Get project details
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": f"Project not found: {project_id}"
        }), 404

    return jsonify({
        "success": True,
        "data": project.to_dict()
    })


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """
    List all projects
    """
    limit = request.args.get('limit', 50, type=int)
    projects = ProjectManager.list_projects(limit=limit)
    
    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in projects],
        "count": len(projects)
    })


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """
    Delete project
    """
    success = ProjectManager.delete_project(project_id)
    
    if not success:
        return jsonify({
            "success": False,
            "error": f"Project not found or deletion failed: {project_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "message": f"Project deleted: {project_id}"
    })


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """
    Reset project state (for rebuilding the graph)
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": f"Project not found: {project_id}"
        }), 404

    # Reset to ontology-generated state
    if project.ontology:
        project.status = ProjectStatus.ONTOLOGY_GENERATED
    else:
        project.status = ProjectStatus.CREATED
    
    project.graph_id = None
    project.graph_build_task_id = None
    project.error = None
    ProjectManager.save_project(project)
    
    return jsonify({
        "success": True,
        "message": f"Project reset: {project_id}",
        "data": project.to_dict()
    })


# ============== API 1: Upload Files and Generate Ontology ==============

@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """API 1: Upload files and analyze to generate ontology definition."""
    try:
        logger.info("=== Starting ontology generation ===")

        simulation_requirement = request.form.get('simulation_requirement', '')
        project_name = request.form.get('project_name', 'Unnamed Project')
        additional_context = request.form.get('additional_context', '')
        uploaded_files = request.files.getlist('files')

        session = WorkbenchSession.open(metadata={"entrypoint": "api.graph.generate_ontology"})
        result = session.generate_ontology(
            simulation_requirement=simulation_requirement,
            uploaded_files=uploaded_files,
            project_name=project_name,
            additional_context=additional_context if additional_context else None,
        )

        return jsonify({
            "success": True,
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except Exception as e:
        logger.error(f"Failed to generate ontology: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== API 2: Build Graph ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """API 2: Build graph based on project_id."""
    try:
        logger.info("=== Starting graph build ===")

        data = request.get_json() or {}
        project_id = data.get('project_id')
        if not project_id:
            return jsonify({
                "success": False,
                "error": "Please provide project_id"
            }), 400

        session = WorkbenchSession.open(project_id=project_id, metadata={"entrypoint": "api.graph.build_graph"})
        result = session.start_graph_build(
            project_id=project_id,
            graph_name=data.get('graph_name'),
            chunk_size=data.get('chunk_size'),
            chunk_overlap=data.get('chunk_overlap'),
            force=data.get('force', False),
        )

        return jsonify({
            "success": True,
            "data": result
        })

    except FileNotFoundError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except Exception as e:
        logger.error(f"Failed to start graph build: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Task Query API ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """
    Query task status
    """
    id_err = _reject_unsafe_task_id(task_id)
    if id_err:
        return jsonify({"success": False, "error": id_err}), 400

    task = TaskManager().get_task(task_id)
    
    if not task:
        return jsonify({
            "success": False,
            "error": f"Task not found: {task_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


@graph_bp.route("/task/<task_id>/sse", methods=["GET"])
def stream_task_status(task_id: str):
    """
    Server-Sent Events stream of graph/task status (same payload shape as GET /task/<id>).

    Emits JSON as SSE `data:` until task reaches a terminal state or is not found.
    """
    id_err = _reject_unsafe_task_id(task_id)
    if id_err:
        return jsonify({"success": False, "error": id_err}), 400

    def generate():
        delay_sec = 2.0
        max_delay_sec = 12.0
        max_iterations = 1350
        terminal = frozenset({"completed", "failed"})

        for _ in range(max_iterations):
            try:
                task = TaskManager().get_task(task_id)
                if not task:
                    chunk = json.dumps(
                        {"success": False, "error": f"Task not found: {task_id}"},
                        ensure_ascii=False,
                    )
                    yield f"data: {chunk}\n\n"
                    break

                payload = task.to_dict()
                chunk = json.dumps({"success": True, "data": payload}, ensure_ascii=False)
                yield f"data: {chunk}\n\n"

                status = (payload.get("status") or "").lower()
                if status in terminal:
                    break
            except Exception as exc:  # pragma: no cover - defensive stream
                err_chunk = json.dumps(
                    {"success": False, "error": str(exc)},
                    ensure_ascii=False,
                )
                yield f"data: {err_chunk}\n\n"
                break

            time.sleep(delay_sec)
            delay_sec = min(max_delay_sec, delay_sec * 1.15)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """List all tasks."""
    tasks = TaskManager().list_tasks()
    serialized_tasks = [task if isinstance(task, dict) else task.to_dict() for task in tasks]

    return jsonify(serialized_tasks)


@graph_bp.route('/nodes', methods=['GET'])
def list_graph_nodes():
    """Compatibility endpoint for listing graph nodes."""
    graph_id = _resolve_graph_id()
    if not graph_id:
        return jsonify({"success": True, "data": [], "count": 0, "graph_id": None})

    builder = GraphBuilderService()
    graph_data = builder.get_graph_data(graph_id)
    nodes = graph_data.get("nodes", [])
    return jsonify({
        "success": True,
        "data": nodes,
        "count": len(nodes),
        "graph_id": graph_id,
    })


@graph_bp.route('/edges', methods=['GET'])
def list_graph_edges():
    """Compatibility endpoint for listing graph edges."""
    graph_id = _resolve_graph_id()
    if not graph_id:
        return jsonify({"success": True, "data": [], "count": 0, "graph_id": None})

    builder = GraphBuilderService()
    graph_data = builder.get_graph_data(graph_id)
    edges = graph_data.get("edges", [])
    return jsonify({
        "success": True,
        "data": edges,
        "count": len(edges),
        "graph_id": graph_id,
    })


# ============== Graph Data API ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """
    Get graph data (nodes and edges)
    """
    try:
        builder = GraphBuilderService()
        graph_data = builder.get_graph_data(graph_id)
        
        return jsonify({
            "success": True,
            "data": graph_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """
    Delete graph
    """
    try:
        builder = GraphBuilderService()
        builder.delete_graph(graph_id)

        return jsonify({
            "success": True,
            "message": f"Graph deleted: {graph_id}"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Workflow bundle, Cypher query, snapshots ==============


def _log_import_bundle_auth_denied(check_name: str, err_response) -> None:
    """Audit log for failed auth on import-bundle (security)."""
    response, status_code = err_response
    err_msg = ""
    payload = response.get_json(silent=True)
    if isinstance(payload, dict):
        err_msg = str(payload.get("error") or "")
    auth_present = bool((request.headers.get("Authorization") or "").strip())
    user_hdr = "present" if optional_user_id() else "absent"
    logger.warning(
        "import_project_bundle: authentication denied | failed_check=%s | http_status=%s | "
        "remote_addr=%s | authorization_header_present=%s | x_mirofish_user_header=%s | "
        "error_message=%r | %s %s",
        check_name,
        status_code,
        request.remote_addr,
        auth_present,
        user_hdr,
        err_msg,
        request.method,
        request.path,
    )


@graph_bp.route("/project/<project_id>/export-bundle", methods=["GET"])
def export_project_bundle(project_id: str):
    """Export project metadata and optional graph JSON (for sharing / backup)."""
    try:
        bundle = build_export_bundle(project_id)
        return jsonify({"success": True, "data": bundle})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404


@graph_bp.route("/project/import-bundle", methods=["POST"])
def import_project_bundle():
    """Restore from export-bundle JSON.

    Enforces ``MIROFISH_API_KEY`` (``require_service_api_key``) and, when
    ``Config.MIROFISH_REQUIRE_USER_HEADER`` is set, ``X-MiroFish-User`` via
    ``require_user_header``. ``optional_user_id()`` supplies ``owner_user_id`` to
    ``import_bundle`` whenever the header is present (optional attribution).
    """
    auth_err = require_service_api_key()
    if auth_err:
        _log_import_bundle_auth_denied("require_service_api_key", auth_err)
        return auth_err
    user_err = require_user_header()
    if user_err:
        _log_import_bundle_auth_denied("require_user_header", user_err)
        return user_err
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"success": False, "error": "JSON body required"}), 400
    try:
        pid, gid = import_bundle(body, owner_user_id=optional_user_id())
        return jsonify({"success": True, "data": {"project_id": pid, "graph_id": gid}})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except StorageError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@graph_bp.route("/query", methods=["POST"])
def graph_cypher_query():
    """Read-only Cypher against a graph (Kuzu only)."""
    data = request.get_json(silent=True) or {}
    graph_id = data.get("graph_id")
    query = (data.get("query") or "").strip()
    raw_max_rows = data.get("max_rows")
    if raw_max_rows is None or raw_max_rows == "":
        max_rows = 500
    else:
        try:
            max_rows = int(raw_max_rows)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Invalid max_rows"}), 400
    if not graph_id:
        return jsonify({"success": False, "error": "graph_id required"}), 400
    if not query:
        return jsonify({"success": False, "error": "query required"}), 400
    storage = get_app_graph_storage(graph_id)
    if not isinstance(storage, KuzuDBStorage):
        return jsonify({"success": False, "error": "Cypher query requires GRAPH_BACKEND=kuzu"}), 400
    try:
        out = storage.execute_read_only_query(query, max_rows=max_rows)
        return jsonify({"success": True, "data": out})
    except StorageError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@graph_bp.route("/project/<project_id>/graph-snapshot", methods=["POST"])
def create_graph_snapshot(project_id: str):
    data = request.get_json(silent=True) or {}
    label = (data.get("label") or "snapshot").strip() or "snapshot"
    try:
        snap = save_graph_snapshot(project_id, label)
        return jsonify({"success": True, "data": snap})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@graph_bp.route("/project/<project_id>/graph-snapshots", methods=["GET"])
def get_graph_snapshots(project_id: str):
    project = ProjectManager.get_project(project_id)
    if not project:
        return jsonify({"success": False, "error": f"Project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": list_graph_snapshots(project_id)})


@graph_bp.route("/project/<project_id>/graph-diff", methods=["POST"])
def graph_diff(project_id: str):
    data = request.get_json(silent=True) or {}
    a = data.get("snapshot_a")
    b = data.get("snapshot_b")
    if not a or not b:
        return jsonify({"success": False, "error": "snapshot_a and snapshot_b required"}), 400
    try:
        diff = diff_graph_snapshots(project_id, str(a), str(b))
        return jsonify({"success": True, "data": diff})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@graph_bp.route("/project/<project_id>/export-bundle/file", methods=["GET"])
def export_project_bundle_file(project_id: str):
    """Same as export-bundle but as attachment download."""
    try:
        bundle = build_export_bundle(project_id)
        payload = json.dumps(bundle, ensure_ascii=False, indent=2)
        return Response(
            payload,
            mimetype="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="mirofish-project-{project_id}.json"'
            },
        )
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
