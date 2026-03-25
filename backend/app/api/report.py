"""
Report API Routes
Provides simulation report generation, retrieval, chat, and other endpoints
"""

import os
import io
import traceback
import threading
from flask import request, jsonify, send_file, make_response

from . import report_bp
from ..config import Config
from ..core.workbench_session import WorkbenchSession
from ..services.report_agent import ReportAgent, ReportManager, ReportStatus
from ..services.simulation_manager import SimulationManager
from ..models.project import ProjectManager
from ..models.task import TaskManager
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.report')


# ============== Report Generation API ==============

def _task_to_dict(task) -> dict:
    """Normalize task objects and pre-serialized task dicts."""
    return task if isinstance(task, dict) else task.to_dict()


def _normalize_task_status_data(task_data: dict) -> dict:
    """Ensure task status payloads always expose a numeric progress field."""
    normalized = dict(task_data)
    if normalized.get("progress") is None:
        normalized["progress"] = 0
    return normalized


def _get_generate_task_by_report_id(report_id: str) -> dict:
    """Resolve an in-flight report generation task by report_id."""
    task_manager = TaskManager()
    for task in task_manager.list_tasks(task_type="report_generate"):
        task_data = _task_to_dict(task)
        metadata = task_data.get("metadata") or {}
        if metadata.get("report_id") == report_id:
            return _normalize_task_status_data(task_data)
    return None


def _build_status_data_from_report(report) -> dict:
    """Build a status payload from persisted report metadata."""
    is_completed = report.status == ReportStatus.COMPLETED
    return {
        "simulation_id": report.simulation_id,
        "report_id": report.report_id,
        "status": report.status.value,
        "progress": 100 if is_completed else 0,
        "message": "Report already generated" if is_completed else (report.error or "Report status available"),
        "already_completed": is_completed,
    }


