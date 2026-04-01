"""Simulation API — create, prepare, list, profiles, config."""
import json
import os
import sqlite3
from datetime import datetime
from typing import Optional
from flask import request, jsonify, send_file

from .. import simulation_bp
from ...config import Config
from ...core.workbench_session import WorkbenchSession
from ...services.entity_reader import get_entity_reader
from ...services.oasis_profile_generator import OasisProfileGenerator
from ...services.simulation_manager import SimulationManager, SimulationStatus
from ...services.simulation_runner import SimulationRunner
from ...tools.simulation_support import check_simulation_prepared as tool_check_simulation_prepared
from ...models.project import ProjectManager
from ...services.report_simulation_index import get_reports_for_simulation

from .common import logger


def _recent_posts_summary(simulation_id: str, platform: str, limit: int = 5) -> dict:
    """Return lightweight recent-post summary for comparison views."""
    db_path = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id, f"{platform}_simulation.db")
    if not os.path.exists(db_path):
        return {"platform": platform, "total": 0, "posts": []}

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM post ORDER BY created_at DESC LIMIT ?", (limit,))
            posts = [dict(row) for row in cursor.fetchall()]
            cursor.execute("SELECT COUNT(*) FROM post")
            total = int(cursor.fetchone()[0])
            return {"platform": platform, "total": total, "posts": posts}
    except sqlite3.OperationalError:
        return {"platform": platform, "total": 0, "posts": []}


def _simulation_compare_payload(simulation_id: str) -> dict:
    manager = SimulationManager()
    state = manager.get_simulation(simulation_id)
    if not state:
        raise FileNotFoundError(f"Simulation not found: {simulation_id}")

    run_state = SimulationRunner.get_run_state(simulation_id)
    timeline = SimulationRunner.get_timeline(simulation_id=simulation_id)
    top_agents = SimulationRunner.get_agent_stats(simulation_id)[:5]

    return {
        "simulation": state.to_dict(),
        "run_state": run_state.to_dict() if run_state else None,
        "timeline": timeline,
        "timeline_tail": timeline[-8:],
        "top_agents": top_agents,
        "posts": {
            "twitter": _recent_posts_summary(simulation_id, "twitter"),
            "reddit": _recent_posts_summary(simulation_id, "reddit"),
        },
    }

# ============== Simulation Management Endpoints ==============

