"""Simulation API — interview and env control."""
from flask import request, jsonify

from .. import simulation_bp
from ...services.simulation_manager import SimulationManager, SimulationStatus
from ...services.simulation_runner import SimulationRunner

from .common import logger, optimize_interview_prompt


def _merged_query_or_json(name: str, default=None):
    """Prefer URL query params; for POST, fall back to JSON body (backward compatibility)."""
    q = request.args.get(name)
    if q is not None and q != "":
        return q
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        v = body.get(name)
        if v is not None:
            return v
    return default


# ============== Interview Endpoints ==============

@simulation_bp.route('/interview', methods=['POST'])
def interview_agent():
    """
    Interview a single Agent

    Note: This feature requires the simulation environment to be in a running state
    (entered command-waiting mode after completing the simulation loop)

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",       // Required, simulation ID
            "agent_id": 0,                     // Required, Agent ID
            "prompt": "What do you think about this?",  // Required, interview question
            "platform": "twitter",             // Optional, specify platform (twitter/reddit)
                                               // When not specified: dual-platform simulation interviews both platforms simultaneously
            "timeout": 60                      // Optional, timeout in seconds, default 60
        }

    Response (platform not specified, dual-platform mode):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "What do you think about this?",
                "result": {
                    "agent_id": 0,
                    "prompt": "...",
                    "platforms": {
                        "twitter": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit": {"agent_id": 0, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }

    Response (platform specified):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "What do you think about this?",
                "result": {
                    "agent_id": 0,
                    "response": "I think...",
                    "platform": "twitter",
                    "timestamp": "2025-12-08T10:00:00"
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        agent_id = data.get('agent_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 60)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400
        
        if agent_id is None:
            return jsonify({
                "success": False,
                "error": "Please provide agent_id"
            }), 400
        
        if not prompt:
            return jsonify({
                "success": False,
                "error": "Please provide prompt (interview question)"
            }), 400

        # Validate platform parameter
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": "platform parameter can only be 'twitter' or 'reddit'"
            }), 400
        
        # Check environment status
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": "Simulation environment is not running or has been closed. Please ensure the simulation is complete and in command-waiting mode."
            }), 400
        
        # Optimize prompt, add prefix to prevent Agent from calling tools
        optimized_prompt = optimize_interview_prompt(prompt)

        result = SimulationRunner.interview_agent(
            simulation_id=simulation_id,
            agent_id=agent_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"Timed out waiting for interview response: {str(e)}"
        }), 504
        
    except Exception as e:
        logger.error(f"Interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/interview/batch', methods=['POST'])
def interview_agents_batch():
    """
    Batch interview multiple Agents

    Note: This feature requires the simulation environment to be in a running state

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",       // Required, simulation ID
            "interviews": [                    // Required, interview list
                {
                    "agent_id": 0,
                    "prompt": "What do you think about A?",
                    "platform": "twitter"      // Optional, specify the interview platform for this Agent
                },
                {
                    "agent_id": 1,
                    "prompt": "What do you think about B?"  // If platform not specified, uses the default
                }
            ],
            "platform": "reddit",              // Optional, default platform (overridden by each item's platform)
                                               // When not specified: dual-platform simulation interviews each Agent on both platforms
            "timeout": 120                     // Optional, timeout in seconds, default 120
        }

    Response:
        {
            "success": true,
            "data": {
                "interviews_count": 2,
                "result": {
                    "interviews_count": 4,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        "twitter_1": {"agent_id": 1, "response": "...", "platform": "twitter"},
                        "reddit_1": {"agent_id": 1, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        interviews = data.get('interviews')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 120)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        if not interviews or not isinstance(interviews, list):
            return jsonify({
                "success": False,
                "error": "Please provide interviews (interview list)"
            }), 400

        # Validate platform parameter
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": "platform parameter can only be 'twitter' or 'reddit'"
            }), 400

        # Validate each interview item
        for i, interview in enumerate(interviews):
            if 'agent_id' not in interview:
                return jsonify({
                    "success": False,
                    "error": f"Interview list item {i+1} is missing agent_id"
                }), 400
            if 'prompt' not in interview:
                return jsonify({
                    "success": False,
                    "error": f"Interview list item {i+1} is missing prompt"
                }), 400
            # Validate each item's platform (if present)
            item_platform = interview.get('platform')
            if item_platform and item_platform not in ("twitter", "reddit"):
                return jsonify({
                    "success": False,
                    "error": f"Interview list item {i+1} platform can only be 'twitter' or 'reddit'"
                }), 400

        # Check environment status
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": "Simulation environment is not running or has been closed. Please ensure the simulation is complete and in command-waiting mode."
            }), 400

        # Optimize each interview item's prompt, add prefix to prevent Agent from calling tools
        optimized_interviews = []
        for interview in interviews:
            optimized_interview = interview.copy()
            optimized_interview['prompt'] = optimize_interview_prompt(interview.get('prompt', ''))
            optimized_interviews.append(optimized_interview)

        result = SimulationRunner.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=optimized_interviews,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"Timed out waiting for batch interview response: {str(e)}"
        }), 504

    except Exception as e:
        logger.error(f"Batch interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/interview/all', methods=['POST'])
def interview_all_agents():
    """
    Global interview - interview all Agents using the same question

    Note: This feature requires the simulation environment to be in a running state

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",            // Required, simulation ID
            "prompt": "What is your overall view on this?",  // Required, interview question (same for all Agents)
            "platform": "reddit",                   // Optional, specify platform (twitter/reddit)
                                                    // When not specified: dual-platform simulation interviews each Agent on both platforms
            "timeout": 180                          // Optional, timeout in seconds, default 180
        }

    Response:
        {
            "success": true,
            "data": {
                "interviews_count": 50,
                "result": {
                    "interviews_count": 100,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        ...
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 180)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        if not prompt:
            return jsonify({
                "success": False,
                "error": "Please provide prompt (interview question)"
            }), 400

        # Validate platform parameter
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": "platform parameter can only be 'twitter' or 'reddit'"
            }), 400

        # Check environment status
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": "Simulation environment is not running or has been closed. Please ensure the simulation is complete and in command-waiting mode."
            }), 400

        # Optimize prompt, add prefix to prevent Agent from calling tools
        optimized_prompt = optimize_interview_prompt(prompt)

        result = SimulationRunner.interview_all_agents(
            simulation_id=simulation_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"Timed out waiting for global interview response: {str(e)}"
        }), 504

    except Exception as e:
        logger.error(f"Global interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/interview/history', methods=['GET', 'POST'])
def get_interview_history():
    """
    Get interview history

    Reads all interview records from the simulation database

    Request (GET query parameters, preferred):
        simulation_id — required
        platform — optional (reddit | twitter); omit for both
        agent_id — optional; filter to one agent (alias: user_id)
        limit — optional, default 100

    Backward compatibility: POST with the same keys in a JSON body is still accepted
    when query parameters are absent.

    Response:
        {
            "success": true,
            "data": {
                "count": 10,
                "history": [
                    {
                        "agent_id": 0,
                        "response": "I think...",
                        "prompt": "What do you think about this?",
                        "timestamp": "2025-12-08T10:00:00",
                        "platform": "reddit"
                    },
                    ...
                ]
            }
        }
    """
    try:
        simulation_id = _merged_query_or_json("simulation_id")
        platform = _merged_query_or_json("platform")
        if platform == "":
            platform = None
        agent_raw = _merged_query_or_json("agent_id")
        if agent_raw is None or agent_raw == "":
            agent_raw = _merged_query_or_json("user_id")
        agent_id = None
        if agent_raw is not None and agent_raw != "":
            try:
                agent_id = int(agent_raw)
            except (TypeError, ValueError):
                return jsonify({
                    "success": False,
                    "error": "agent_id and user_id must be integers when provided",
                }), 400
        limit_raw = _merged_query_or_json("limit", 100)
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            limit = 100

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        if platform is not None:
            if not isinstance(platform, str):
                return jsonify({
                    "success": False,
                    "error": "platform parameter can only be 'twitter' or 'reddit'",
                }), 400
            platform = platform.lower()
            if platform not in ("twitter", "reddit"):
                return jsonify({
                    "success": False,
                    "error": "platform parameter can only be 'twitter' or 'reddit'",
                }), 400

        history = SimulationRunner.get_interview_history(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": {
                "count": len(history),
                "history": history
            }
        })

    except Exception as e:
        logger.error(f"Failed to get interview history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/env-status', methods=['GET', 'POST'])
def get_env_status():
    """
    Get simulation environment status

    Checks whether the simulation environment is alive (can receive interview commands)

    Request (GET query parameters, preferred):
        simulation_id — required

    Backward compatibility: POST with JSON {"simulation_id": "..."} when the query
    string omits simulation_id.

    Response:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "env_alive": true,
                "twitter_available": true,
                "reddit_available": true,
                "message": "Environment is running and can receive interview commands"
            }
        }
    """
    try:
        simulation_id = _merged_query_or_json("simulation_id")

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        env_alive = SimulationRunner.check_env_alive(simulation_id)
        
        # Get more detailed status information
        env_status = SimulationRunner.get_env_status_detail(simulation_id)

        if env_alive:
            message = "Environment is running and can receive interview commands"
        else:
            message = "Environment is not running or has been closed"

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "env_alive": env_alive,
                "twitter_available": env_status.get("twitter_available", False),
                "reddit_available": env_status.get("reddit_available", False),
                "message": message
            }
        })

    except Exception as e:
        logger.error(f"Failed to get environment status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/start-env', methods=['POST'])
def start_simulation_env():
    """
    Start the OASIS environment in command-waiting mode without re-running
    simulation rounds.  Uses existing profiles and databases so the interview
    API becomes available for report generation.

    Request JSON:
        {"simulation_id": "sim_xxxx"}

    Response:
        {"success": true, "data": {"simulation_id": "...", "message": "..."}}
    """
    try:
        data = request.get_json(silent=True) or {}
        simulation_id = data.get("simulation_id")

        if not simulation_id:
            return jsonify({"success": False, "error": "Please provide simulation_id"}), 400

        state = SimulationRunner.start_env_only(simulation_id)

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "pid": state.process_pid,
                "message": (
                    "Environment starting in wait-only mode. "
                    "Use /env-status to check when it is alive."
                ),
            },
        })

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to start environment: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/close-env', methods=['POST'])
def close_simulation_env():
    """
    Close the simulation environment

    Sends a close environment command to the simulation for a graceful exit from command-waiting mode.

    Note: This differs from the /stop endpoint. /stop forcefully terminates the process,
    while this endpoint allows the simulation to gracefully close the environment and exit.

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",  // Required, simulation ID
            "timeout": 30                  // Optional, timeout in seconds, default 30
        }

    Response:
        {
            "success": true,
            "data": {
                "message": "Environment close command sent",
                "result": {...},
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        timeout = data.get('timeout', 30)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400
        
        result = SimulationRunner.close_simulation_env(
            simulation_id=simulation_id,
            timeout=timeout
        )

        manager = SimulationManager()
        env_success = result.get("success", False)
        intended_status = (
            SimulationStatus.COMPLETED if env_success else SimulationStatus.FAILED
        )
        if not manager.update_simulation_status(simulation_id, intended_status):
            logger.error(
                "SimulationManager.update_simulation_status found no simulation state: "
                "simulation_id=%s intended_status=%s",
                simulation_id,
                intended_status.value,
            )

        return jsonify({
            "success": env_success,
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Failed to close environment: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Scenario Forking Endpoints ==============