@report_bp.route('/generate', methods=['POST'])
def generate_report():
    """Generate a simulation analysis report."""
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        session = WorkbenchSession.open(simulation_id=simulation_id, metadata={"entrypoint": "api.report.generate"})
        result = session.start_report_generation(
            simulation_id=simulation_id,
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
        logger.error(f"Failed to start report generation task: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/generate/status', methods=['GET', 'POST'])
def get_generate_status():
    """
    Query report generation task progress

    Request (JSON):
        {
            "task_id": "task_xxxx",         // Optional, task_id from generate
            "simulation_id": "sim_xxxx"     // Optional, simulation ID
        }

    Returns:
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|failed",
                "progress": 45,
                "message": "..."
            }
        }
    """
    try:
        report_id = None
        if request.method == 'GET':
            task_id = request.args.get('task_id')
            simulation_id = request.args.get('simulation_id')
            report_id = request.args.get('report_id')
        else:
            data = request.get_json() or {}
            task_id = data.get('task_id')
            simulation_id = data.get('simulation_id')
            report_id = data.get('report_id')
        
        if report_id:
            task_data = _get_generate_task_by_report_id(report_id)
            if task_data:
                return jsonify({
                    "success": True,
                    "data": task_data
                })

            report = ReportManager.get_report(report_id)
            if report:
                return jsonify({
                    "success": True,
                    "data": _build_status_data_from_report(report)
                })

            return jsonify({
                "success": False,
                "error": f"Report not found: {report_id}"
            }), 404

        # If simulation_id is provided, first check if a completed report already exists
        if simulation_id:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "progress": 100,
                        "message": "Report already generated",
                        "already_completed": True
                    }
                })
        
        task = _find_report_task(task_id=task_id, simulation_id=simulation_id, report_id=report_id)

        if not task:
            return jsonify({
                "success": False,
                "error": "Report generation task not found"
            }), 404
        
        return jsonify({
            "success": True,
            "data": _normalize_task_status_data(_task_to_dict(task))
        })
        
    except Exception as e:
        logger.error(f"Failed to query task status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Report Retrieval API ==============

@report_bp.route('/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """
    Get report details

    Returns:
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "simulation_id": "sim_xxxx",
                "status": "completed",
                "outline": {...},
                "markdown_content": "...",
                "created_at": "...",
                "completed_at": "..."
            }
        }
    """
    try:
        report = ReportManager.get_report(report_id)
        
        if not report:
            return jsonify({
                "success": False,
                "error": f"Report not found: {report_id}"
            }), 404
        
        return jsonify({
            "success": True,
            "data": report.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to get report: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/by-simulation/<simulation_id>', methods=['GET'])
def get_report_by_simulation(simulation_id: str):
    """
    Get report by simulation ID

    Returns:
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                ...
            }
        }
    """
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)
        
        if not report:
            return jsonify({
                "success": False,
                "error": f"No report available for this simulation: {simulation_id}",
                "has_report": False
            }), 404
        
        return jsonify({
            "success": True,
            "data": report.to_dict(),
            "has_report": True
        })
        
    except Exception as e:
        logger.error(f"Failed to get report: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/list', methods=['GET'])
def list_reports():
    """
    List all reports

    Query parameters:
        simulation_id: Filter by simulation ID (optional)
        limit: Return count limit (default 50)

    Returns:
        {
            "success": true,
            "data": [...],
            "count": 10
        }
    """
    try:
        simulation_id = request.args.get('simulation_id')
        limit = request.args.get('limit', 50, type=int)
        
        reports = ReportManager.list_reports(
            simulation_id=simulation_id,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in reports],
            "count": len(reports)
        })
        
    except Exception as e:
        logger.error(f"Failed to list reports: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/download', methods=['GET'])
def download_report(report_id: str):
    """
    Download report (Markdown format)

    Returns Markdown file
    """
    try:
        report = ReportManager.get_report(report_id)
        
        if not report:
            return jsonify({
                "success": False,
                "error": f"Report not found: {report_id}"
            }), 404
        
        md_path = ReportManager._get_report_markdown_path(report_id)
        
        if not os.path.exists(md_path):
            # If MD file doesn't exist, generate a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(report.markdown_content)
                temp_path = f.name
            
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{report_id}.md"
            )
        
        return send_file(
            md_path,
            as_attachment=True,
            download_name=f"{report_id}.md"
        )
        
    except Exception as e:
        logger.error(f"Failed to download report: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>', methods=['DELETE'])
def delete_report(report_id: str):
    """Delete report"""
    try:
        success = ReportManager.delete_report(report_id)
        
        if not success:
            return jsonify({
                "success": False,
                "error": f"Report not found: {report_id}"
            }), 404
        
        return jsonify({
            "success": True,
            "message": f"Report deleted: {report_id}"
        })
        
    except Exception as e:
        logger.error(f"Failed to delete report: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Report Agent Chat API ==============

@report_bp.route('/chat', methods=['POST'])
def chat_with_report_agent():
    """
    Chat with Report Agent

    Report Agent can autonomously call retrieval tools to answer questions during conversation.

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",                // Required, simulation ID
            "message": "Please explain the trend",      // Required, user message
            "chat_history": [                            // Optional, chat history
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }

    Returns:
        {
            "success": true,
            "data": {
                "response": "Agent response...",
                "tool_calls": [list of tool calls],
                "sources": [information sources]
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        message = data.get('message')
        chat_history = data.get('chat_history', [])
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400
        
        if not message:
            return jsonify({
                "success": False,
                "error": "Please provide message"
            }), 400
        
        # Get simulation and project info
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404
        
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"Project not found: {state.project_id}"
            }), 404
        
        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Missing graph ID"
            }), 400
        
        simulation_requirement = project.simulation_requirement or ""
        
        # Create Agent and conduct chat
        agent = ReportAgent(
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement
        )
        
        result = agent.chat(message=message, chat_history=chat_history)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Chat failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Report Progress and Section API ==============

