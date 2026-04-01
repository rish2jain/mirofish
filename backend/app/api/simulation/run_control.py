"""Simulation API — run control, actions, timeline, posts."""

import json
import os
import shutil
import time
from contextlib import closing

from flask import request, jsonify, Response

from .. import simulation_bp
from ...core.workbench_session import WorkbenchSession
from ...services.simulation_manager import SimulationManager, SimulationStatus
from ...services.simulation_runner import SimulationRunner

from .common import (
    _reject_unsafe_simulation_id,
    _resolved_simulation_dir_or_error,
    logger,
)

# ============== Simulation Run Control Endpoints ==============


@simulation_bp.route("/start", methods=["POST"])
def start_simulation():
    """Start running the simulation."""
    try:
        data = request.get_json() or {}

        simulation_id = data.get("simulation_id")
        if not simulation_id:
            return jsonify({"success": False, "error": "Please provide simulation_id"}), 400

        session = WorkbenchSession.open(
            simulation_id=simulation_id, metadata={"entrypoint": "api.simulation.start"}
        )
        result = session.start_simulation_run(
            simulation_id=simulation_id,
            platform=data.get("platform", "parallel"),
            max_rounds=data.get("max_rounds"),
            enable_graph_memory_update=data.get("enable_graph_memory_update", False),
            force=data.get("force", False),
        )

        return jsonify({"success": True, "data": result})

    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        logger.error(f"Failed to start simulation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route("/stop", methods=["POST"])
def stop_simulation():
    """
    Stop the simulation

    Request (JSON):
        {
            "simulation_id": "sim_xxxx"  // Required, simulation ID
        }

    Response:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "stopped",
                "completed_at": "2025-12-01T12:00:00"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get("simulation_id")
        if not simulation_id:
            return jsonify({"success": False, "error": "Please provide simulation_id"}), 400

        run_state = SimulationRunner.stop_simulation(simulation_id)

        # Update simulation status
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.PAUSED
            manager._save_simulation_state(state)

        return jsonify({"success": True, "data": run_state.to_dict()})

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        logger.error(f"Failed to stop simulation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route("/delete", methods=["POST"])
def delete_simulation():
    """
    Remove a simulation directory and in-memory bookkeeping (best-effort).

    Used when a client created a simulation but failed during prepare/start.
    Stops an active runner when possible, then deletes disk state under uploads.
    Each cleanup step runs independently; failures are logged and returned under
    ``data.cleanup_issues`` when present.
    """
    try:
        data = request.get_json() or {}
        simulation_id = data.get("simulation_id")
        if not simulation_id:
            return jsonify({"success": False, "error": "Please provide simulation_id"}), 400

        id_err = _reject_unsafe_simulation_id(simulation_id)
        if id_err:
            return jsonify({"success": False, "error": id_err}), 400

        sim_dir, path_err = _resolved_simulation_dir_or_error(simulation_id)
        if path_err or not sim_dir:
            return jsonify({"success": False, "error": path_err or "Invalid simulation path"}), 400

        cleanup_issues: list[dict[str, str]] = []

        try:
            SimulationRunner.stop_simulation(simulation_id)
        except ValueError as e:
            logger.debug(
                "delete_simulation: stop_simulation skipped for %s: %s",
                simulation_id,
                e,
            )
        except Exception as e:
            logger.warning(
                "delete_simulation: stop_simulation failed for %s: %s",
                simulation_id,
                e,
                exc_info=True,
            )
            cleanup_issues.append({"step": "stop_simulation", "error": str(e)})

        try:
            cleanup_result = SimulationRunner.cleanup_simulation_logs(simulation_id)
            if cleanup_result:
                for err in cleanup_result.get("errors") or []:
                    logger.warning(
                        "delete_simulation: cleanup_simulation_logs partial failure %s: %s",
                        simulation_id,
                        err,
                    )
                    cleanup_issues.append({"step": "cleanup_simulation_logs", "error": str(err)})
        except Exception as e:
            logger.warning(
                "delete_simulation: cleanup_simulation_logs failed for %s: %s",
                simulation_id,
                e,
                exc_info=True,
            )
            cleanup_issues.append({"step": "cleanup_simulation_logs", "error": str(e)})

        try:
            manager = SimulationManager()
            manager.remove_simulation(simulation_id)
        except Exception as e:
            logger.warning(
                "delete_simulation: remove_simulation failed for %s: %s",
                simulation_id,
                e,
                exc_info=True,
            )
            cleanup_issues.append({"step": "remove_simulation", "error": str(e)})

        removed_dir = False
        if os.path.isdir(sim_dir):
            try:
                shutil.rmtree(sim_dir)
                removed_dir = True
            except Exception as e:
                logger.warning(
                    "delete_simulation: rmtree failed path=%s simulation_id=%s: %s",
                    sim_dir,
                    simulation_id,
                    e,
                    exc_info=True,
                )
                cleanup_issues.append(
                    {"step": "remove_directory", "path": sim_dir, "error": str(e)}
                )

        data_out = {
            "simulation_id": simulation_id,
            "removed_directory": removed_dir,
        }
        if cleanup_issues:
            data_out["cleanup_issues"] = cleanup_issues

        return jsonify({"success": True, "data": data_out})

    except Exception as e:
        logger.error(f"Failed to delete simulation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============== Real-time Status Monitoring Endpoints ==============


@simulation_bp.route("/<simulation_id>/run-status", methods=["GET"])
def get_run_status(simulation_id: str):
    """
    Get real-time simulation run status (for frontend polling)

    Response:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                "total_rounds": 144,
                "progress_percent": 3.5,
                "simulated_hours": 2,
                "total_simulation_hours": 72,
                "twitter_running": true,
                "reddit_running": true,
                "twitter_actions_count": 150,
                "reddit_actions_count": 200,
                "total_actions_count": 350,
                "started_at": "2025-12-01T10:00:00",
                "updated_at": "2025-12-01T10:30:00"
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)

        if not run_state:
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "runner_status": "idle",
                        "current_round": 0,
                        "total_rounds": 0,
                        "progress_percent": 0,
                        "twitter_actions_count": 0,
                        "reddit_actions_count": 0,
                        "total_actions_count": 0,
                    },
                }
            )

        return jsonify({"success": True, "data": run_state.to_dict()})

    except Exception as e:
        logger.error(f"Failed to get run status: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route("/<simulation_id>/run-status/stream", methods=["GET"])
def stream_run_status(simulation_id: str):
    """
    Server-Sent Events stream of run status (same payload shape as GET run-status).

    Emits JSON lines as SSE `data:` until runner reaches a terminal state or max duration.
    """
    id_err = _reject_unsafe_simulation_id(simulation_id)
    if id_err:
        return jsonify({"success": False, "error": id_err}), 400

    idle_payload = {
        "simulation_id": simulation_id,
        "runner_status": "idle",
        "current_round": 0,
        "total_rounds": 0,
        "progress_percent": 0,
        "twitter_actions_count": 0,
        "reddit_actions_count": 0,
        "total_actions_count": 0,
    }

    def generate():
        delay_sec = 2.0
        max_delay_sec = 12.0
        max_iterations = 1350  # ~up to 45+ minutes with backoff cap
        terminal = frozenset({"completed", "stopped", "failed"})

        for _ in range(max_iterations):
            try:
                run_state = SimulationRunner.get_run_state(simulation_id)
                if not run_state:
                    payload = idle_payload
                else:
                    payload = run_state.to_dict()

                chunk = json.dumps({"success": True, "data": payload}, ensure_ascii=False)
                yield f"data: {chunk}\n\n"

                status = (payload.get("runner_status") or "").lower()
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


@simulation_bp.route("/<simulation_id>/run-status/detail", methods=["GET"])
def get_run_status_detail(simulation_id: str):
    """
    Get detailed simulation run status (including all actions)

    Used for frontend real-time activity display

    Query parameters:
        platform: Filter by platform (twitter/reddit, optional)

    Response:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                ...
                "all_actions": [
                    {
                        "round_num": 5,
                        "timestamp": "2025-12-01T10:30:00",
                        "platform": "twitter",
                        "agent_id": 3,
                        "agent_name": "Agent Name",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "..."},
                        "result": null,
                        "success": true
                    },
                    ...
                ],
                "twitter_actions": [...],  # All actions on the Twitter platform
                "reddit_actions": [...]    # All actions on the Reddit platform
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        platform_filter = request.args.get("platform")

        if not run_state:
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "runner_status": "idle",
                        "all_actions": [],
                        "twitter_actions": [],
                        "reddit_actions": [],
                    },
                }
            )

        # Get the complete action list
        all_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id, platform=platform_filter
        )

        # Get actions by platform
        twitter_actions = (
            SimulationRunner.get_all_actions(simulation_id=simulation_id, platform="twitter")
            if not platform_filter or platform_filter == "twitter"
            else []
        )

        reddit_actions = (
            SimulationRunner.get_all_actions(simulation_id=simulation_id, platform="reddit")
            if not platform_filter or platform_filter == "reddit"
            else []
        )

        # Get actions for the current round (recent_actions only shows the latest round)
        current_round = run_state.current_round
        recent_actions = (
            SimulationRunner.get_all_actions(
                simulation_id=simulation_id, platform=platform_filter, round_num=current_round
            )
            if current_round > 0
            else []
        )

        # Get basic status information
        result = run_state.to_dict()
        result["all_actions"] = [a.to_dict() for a in all_actions]
        result["twitter_actions"] = [a.to_dict() for a in twitter_actions]
        result["reddit_actions"] = [a.to_dict() for a in reddit_actions]
        result["rounds_count"] = len(run_state.rounds)
        # recent_actions only shows content from both platforms for the latest round
        result["recent_actions"] = [a.to_dict() for a in recent_actions]

        return jsonify({"success": True, "data": result})

    except Exception as e:
        logger.error(f"Failed to get detailed status: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route("/<simulation_id>/actions", methods=["GET"])
def get_simulation_actions(simulation_id: str):
    """
    Get Agent action history from the simulation

    Query parameters:
        limit: Number of results (default 100)
        offset: Offset (default 0)
        platform: Filter by platform (twitter/reddit)
        agent_id: Filter by Agent ID
        round_num: Filter by round number

    Response:
        {
            "success": true,
            "data": {
                "count": 100,
                "actions": [...]
            }
        }
    """
    try:
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        platform = request.args.get("platform")
        agent_id = request.args.get("agent_id", type=int)
        round_num = request.args.get("round_num", type=int)

        actions = SimulationRunner.get_actions(
            simulation_id=simulation_id,
            limit=limit,
            offset=offset,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num,
        )

        return jsonify(
            {
                "success": True,
                "data": {"count": len(actions), "actions": [a.to_dict() for a in actions]},
            }
        )

    except Exception as e:
        logger.error(f"Failed to get action history: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route("/<simulation_id>/timeline", methods=["GET"])
def get_simulation_timeline(simulation_id: str):
    """
    Get simulation timeline (summarized by round)

    Used for frontend progress bar and timeline view display

    Query parameters:
        start_round: Starting round (default 0)
        end_round: Ending round (default all)

    Returns summary information for each round
    """
    try:
        start_round = request.args.get("start_round", 0, type=int)
        end_round = request.args.get("end_round", type=int)

        timeline = SimulationRunner.get_timeline(
            simulation_id=simulation_id, start_round=start_round, end_round=end_round
        )

        return jsonify(
            {"success": True, "data": {"rounds_count": len(timeline), "timeline": timeline}}
        )

    except Exception as e:
        logger.error(f"Failed to get timeline: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route("/<simulation_id>/agent-stats", methods=["GET"])
def get_agent_stats(simulation_id: str):
    """
    Get statistics for each Agent

    Used for frontend Agent activity rankings, action distribution, etc.
    """
    try:
        stats = SimulationRunner.get_agent_stats(simulation_id)

        return jsonify({"success": True, "data": {"agents_count": len(stats), "stats": stats}})

    except Exception as e:
        logger.error(f"Failed to get Agent statistics: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============== Database Query Endpoints ==============


@simulation_bp.route("/<simulation_id>/posts", methods=["GET"])
def get_simulation_posts(simulation_id: str):
    """
    Get posts from the simulation

    Query parameters:
        platform: Platform type (twitter/reddit)
        limit: Number of results (default 50)
        offset: Offset

    Returns a list of posts (read from SQLite database)
    """
    try:
        id_err = _reject_unsafe_simulation_id(simulation_id)
        if id_err:
            return jsonify({"success": False, "error": id_err}), 400

        platform = request.args.get("platform", "reddit")
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)

        from ...config import Config

        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)

        db_file = f"{platform}_simulation.db"
        db_path = os.path.join(sim_dir, db_file)

        if not os.path.exists(db_path):
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "platform": platform,
                        "count": 0,
                        "posts": [],
                        "message": "Database does not exist, simulation may not have been run yet",
                    },
                }
            )

        import sqlite3

        with closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT * FROM post 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """,
                    (limit, offset),
                )

                posts = [dict(row) for row in cursor.fetchall()]

                cursor.execute("SELECT COUNT(*) FROM post")
                total = cursor.fetchone()[0]

            except sqlite3.OperationalError:
                posts = []
                total = 0

        return jsonify(
            {
                "success": True,
                "data": {"platform": platform, "total": total, "count": len(posts), "posts": posts},
            }
        )

    except Exception as e:
        logger.error(f"Failed to get posts: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route("/<simulation_id>/comments", methods=["GET"])
def get_simulation_comments(simulation_id: str):
    """
    Get comments from the simulation (Reddit only)

    Query parameters:
        post_id: Filter by post ID (optional)
        limit: Number of results
        offset: Offset
    """
    try:
        id_err = _reject_unsafe_simulation_id(simulation_id)
        if id_err:
            return jsonify({"success": False, "error": id_err}), 400

        post_id = request.args.get("post_id")
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)

        from ...config import Config

        sim_dir = os.path.join(
            Config.OASIS_SIMULATION_DATA_DIR,
            simulation_id,
        )

        db_path = os.path.join(sim_dir, "reddit_simulation.db")

        if not os.path.exists(db_path):
            return jsonify({"success": True, "data": {"count": 0, "comments": []}})

        import sqlite3

        with closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                if post_id:
                    cursor.execute(
                        """
                        SELECT * FROM comment 
                        WHERE post_id = ?
                        ORDER BY created_at DESC 
                        LIMIT ? OFFSET ?
                    """,
                        (post_id, limit, offset),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM comment 
                        ORDER BY created_at DESC 
                        LIMIT ? OFFSET ?
                    """,
                        (limit, offset),
                    )

                comments = [dict(row) for row in cursor.fetchall()]

            except sqlite3.OperationalError:
                comments = []

        return jsonify({"success": True, "data": {"count": len(comments), "comments": comments}})

    except Exception as e:
        logger.error(f"Failed to get comments: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
