"""Shared helpers for the simulation API."""

import os
import re

from ...config import Config
from ...utils.logger import get_logger

logger = get_logger("mirofish.api.simulation")

_SIMULATION_ID_SAFE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")


def _reject_unsafe_simulation_id(simulation_id) -> str | None:
    """Return an error message if simulation_id is unsafe for filesystem use, else None."""
    if not isinstance(simulation_id, str):
        return "simulation_id must be a string"
    if len(simulation_id) > 256:
        return "Invalid simulation_id"
    if ".." in simulation_id or "/" in simulation_id or "\\" in simulation_id:
        return "Invalid simulation_id"
    if not _SIMULATION_ID_SAFE_RE.match(simulation_id):
        return "Invalid simulation_id"
    return None


def _resolved_simulation_dir_or_error(simulation_id: str) -> tuple[str | None, str | None]:
    """
    Resolve the absolute simulation data directory for a validated id.

    Returns (sim_dir, None) on success, or (None, error_message) if the path
    would lie outside OASIS_SIMULATION_DATA_DIR.
    """
    root = os.path.abspath(os.path.realpath(Config.OASIS_SIMULATION_DATA_DIR))
    candidate = os.path.join(root, simulation_id)
    sim_dir = os.path.abspath(os.path.normpath(os.path.realpath(candidate)))
    try:
        if os.path.commonpath([root, sim_dir]) != root:
            return None, "Invalid simulation path"
    except ValueError:
        return None, "Invalid simulation path"
    if sim_dir == root:
        return None, "Invalid simulation path"
    return sim_dir, None


# Interview prompt optimization prefix
# Adding this prefix prevents Agent from calling tools and forces a direct text reply
INTERVIEW_PROMPT_PREFIX = "Based on your persona, all past memories and actions, reply directly with text without calling any tools: "


def optimize_interview_prompt(prompt: str) -> str:
    """
    Optimize interview prompt by adding a prefix to prevent Agent from calling tools

    Args:
        prompt: Original prompt

    Returns:
        Optimized prompt
    """
    if not prompt:
        return prompt
    # Avoid adding the prefix repeatedly
    if prompt.startswith(INTERVIEW_PROMPT_PREFIX):
        return prompt
    return f"{INTERVIEW_PROMPT_PREFIX}{prompt}"