@report_bp.route('/<report_id>/progress', methods=['GET'])
def get_report_progress(report_id: str):
    """
    Get report generation progress (real-time)

    Returns:
        {
            "success": true,
            "data": {
                "status": "generating",
                "progress": 45,
                "message": "Generating section: Key Findings",
                "current_section": "Key Findings",
                "completed_sections": ["Executive Summary", "Simulation Background"],
                "updated_at": "2025-12-09T..."
            }
        }
    """
    try:
        progress = ReportManager.get_progress(report_id)
        
        if not progress:
            return jsonify({
                "success": False,
                "error": f"Report not found or progress info unavailable: {report_id}"
            }), 404
        
        return jsonify({
            "success": True,
            "data": progress
        })
        
    except Exception as e:
        logger.error(f"Failed to get report progress: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/sections', methods=['GET'])
def get_report_sections(report_id: str):
    """
    Get list of generated sections (per-section output)

    Frontend can poll this endpoint to get generated section content without waiting for the entire report.

    Returns:
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "sections": [
                    {
                        "filename": "section_01.md",
                        "section_index": 1,
                        "content": "## Executive Summary\\n\\n..."
                    },
                    ...
                ],
                "total_sections": 3,
                "is_complete": false
            }
        }
    """
    try:
        sections = ReportManager.get_generated_sections(report_id)
        
        # Get report status
        report = ReportManager.get_report(report_id)
        is_complete = report is not None and report.status == ReportStatus.COMPLETED
        
        return jsonify({
            "success": True,
            "data": {
                "report_id": report_id,
                "sections": sections,
                "total_sections": len(sections),
                "is_complete": is_complete
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get section list: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/section/<int:section_index>', methods=['GET'])
def get_single_section(report_id: str, section_index: int):
    """
    Get single section content

    Returns:
        {
            "success": true,
            "data": {
                "filename": "section_01.md",
                "content": "## Executive Summary\\n\\n..."
            }
        }
    """
    try:
        section_path = ReportManager._get_section_path(report_id, section_index)
        
        if not os.path.exists(section_path):
            return jsonify({
                "success": False,
                "error": f"Section not found: section_{section_index:02d}.md"
            }), 404
        
        with open(section_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            "success": True,
            "data": {
                "filename": f"section_{section_index:02d}.md",
                "section_index": section_index,
                "content": content
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get section content: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Report Status Check API ==============

@report_bp.route('/check/<simulation_id>', methods=['GET'])
def check_report_status(simulation_id: str):
    """
    Check if a simulation has a report and its status

    Used by frontend to determine whether to unlock Interview feature
    
    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "has_report": true,
                "report_status": "completed",
                "report_id": "report_xxxx",
                "interview_unlocked": true
            }
        }
    """
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)
        
        has_report = report is not None
        report_status = report.status.value if report else None
        report_id = report.report_id if report else None
        
        # Only unlock interview after report is completed
        interview_unlocked = has_report and report.status == ReportStatus.COMPLETED
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "has_report": has_report,
                "report_status": report_status,
                "report_id": report_id,
                "interview_unlocked": interview_unlocked
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to check report status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Agent Log API ==============

@report_bp.route('/<report_id>/agent-log', methods=['GET'])
def get_agent_log(report_id: str):
    """
    Get detailed execution log of Report Agent

    Real-time access to each step during report generation, including:
    - Report start, planning start/complete
    - Each section's start, tool calls, LLM responses, completion
    - Report complete or failed

    Query parameters:
        from_line: Line to start reading from (optional, default 0, for incremental fetching)

    Returns:
        {
            "success": true,
            "data": {
                "logs": [
                    {
                        "timestamp": "2025-12-13T...",
                        "elapsed_seconds": 12.5,
                        "report_id": "report_xxxx",
                        "action": "tool_call",
                        "stage": "generating",
                        "section_title": "Executive Summary",
                        "section_index": 1,
                        "details": {
                            "tool_name": "insight_forge",
                            "parameters": {...},
                            ...
                        }
                    },
                    ...
                ],
                "total_lines": 25,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        from_line = request.args.get('from_line', 0, type=int)
        
        log_data = ReportManager.get_agent_log(report_id, from_line=from_line)
        
        return jsonify({
            "success": True,
            "data": log_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get Agent log: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/agent-log/stream', methods=['GET'])
def stream_agent_log(report_id: str):
    """
    Get complete Agent log (fetch all at once)

    Returns:
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 25
            }
        }
    """
    try:
        logs = ReportManager.get_agent_log_stream(report_id)
        
        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get Agent log: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Console Log API ==============

@report_bp.route('/<report_id>/console-log', methods=['GET'])
def get_console_log(report_id: str):
    """
    Get Report Agent console output log

    Real-time access to console output during report generation (INFO, WARNING, etc.).
    This differs from the agent-log endpoint which returns structured JSON logs;
    this is plain text console-style logging.

    Query parameters:
        from_line: Line to start reading from (optional, default 0, for incremental fetching)

    Returns:
        {
            "success": true,
            "data": {
                "logs": [
                    "[19:46:14] INFO: Search complete: found 15 relevant facts",
                    "[19:46:14] INFO: Graph search: graph_id=xxx, query=...",
                    ...
                ],
                "total_lines": 100,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        from_line = request.args.get('from_line', 0, type=int)
        
        log_data = ReportManager.get_console_log(report_id, from_line=from_line)
        
        return jsonify({
            "success": True,
            "data": log_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get console log: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/console-log/stream', methods=['GET'])
def stream_console_log(report_id: str):
    """
    Get complete console log (fetch all at once)

    Returns:
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 100
            }
        }
    """
    try:
        logs = ReportManager.get_console_log_stream(report_id)
        
        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get console log: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Report Comparison & Export API ==============

@report_bp.route('/compare', methods=['POST'])
def compare_reports():
    """
    Compare two reports side-by-side (A/B scenario diff).

    Request (JSON):
        {
            "report_id_a": "report_xxxx",
            "report_id_b": "report_yyyy"
        }

    Returns:
        Structured comparison with both reports' content and metadata.
    """
    try:
        data = request.get_json() or {}
        report_id_a = data.get('report_id_a')
        report_id_b = data.get('report_id_b')

        if not report_id_a or not report_id_b:
            return jsonify({
                "success": False,
                "error": "Please provide both report_id_a and report_id_b"
            }), 400

        report_a = ReportManager.get_report(report_id_a)
        report_b = ReportManager.get_report(report_id_b)

        if not report_a:
            return jsonify({"success": False, "error": f"Report not found: {report_id_a}"}), 404
        if not report_b:
            return jsonify({"success": False, "error": f"Report not found: {report_id_b}"}), 404

        # Build comparison structure
        comparison = {
            "report_a": {
                "report_id": report_a.report_id,
                "simulation_id": report_a.simulation_id,
                "status": report_a.status.value,
                "created_at": report_a.created_at if hasattr(report_a, 'created_at') else None,
                "markdown_content": report_a.markdown_content,
            },
            "report_b": {
                "report_id": report_b.report_id,
                "simulation_id": report_b.simulation_id,
                "status": report_b.status.value,
                "created_at": report_b.created_at if hasattr(report_b, 'created_at') else None,
                "markdown_content": report_b.markdown_content,
            },
        }

        # Extract section-level comparison if both have sections
        sections_a = ReportManager.get_generated_sections(report_id_a)
        sections_b = ReportManager.get_generated_sections(report_id_b)

        if sections_a and sections_b:
            comparison["sections_a"] = sections_a
            comparison["sections_b"] = sections_b
            comparison["section_count_a"] = len(sections_a)
            comparison["section_count_b"] = len(sections_b)

        return jsonify({
            "success": True,
            "data": comparison
        })

    except Exception as e:
        logger.error(f"Failed to compare reports: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/pdf', methods=['GET'])
def export_report_pdf(report_id: str):
    """
    Export report as a branded PDF.

    Uses markdown-to-HTML conversion with branded CSS, then converts to PDF.
    Falls back to plain-text PDF if weasyprint is not available.
    """
    try:
        report = ReportManager.get_report(report_id)
        if not report:
            return jsonify({"success": False, "error": f"Report not found: {report_id}"}), 404

        if report.status != ReportStatus.COMPLETED:
            return jsonify({"success": False, "error": "Report is not yet completed"}), 400

        markdown_content = report.markdown_content or ""

        # Convert markdown to HTML
        try:
            import markdown
            html_body = markdown.markdown(
                markdown_content,
                extensions=['tables', 'fenced_code', 'toc']
            )
        except ImportError:
            # Fallback: wrap raw markdown in <pre>
            html_body = f"<pre>{markdown_content}</pre>"

        # Branded HTML wrapper
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @page {{
        size: A4;
        margin: 2cm;
        @top-center {{
            content: "MiroFish Simulation Report";
            font-size: 9pt;
            color: #666;
        }}
        @bottom-center {{
            content: "Page " counter(page) " of " counter(pages);
            font-size: 9pt;
            color: #666;
        }}
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 11pt;
        line-height: 1.6;
        color: #1a1a1a;
        max-width: 100%;
    }}
    h1 {{ color: #0f172a; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; }}
    h2 {{ color: #1e293b; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }}
    h3 {{ color: #334155; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }}
    th {{ background-color: #f8fafc; font-weight: 600; }}
    code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
    pre {{ background: #f8fafc; padding: 16px; border-radius: 6px; overflow-x: auto; }}
    blockquote {{ border-left: 4px solid #3b82f6; margin: 1em 0; padding: 0.5em 1em; background: #f8fafc; }}
    .header {{
        text-align: center;
        margin-bottom: 2em;
        padding-bottom: 1em;
        border-bottom: 3px solid #3b82f6;
    }}
    .header h1 {{ border: none; color: #3b82f6; font-size: 24pt; }}
    .header .meta {{ color: #64748b; font-size: 10pt; }}
</style>
</head>
<body>
<div class="header">
    <h1>MiroFish Simulation Report</h1>
    <div class="meta">
        Report ID: {report_id} | Simulation: {report.simulation_id}
    </div>
</div>
{html_body}
</body>
</html>"""

        # Try weasyprint for high-quality PDF
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html).write_pdf()
            return send_file(
                io.BytesIO(pdf_bytes),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"{report_id}.pdf",
            )
        except ImportError:
            logger.warning("weasyprint not installed — returning HTML instead of PDF")
            response = make_response(html)
            response.headers['Content-Type'] = 'text/html; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="{report_id}.html"'
            return response

    except Exception as e:
        logger.error(f"Failed to export PDF: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Tool Call API (for debugging) ==============

@report_bp.route('/tools/search', methods=['POST'])
def search_graph_tool():
    """
    Graph search tool endpoint (for debugging)

    Request (JSON):
        {
            "graph_id": "mirofish_xxxx",
            "query": "search query",
            "limit": 10
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        query = data.get('query')
        limit = data.get('limit', 10)
        
        if not graph_id or not query:
            return jsonify({
                "success": False,
                "error": "Please provide graph_id and query"
            }), 400
        
        from ..services.graph_tools import GraphToolsService
        
        tools = GraphToolsService()
        result = tools.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Graph search failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/tools/statistics', methods=['POST'])
def get_graph_statistics_tool():
    """
    Graph statistics tool endpoint (for debugging)

    Request (JSON):
        {
            "graph_id": "mirofish_xxxx"
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
        
        from ..services.graph_tools import GraphToolsService
        
        tools = GraphToolsService()
        result = tools.get_graph_statistics(graph_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Failed to get graph statistics: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
