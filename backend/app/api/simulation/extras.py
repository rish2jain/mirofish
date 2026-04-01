"""Simulation API — fork and cost estimate."""
import json
import os
import shutil
from flask import request, jsonify

from .. import simulation_bp
from ...config import Config
from ...services.simulation_manager import SimulationManager
from ...models.project import ProjectManager

from .common import logger

@simulation_bp.route('/fork', methods=['POST'])
def fork_simulation():
    """
    Fork an existing simulation with modified parameters (A/B scenario testing).

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",
            "changes": {
                "requirement": "Modified requirement text",
                "max_rounds": 20,
                "variable_overrides": {"key": "value"}
            }
        }

    Returns:
        New simulation state with forked_from metadata.
    """
    try:
        data = request.get_json() or {}

        source_id = data.get('simulation_id')
        if not source_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        changes = data.get('changes', {})

        manager = SimulationManager()
        source_state = manager.get_simulation(source_id)
        if not source_state:
            return jsonify({
                "success": False,
                "error": f"Source simulation not found: {source_id}"
            }), 404

        # Create new simulation from the same project/graph
        new_state = manager.create_simulation(
            project_id=source_state.project_id,
            graph_id=source_state.graph_id,
            enable_twitter=source_state.enable_twitter,
            enable_reddit=source_state.enable_reddit,
        )

        # Store fork metadata in the simulation directory
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, new_state.simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        fork_meta = {
            "forked_from": source_id,
            "changes": changes,
        }
        if changes.get('requirement'):
            project = ProjectManager.get_project(source_state.project_id)
            if project:
                fork_meta['original_requirement'] = project.simulation_requirement
        meta_path = os.path.join(sim_dir, "fork_metadata.json")
        try:
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(fork_meta, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error(
                "Failed to write fork_metadata.json (sim_dir=%s, path=%s): %s",
                sim_dir,
                meta_path,
                exc,
                exc_info=True,
            )
            try:
                if os.path.isdir(sim_dir):
                    shutil.rmtree(sim_dir)
            except OSError as cleanup_exc:
                logger.error(
                    "Fork cleanup: shutil.rmtree failed after fork_metadata write error "
                    "(simulation_id=%s, sim_dir=%s): %s",
                    new_state.simulation_id,
                    sim_dir,
                    cleanup_exc,
                    exc_info=True,
                )
            try:
                manager.remove_simulation(new_state.simulation_id)
            except Exception as cleanup_exc:
                logger.error(
                    "Fork cleanup: remove_simulation failed after fork_metadata write error "
                    "(simulation_id=%s): %s",
                    new_state.simulation_id,
                    cleanup_exc,
                    exc_info=True,
                )
            return jsonify({
                "success": False,
                "error": "Failed to save fork metadata (filesystem error)",
            }), 500
        except TypeError as exc:
            # json.dump raises TypeError for non-JSON-serializable values
            logger.error(
                "Failed to encode fork_metadata.json (sim_dir=%s): %s",
                sim_dir,
                exc,
                exc_info=True,
            )
            return jsonify({
                "success": False,
                "error": "Failed to save fork metadata (invalid data)",
            }), 500

        response_data = new_state.to_dict()
        response_data['forked_from'] = source_id
        response_data['changes'] = changes

        return jsonify({
            "success": True,
            "data": response_data
        })

    except Exception:
        logger.exception("Failed to fork simulation")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@simulation_bp.route('/<simulation_id>/cost-estimate', methods=['GET'])
def get_cost_estimate(simulation_id: str):
    """
    Get estimated token cost for a simulation.

    Returns cost breakdown based on agent count, rounds, and model pricing.
    """
    try:
        from ...utils.cost_estimator import estimate_simulation_cost

        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if not state:
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404

        # Get config for round count
        config = manager.get_simulation_config(simulation_id)
        max_rounds = Config.OASIS_DEFAULT_MAX_ROUNDS
        if config:
            max_rounds = config.get('max_rounds', max_rounds)

        model = Config.LLM_MODEL_NAME or "unknown"
        is_cli = (Config.LLM_PROVIDER or "").lower() in ("claude-cli", "codex-cli", "gemini-cli")

        num_agents = (
            state.profiles_count
            if state.profiles_count is not None
            else state.entities_count
            if state.entities_count is not None
            else 10
        )
        estimate = estimate_simulation_cost(
            num_agents=num_agents,
            num_rounds=max_rounds,
            model=model,
            is_cli=is_cli,
        )

        return jsonify({
            "success": True,
            "data": estimate.to_dict()
        })

    except Exception:
        logger.exception("Failed to estimate cost")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500
