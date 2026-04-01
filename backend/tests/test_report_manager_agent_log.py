"""ReportManager.get_agent_log skipped_lines and totals."""

import json
import os
import tempfile
from unittest.mock import patch

from app.services.report_manager import ReportManager


def test_get_agent_log_skipped_lines_and_total_lines():
    rid = "rep_test_agent_log"
    with tempfile.TemporaryDirectory() as tmp:
        reports_root = os.path.join(tmp, "reports")
        folder = os.path.join(reports_root, rid)
        os.makedirs(folder, exist_ok=True)
        log_path = os.path.join(folder, "agent_log.jsonl")
        lines = [
            json.dumps({"ok": 1}),
            "not json",
            json.dumps({"ok": 2}),
            "",
        ]
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        with patch.object(ReportManager, "REPORTS_DIR", reports_root):
            out = ReportManager.get_agent_log(rid, from_line=0)

    assert out["total_lines"] == 4
    assert len(out["logs"]) == 2
    # "not json" and empty line after strip both raise JSONDecodeError.
    assert out["skipped_lines"] == 2