@simulation_bp.route('/create', methods=['POST'])
def create_simulation():
    """Create a new simulation."""
    try:
        data = request.get_json() or {}

        project_id = data.get('project_id')
        if not project_id:
            return jsonify({
                "success": False,
                "error": "Please provide project_id"
            }), 400

        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"Project not found: {project_id}"
            }), 404

        graph_id = data.get('graph_id') or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Project graph has not been built yet. Please call /api/graph/build first"
            }), 400

        session = WorkbenchSession.open(project_id=project_id, graph_id=graph_id, metadata={"entrypoint": "api.simulation.create"})
        state = session.create_simulation(
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=data.get('enable_twitter', True),
            enable_reddit=data.get('enable_reddit', True),
        )

        response_data = state.to_dict()
        response_data['session_id'] = session.session_id
        return jsonify({
            "success": True,
            "data": response_data
        })

    except Exception as e:
        logger.error(f"Failed to create simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def _check_simulation_prepared(simulation_id: str) -> tuple:
    """Compatibility wrapper around the shared simulation preparation check."""
    return tool_check_simulation_prepared(simulation_id)


@simulation_bp.route('/prepare', methods=['POST'])
def prepare_simulation():
    """Prepare the simulation environment."""
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        session = WorkbenchSession.open(simulation_id=simulation_id, metadata={"entrypoint": "api.simulation.prepare"})
        result = session.start_simulation_preparation(
            simulation_id=simulation_id,
            entity_types=data.get('entity_types'),
            use_llm_for_profiles=data.get('use_llm_for_profiles', True),
            parallel_profile_count=data.get('parallel_profile_count', 5),
            force_regenerate=data.get('force_regenerate', False),
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
        logger.error(f"Failed to start preparation task: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/prepare/status', methods=['POST'])
def get_prepare_status():
    """
    Query preparation task progress

    Supports two query methods:
    1. Query ongoing task progress by task_id
    2. Check if preparation is already complete by simulation_id

    Request (JSON):
        {
            "task_id": "task_xxxx",          // Optional, task_id returned by prepare
            "simulation_id": "sim_xxxx"      // Optional, simulation ID (for checking completed preparation)
        }

    Response:
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|ready",
                "progress": 45,
                "message": "...",
                "already_prepared": true|false,  // Whether preparation is already complete
                "prepare_info": {...}            // Detailed info when preparation is complete
            }
        }
    """
    from ...models.task import TaskManager
    
    try:
        data = request.get_json() or {}
        
        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        
        # If simulation_id is provided, first check if preparation is already complete
        if simulation_id:
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            if is_prepared:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "progress": 100,
                        "message": "Preparation already complete",
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
        
        # If no task_id, return error
        if not task_id:
            if simulation_id:
                # Has simulation_id but preparation is not complete
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "not_started",
                        "progress": 0,
                        "message": "Preparation has not started yet. Please call /api/simulation/prepare to begin",
                        "already_prepared": False
                    }
                })
            return jsonify({
                "success": False,
                "error": "Please provide task_id or simulation_id"
            }), 400
        
        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            # Task does not exist, but if simulation_id is provided, check if preparation is complete
            if simulation_id:
                is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
                if is_prepared:
                    return jsonify({
                        "success": True,
                        "data": {
                            "simulation_id": simulation_id,
                            "task_id": task_id,
                            "status": "ready",
                            "progress": 100,
                            "message": "Task completed (preparation work already exists)",
                            "already_prepared": True,
                            "prepare_info": prepare_info
                        }
                    })
            
            return jsonify({
                "success": False,
                "error": f"Task not found: {task_id}"
            }), 404
        
        task_dict = task.to_dict()
        task_dict["already_prepared"] = False
        
        return jsonify({
            "success": True,
            "data": task_dict
        })
        
    except Exception as e:
        logger.error(f"Failed to query task status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id: str):
    """Get simulation status"""
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404

        result = state.to_dict()

        # If simulation is ready, attach run instructions
        if state.status == SimulationStatus.READY:
            result["run_instructions"] = manager.get_run_instructions(simulation_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Failed to get simulation status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/compare', methods=['POST'])
def compare_simulations():
    """Compare two simulations by state, timeline, top agents, and recent posts."""
    try:
        data = request.get_json() or {}
        simulation_id_a = data.get('simulation_id_a')
        simulation_id_b = data.get('simulation_id_b')

        if not simulation_id_a or not simulation_id_b:
            return jsonify({
                "success": False,
                "error": "simulation_id_a and simulation_id_b are required"
            }), 400

        payload_a = _simulation_compare_payload(simulation_id_a)
        payload_b = _simulation_compare_payload(simulation_id_b)

        sim_a = payload_a["simulation"]
        sim_b = payload_b["simulation"]
        delta = {
            "entities_count": sim_b.get("entities_count", 0) - sim_a.get("entities_count", 0),
            "profiles_count": sim_b.get("profiles_count", 0) - sim_a.get("profiles_count", 0),
            "current_round": (payload_b["run_state"] or {}).get("current_round", 0) - (payload_a["run_state"] or {}).get("current_round", 0),
            "total_posts_twitter": payload_b["posts"]["twitter"]["total"] - payload_a["posts"]["twitter"]["total"],
            "total_posts_reddit": payload_b["posts"]["reddit"]["total"] - payload_a["posts"]["reddit"]["total"],
        }

        return jsonify({
            "success": True,
            "data": {
                "simulation_a": payload_a,
                "simulation_b": payload_b,
                "delta": delta,
            }
        })

    except FileNotFoundError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404

    except Exception as e:
        logger.error(f"Failed to compare simulations: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/list', methods=['GET'])
def list_simulations():
    """
    List all simulations

    Query parameters:
        project_id: Filter by project ID (optional)
    """
    try:
        project_id = request.args.get('project_id')
        
        manager = SimulationManager()
        simulations = manager.list_simulations(project_id=project_id)
        
        return jsonify({
            "success": True,
            "data": [s.to_dict() for s in simulations],
            "count": len(simulations)
        })
        
    except Exception as e:
        logger.error(f"Failed to list simulations: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def _get_report_id_for_simulation(simulation_id: str) -> Optional[str]:
    """
    Latest report_id for a simulation (by meta created_at).

    Uses report_simulation_index.json when present; otherwise scans reports once
    and rebuilds the index (see get_reports_for_simulation).
    """
    try:
        entries = get_reports_for_simulation(simulation_id)
        if not entries:
            return None
        return entries[0].get("report_id")
    except Exception as e:
        logger.warning("Failed to find report for simulation %s: %s", simulation_id, e)
        return None


@simulation_bp.route('/history', methods=['GET'])
def get_simulation_history():
    """
    Get historical simulation list (with project details)

    Used for homepage historical project display. Returns a simulation list enriched with
    project name, description, and other detailed information.
    Each item's ``version`` is ``Config.VERSION`` (``mirofish-backend`` distribution / pyproject).

    Query parameters:
        limit: Maximum number of results (default 20)

    Response:
        {
            "success": true,
            "data": [
                {
                    "simulation_id": "sim_xxxx",
                    "project_id": "proj_xxxx",
                    "project_name": "WHU Public Opinion Analysis",
                    "simulation_requirement": "If Wuhan University releases...",
                    "status": "completed",
                    "entities_count": 68,
                    "profiles_count": 68,
                    "entity_types": ["Student", "Professor", ...],
                    "created_at": "2024-12-10",
                    "updated_at": "2024-12-10",
                    "total_rounds": 120,
                    "current_round": 120,
                    "report_id": "report_xxxx",
                    "version": "v0.1.0"
                },
                ...
            ],
            "count": 7
        }
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        
        manager = SimulationManager()
        simulations = manager.list_simulations()[:limit]
        
        # Enrich simulation data, read only from Simulation files
        enriched_simulations = []
        for sim in simulations:
            sim_dict = sim.to_dict()
            
            # Get simulation configuration info (read simulation_requirement from simulation_config.json)
            config = manager.get_simulation_config(sim.simulation_id)
            if config:
                sim_dict["simulation_requirement"] = config.get("simulation_requirement", "")
                time_config = config.get("time_config", {})
                sim_dict["total_simulation_hours"] = time_config.get("total_simulation_hours", 0)
                # Recommended rounds (fallback value)
                recommended_rounds = int(
                    time_config.get("total_simulation_hours", 0) * 60 / 
                    max(time_config.get("minutes_per_round", 60), 1)
                )
            else:
                sim_dict["simulation_requirement"] = ""
                sim_dict["total_simulation_hours"] = 0
                recommended_rounds = 0
            
            # Get run state (read user-configured actual rounds from run_state.json)
            run_state = SimulationRunner.get_run_state(sim.simulation_id)
            if run_state:
                sim_dict["current_round"] = run_state.current_round
                sim_dict["runner_status"] = run_state.runner_status.value
                # Use user-configured total_rounds; fall back to recommended rounds if not set
                sim_dict["total_rounds"] = run_state.total_rounds if run_state.total_rounds > 0 else recommended_rounds
            else:
                sim_dict["current_round"] = 0
                sim_dict["runner_status"] = "idle"
                sim_dict["total_rounds"] = recommended_rounds
            
            # Get the associated project's file list (up to 3)
            project = ProjectManager.get_project(sim.project_id)
            if project and hasattr(project, 'files') and project.files:
                sim_dict["files"] = [
                    {"filename": f.get("filename", "Unknown file")}
                    for f in project.files[:3]
                ]
            else:
                sim_dict["files"] = []
            
            # Get the associated report_id (find the latest report for this simulation)
            sim_dict["report_id"] = _get_report_id_for_simulation(sim.simulation_id)
            
            sim_dict["version"] = Config.VERSION
            
            # Format date
            try:
                created_date = sim_dict.get("created_at", "")[:10]
                sim_dict["created_date"] = created_date
            except Exception:
                sim_dict["created_date"] = ""
            
            enriched_simulations.append(sim_dict)
        
        return jsonify({
            "success": True,
            "data": enriched_simulations,
            "count": len(enriched_simulations)
        })
        
    except Exception as e:
        logger.error(f"Failed to get simulation history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>/profiles', methods=['GET'])
def get_simulation_profiles(simulation_id: str):
    """
    Get simulation Agent Profiles

    Query parameters:
        platform: Platform type (reddit/twitter, default reddit)
    """
    try:
        platform = request.args.get('platform', 'reddit')
        
        manager = SimulationManager()
        profiles = manager.get_profiles(simulation_id, platform=platform)
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "count": len(profiles),
                "profiles": profiles
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"Failed to get profiles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>/profiles/realtime', methods=['GET'])
def get_simulation_profiles_realtime(simulation_id: str):
    """
    Get simulation Agent Profiles in real-time (for live progress viewing during generation)

    Differences from the /profiles endpoint:
    - Reads files directly, bypassing SimulationManager
    - Suitable for real-time viewing during the generation process
    - Returns additional metadata (e.g., file modification time, whether generation is in progress)

    Query parameters:
        platform: Platform type (reddit/twitter, default reddit)

    Response:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "platform": "reddit",
                "count": 15,
                "total_expected": 93,  // Expected total (if available)
                "is_generating": true,  // Whether generation is in progress
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "profiles": [...]
            }
        }
    """
    try:
        platform = request.args.get('platform', 'reddit')
        
        # Get simulation directory
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)

        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404

        # Determine file path
        if platform == "reddit":
            profiles_file = os.path.join(sim_dir, "reddit_profiles.json")
        else:
            profiles_file = os.path.join(sim_dir, "twitter_profiles.csv")
        
        # Check if file exists
        file_exists = os.path.exists(profiles_file)
        profiles = []
        file_modified_at = None
        
        if file_exists:
            # Get file modification time
            file_stat = os.stat(profiles_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                if platform == "reddit":
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        profiles = json.load(f)
                else:
                    profiles = SimulationManager._load_twitter_profiles_csv(profiles_file)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to read profiles file (possibly being written): {e}")
                profiles = []
        
        # Check if generation is in progress (determined via state.json)
        is_generating = False
        total_expected = None

        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    total_expected = state_data.get("entities_count")
            except Exception as exc:
                logger.warning("Failed to read simulation state for profiles: %s", exc)

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "platform": platform,
                "count": len(profiles),
                "total_expected": total_expected,
                "is_generating": is_generating,
                "file_exists": file_exists,
                "file_modified_at": file_modified_at,
                "profiles": profiles
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get real-time profiles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>/config/realtime', methods=['GET'])
def get_simulation_config_realtime(simulation_id: str):
    """
    Get simulation configuration in real-time (for live progress viewing during generation)

    Differences from the /config endpoint:
    - Reads files directly, bypassing SimulationManager
    - Suitable for real-time viewing during the generation process
    - Returns additional metadata (e.g., file modification time, whether generation is in progress)
    - Can return partial information even if configuration generation is not yet complete

    Response:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "is_generating": true,  // Whether generation is in progress
                "generation_stage": "generating_config",  // Current generation stage
                "config": {...}  // Configuration content (if exists)
            }
        }
    """
    try:
        # Get simulation directory
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)

        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404

        # Configuration file path
        config_file = os.path.join(sim_dir, "simulation_config.json")
        
        # Check if file exists
        file_exists = os.path.exists(config_file)
        config = None
        file_modified_at = None
        
        if file_exists:
            # Get file modification time
            file_stat = os.stat(config_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to read config file (possibly being written): {e}")
                config = None
        
        # Check if generation is in progress (determined via state.json)
        is_generating = False
        generation_stage = None
        config_generated = False
        
        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    config_generated = state_data.get("config_generated", False)
                    
                    # Determine current stage
                    if is_generating:
                        if state_data.get("profiles_generated", False):
                            generation_stage = "generating_config"
                        else:
                            generation_stage = "generating_profiles"
                    elif status == "ready":
                        generation_stage = "completed"
            except Exception as exc:
                logger.warning("Failed to read simulation state for config: %s", exc)

        # Build response data
        response_data = {
            "simulation_id": simulation_id,
            "file_exists": file_exists,
            "file_modified_at": file_modified_at,
            "is_generating": is_generating,
            "generation_stage": generation_stage,
            "config_generated": config_generated,
            "config": config
        }
        
        # If configuration exists, extract some key statistics
        if config:
            response_data["summary"] = {
                "total_agents": len(config.get("agent_configs", [])),
                "simulation_hours": config.get("time_config", {}).get("total_simulation_hours"),
                "initial_posts_count": len(config.get("event_config", {}).get("initial_posts", [])),
                "hot_topics_count": len(config.get("event_config", {}).get("hot_topics", [])),
                "has_twitter_config": "twitter_config" in config,
                "has_reddit_config": "reddit_config" in config,
                "generated_at": config.get("generated_at"),
                "llm_model": config.get("llm_model")
            }
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get real-time config: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>/config', methods=['GET'])
def get_simulation_config(simulation_id: str):
    """
    Get simulation configuration (complete configuration intelligently generated by LLM)

    Returns:
        - time_config: Time configuration (simulation duration, rounds, peak/off-peak periods)
        - agent_configs: Activity configuration for each Agent (activity level, posting frequency, stance, etc.)
        - event_config: Event configuration (initial posts, hot topics)
        - platform_configs: Platform configuration
        - generation_reasoning: LLM's configuration reasoning explanation
    """
    try:
        manager = SimulationManager()
        config = manager.get_simulation_config(simulation_id)
        
        if not config:
            return jsonify({
                "success": False,
                "error": "Simulation configuration does not exist. Please call the /prepare endpoint first"
            }), 404
        
        return jsonify({
            "success": True,
            "data": config
        })
        
    except Exception as e:
        logger.error(f"Failed to get configuration: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>/config/download', methods=['GET'])
def download_simulation_config(simulation_id: str):
    """Download simulation configuration file"""
    try:
        manager = SimulationManager()
        sim_dir = manager._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return jsonify({
                "success": False,
                "error": "Configuration file does not exist. Please call the /prepare endpoint first"
            }), 404
        
        return send_file(
            config_path,
            as_attachment=True,
            download_name="simulation_config.json"
        )
        
    except Exception as e:
        logger.error(f"Failed to download configuration: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/script/<script_name>/download', methods=['GET'])
def download_simulation_script(script_name: str):
    """
    Download simulation run script file (shared scripts located in backend/scripts/)

    Allowed script_name values:
        - run_twitter_simulation.py
        - run_reddit_simulation.py
        - run_parallel_simulation.py
        - action_logger.py
    """
    try:
        # Scripts are located in the backend/scripts/ directory
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        # Validate script name
        allowed_scripts = [
            "run_twitter_simulation.py",
            "run_reddit_simulation.py", 
            "run_parallel_simulation.py",
            "action_logger.py"
        ]
        
        if script_name not in allowed_scripts:
            return jsonify({
                "success": False,
                "error": f"Unknown script: {script_name}, allowed: {allowed_scripts}"
            }), 400
        
        script_path = os.path.join(scripts_dir, script_name)
        
        if not os.path.exists(script_path):
            return jsonify({
                "success": False,
                "error": f"Script file does not exist: {script_name}"
            }), 404
        
        return send_file(
            script_path,
            as_attachment=True,
            download_name=script_name
        )
        
    except Exception as e:
        logger.error(f"Failed to download script: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Profile Generation Endpoints (Standalone Use) ==============

@simulation_bp.route('/generate-profiles', methods=['POST'])
def generate_profiles():
    """
    Generate OASIS Agent Profiles directly from the graph (without creating a simulation)

    Request (JSON):
        {
            "graph_id": "mirofish_xxxx",     // Required
            "entity_types": ["Student"],      // Optional
            "use_llm": true,                  // Optional
            "platform": "reddit"              // Optional
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Please provide graph_id"
            }), 400
        
        entity_types = data.get('entity_types')
        use_llm = data.get('use_llm', True)
        platform = data.get('platform', 'reddit')
        
        reader = get_entity_reader()
        filtered = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=True
        )
        
        if filtered.filtered_count == 0:
            return jsonify({
                "success": False,
                "error": "No entities matching the criteria were found"
            }), 400
        
        generator = OasisProfileGenerator()
        profiles = generator.generate_profiles_from_entities(
            entities=filtered.entities,
            use_llm=use_llm
        )
        
        if platform == "reddit":
            profiles_data = [p.to_reddit_format() for p in profiles]
        elif platform == "twitter":
            profiles_data = [p.to_twitter_format() for p in profiles]
        else:
            profiles_data = [p.to_dict() for p in profiles]
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "entity_types": list(filtered.entity_types),
                "count": len(profiles_data),
                "profiles": profiles_data
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to generate profiles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
