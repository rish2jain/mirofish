"""Ensure backend root is on sys.path before any test module imports ``app``.

Pytest loads this file first; ``[tool.pytest.ini_options] pythonpath`` in
``pyproject.toml`` also adds ``.`` when running from ``backend/``. This keeps
``import app`` reliable if the test runner uses an unexpected cwd.
"""

from __future__ import annotations

import sys
from pathlib import Path

_backend_root = Path(__file__).resolve().parents[1]
_root = str(_backend_root)
if _root not in sys.path:
    sys.path.insert(0, _root)
