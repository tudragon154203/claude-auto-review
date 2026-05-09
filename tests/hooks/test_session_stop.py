import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from state import ensure_client_runtime  # noqa: E402
from tests.hooks.support import HookTestCase  # noqa: E402


def find_client_dir(project_root, session_id):
    """Find the client directory matching a session_id suffix.

    get_client_id() produces '{timestamp}_{session_id}', so the directory
    is 'client-{timestamp}_{session_id}'. We glob for the suffix.
    """
    clients_dir = project_root / ".claude" / "claude-auto-review" / "clients"
    matches = sorted(clients_dir.glob(f"client-*_{session_id}"))
    return matches[-1] if matches else None


class TestSessionStopHook(HookTestCase, unittest.TestCase):

    def test_removes_client_state_after_edits(self):
        """PostToolUse tracks files; SessionStop removes client data."""
        project_root = self.temp_project()
        (project_root / "src").mkdir(parents=True, exist_ok=True)
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root,
                        json.dumps({"tool_input": {"file_path": "src/app.ts"}}))
        client_dir = find_client_dir(project_root, "test-session")
        self.assertIsNotNone(client_dir)
        self.assertTrue(client_dir.exists())
        result = self.run_python("hooks/session_stop.py", project_root)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(client_dir.exists())

    def test_preserves_other_client_data(self):
        """SessionStop only removes the current session's data."""
        project_root = self.temp_project()
        (project_root / "src").mkdir(parents=True, exist_ok=True)
        (project_root / "src" / "a.ts").write_text("export const a = 1;\n", encoding="utf-8")
        (project_root / "src" / "b.ts").write_text("export const b = 2;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root,
                        json.dumps({"tool_input": {"file_path": "src/a.ts"}}),
                        client_id="session-a")
        self.run_python("hooks/post_tool_use.py", project_root,
                        json.dumps({"tool_input": {"file_path": "src/b.ts"}}),
                        client_id="session-b")
        dir_a = find_client_dir(project_root, "session-a")
        dir_b = find_client_dir(project_root, "session-b")
        self.assertIsNotNone(dir_a)
        self.assertIsNotNone(dir_b)
        self.assertTrue(dir_a.exists())
        self.assertTrue(dir_b.exists())
        result = self.run_python("hooks/session_stop.py", project_root, client_id="session-a")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(dir_a.exists())
        self.assertTrue(dir_b.exists())

    def test_noop_when_no_state(self):
        """Returns 0 on clean project with no runtime data."""
        project_root = self.temp_project()
        result = self.run_python("hooks/session_stop.py", project_root)
        self.assertEqual(result.returncode, 0)

    def test_fails_open_on_corrupt_state(self):
        """Malformed state doesn't cause non-zero exit."""
        project_root = self.temp_project()
        # Create a real client dir so we have something to clean up
        ensure_client_runtime(project_root, "corrupt-test")
        # Write corrupted state into it
        corrupt_state = project_root / ".claude" / "claude-auto-review" / "clients" / "client-corrupt-test" / "state.jsonl"
        corrupt_state.write_text("NOT JSON {{{", encoding="utf-8")
        result = self.run_python("hooks/session_stop.py", project_root, client_id="corrupt-test")
        self.assertEqual(result.returncode, 0)

    def test_logs_cleanup_event(self):
        """Cleanup writes log event with removed paths."""
        project_root = self.temp_project()
        (project_root / "src").mkdir(parents=True, exist_ok=True)
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root,
                        json.dumps({"tool_input": {"file_path": "src/app.ts"}}))
        result = self.run_python("hooks/session_stop.py", project_root)
        self.assertEqual(result.returncode, 0)
        log_path = project_root / ".claude" / "claude-auto-review" / "claude-auto-review.log"
        self.assertTrue(log_path.exists())
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn("session_stop_cleanup", log_content)

    def test_idempotent(self):
        """Running twice succeeds both times."""
        project_root = self.temp_project()
        (project_root / "src").mkdir(parents=True, exist_ok=True)
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root,
                        json.dumps({"tool_input": {"file_path": "src/app.ts"}}))
        result1 = self.run_python("hooks/session_stop.py", project_root)
        self.assertEqual(result1.returncode, 0)
        result2 = self.run_python("hooks/session_stop.py", project_root)
        self.assertEqual(result2.returncode, 0)

    def test_removes_review_artifacts(self):
        """SessionStop removes review files created during session."""
        project_root = self.temp_project()
        (project_root / "src").mkdir(parents=True, exist_ok=True)
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root,
                        json.dumps({"tool_input": {"file_path": "src/app.ts"}}))
        client_dir = find_client_dir(project_root, "test-session")
        self.assertIsNotNone(client_dir)
        reviews_dir = client_dir / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        (reviews_dir / "review-test.md").write_text("# Test review\nPending.", encoding="utf-8")
        self.assertTrue((reviews_dir / "review-test.md").exists())
        result = self.run_python("hooks/session_stop.py", project_root)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(client_dir.exists())


if __name__ == "__main__":
    unittest.main()