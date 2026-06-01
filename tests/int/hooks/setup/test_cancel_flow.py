import json
import os
import subprocess
import sys
import unittest

from claude_auto_review.paths.path_utils import get_state_path
from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.store.write import append_state_event
from tests.int.hooks.support import HookTestCase


class TestCancelFlow(HookTestCase, unittest.TestCase):
    def test_cancel_script_clears_state_run_and_review_artifacts(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.run_python("claude_auto_review/review/prompt.py", project_root)

        cancel = self.run_python("claude_auto_review/install/cli/cancel.py", project_root)
        self.assertEqual(cancel.returncode, 0)
        self.assertFalse(
            (
                project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "state.jsonl"
            ).exists()
        )
        self.assertFalse(
            (project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "run").exists()
        )
        self.assertFalse(
            (project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews").exists()
        )
        log_content = get_state_path(project_root).read_text(encoding="utf-8")
        self.assertIn('"type":"cancel_completed"', log_content)

    def test_project_local_cancel_shim_runs(self):
        project_root = self.temp_project()
        self.run_python("claude_auto_review/install/cli/setup.py", project_root)
        append_state_event(
            EditRecord(
                timestamp="2026-05-05T08:00:00+07:00",
                file="src/app.ts",
                hash="deadbeef",
                reviewed=False,
            ),
            project_root,
            client_id="test-session",
        )
        shim = project_root / ".claude" / "claude-auto-review" / "scripts" / "cancel_claude_auto_review.py"
        result = subprocess.run(
            [sys.executable, str(shim)],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_root), "CLAUDE_SESSION_ID": "test-session"},
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(
            (
                project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "state.jsonl"
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
