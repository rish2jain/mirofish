"""
MiroFish Backend - Flask Application Factory
"""

import os
import warnings
from typing import TYPE_CHECKING, Optional

# Suppress multiprocessing resource_tracker warnings (from third-party libs like transformers)
# Must be set before all other imports
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request, send_from_directory
from flask_cors import CORS

from .config import Config
from .services.graph_storage import JSONStorage, KuzuDBStorage
from .utils.logger import setup_logger, get_logger

if TYPE_CHECKING:
    from .core.llm_orchestrator import OrchestrationResult


def create_app(config_class=Config, orchestration: Optional["OrchestrationResult"] = None):
    """Flask application factory function.

    If ``orchestration`` is provided (e.g. from ``run.py`` after ``detect_backend()``),
    it is stored as ``app.extensions[\"llm_backend\"]`` and ``detect_backend()`` is not
    called again. Otherwise ``detect_backend()`` runs once inside the factory.
    """
    frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../frontend/dist'))
    app = Flask(__name__, static_folder=frontend_dist if os.path.isdir(frontend_dist) else None)
    app.config.from_object(config_class)
    
    # Set JSON encoding: ensure non-ASCII characters are displayed directly (instead of \uXXXX format)
    # Flask >= 2.3 uses app.json.ensure_ascii, older versions use JSON_AS_ASCII config
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # Set up logging
    logger = setup_logger('mirofish')
    
    # Only print startup info in the reloader subprocess (avoid printing twice in debug mode)
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend starting...")
        logger.info("=" * 50)

    if orchestration is None:
        from .core.llm_orchestrator import detect_backend

        orchestration = detect_backend()
    app.extensions["llm_backend"] = orchestration

    if should_log_startup:
        logger.info("LLM backend: %s (binary: %s)", orchestration.backend.value, orchestration.binary_path or "N/A")

    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": app.config.get('CORS_ORIGINS', [])}})

    storage_backend = app.config.get("GRAPH_BACKEND", "kuzu")
    if storage_backend == "json":
        app.extensions["graph_storage"] = JSONStorage(data_dir=app.config["DATA_DIR"])
    else:
        app.extensions["graph_storage"] = KuzuDBStorage(db_path=app.config["KUZU_DB_PATH"])
    
    # Register simulation process cleanup (ensure all simulation processes are terminated on server shutdown)
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Simulation process cleanup registered")
        logger.info("Graph storage backend: %s", type(app.extensions["graph_storage"]).__name__)
    
    # Request logging middleware
    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"Request: {request.method} {request.path}")
        if app.config.get('DEBUG') and request.content_type and 'json' in request.content_type:
            logger.debug(f"Request body: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"Response: {response.status_code}")
        return response
    
    # Register blueprints
    from .api import graph_bp, simulation_bp, report_bp
    from .api.templates import templates_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(templates_bp, url_prefix='/api/templates')
    
    # Health check
    @app.route('/health')
    def health():
        orch = app.extensions.get("llm_backend")
        result = {'status': 'ok', 'service': 'MiroFish Backend'}
        if orch:
            result['llm_backend'] = orch.backend.value
            result['llm_model'] = orch.model
            expose_path = app.debug or app.config.get("EXPOSE_BINARY_PATH", False)
            if expose_path:
                result['llm_binary'] = orch.binary_path
            else:
                result['llm_cli_on_path'] = orch.binary_path is not None
        return result

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        if path.startswith('api/') or path == 'health':
            return {'error': 'Not found'}, 404

        static_folder = app.static_folder
        if not static_folder or not os.path.isdir(static_folder):
            return {'error': 'Frontend not built'}, 404

        if path:
            asset_path = os.path.join(static_folder, path)
            if os.path.isfile(asset_path):
                return send_from_directory(static_folder, path)

        return send_from_directory(static_folder, 'index.html')
    
    if should_log_startup:
        if app.static_folder:
            logger.info(f"Serving frontend from: {app.static_folder}")
        logger.info("MiroFish Backend started successfully")
    
    return app
