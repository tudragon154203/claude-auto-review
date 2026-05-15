import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.runtime.setup import ensure_client_runtime  # noqa: E402
from claude_auto_review.state.models import ReviewFileRecord, ReviewMetadata  # noqa: E402
from claude_auto_review.state.store_read import load_state  # noqa: E402
from claude_auto_review.state.store_write import append_state  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402
from tests.support import client_dir  # noqa: E402
from claude_auto_review.path_utils import get_log_path  # noqa: E402


def find_client_dir(project_root, session_id):
    """Find the timestamped client directory for a session_id."""
    clients_dir = project_root / ".claude" / "claude-auto-review" / "clients"
    matches = sorted(clients_dir.glob(f"client-*_{session_id}"))
    return matches[-1] if matches else None


class TestSessionEndHook(HookTestCase, unittest.TestCase):
    def test_session_end_fails_open_on_invalid_json_payload(self):
        project_root = self.temp_project()
        result = self.run_python("hooks/session_end.py", project_root, input_text="{not-json")
        self.assertEqual(result.returncode, 0)
        log_path = get_log_path(project_root)
        self.assertTrue(log_path.exists())
        self.assertIn("session_end_error", log_path.read_text(encoding="utf-8"))

    def test_removes_client_state_after_edits(self):
        """PostToolUse tracks files; SessionEnd removes client data."""
        project_root = self.temp_project()
        (project_root / "src").mkdir(parents=True, exist_ok=True)
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root,
                        json.dumps({"tool_input": {"file_path": "src/app.ts"}}))
        client_dir = find_client_dir(project_root, "test-session")
        self.assertIsNotNone(client_dir)
        self.assertTrue(client_dir.exists())
        result = self.run_python("hooks/session_end.py", project_root)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(client_dir.exists())

    def test_preserves_other_client_data(self):
        """SessionEnd only removes the current session's data."""
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
        result = self.run_python("hooks/session_end.py", project_root, client_id="session-a")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(dir_a.exists())
        self.assertTrue(dir_b.exists())

    def test_noop_when_no_state(self):
        """Returns 0 on clean project with no runtime data."""
        project_root = self.temp_project()
        result = self.run_python("hooks/session_end.py", project_root)
        self.assertEqual(result.returncode, 0)

    def test_fails_open_on_corrupt_state(self):
        """Malformed state doesn't cause non-zero exit."""
        project_root = self.temp_project()
        # Create a real client dir so we have something to clean up
        ensure_client_runtime(project_root, "corrupt-test")
        # Write corrupted state into it
        from claude_auto_review.client_dirs import client_state_path

        corrupt_state = client_state_path(project_root, "corrupt-test")
        corrupt_state.write_text("NOT JSON {{{", encoding="utf-8")
        result = self.run_python("hooks/session_end.py", project_root, client_id="corrupt-test")
        self.assertEqual(result.returncode, 0)

    def test_logs_cleanup_event(self):
        """Cleanup writes log event with removed paths."""
        project_root = self.temp_project()
        (project_root / "src").mkdir(parents=True, exist_ok=True)
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root,
                        json.dumps({"tool_input": {"file_path": "src/app.ts"}}))
        result = self.run_python("hooks/session_end.py", project_root)
        self.assertEqual(result.returncode, 0)
        log_path = get_log_path(project_root)
        self.assertTrue(log_path.exists())
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn("session_end_cleanup", log_content)

    def test_idempotent(self):
        """Running twice succeeds both times."""
        project_root = self.temp_project()
        (project_root / "src").mkdir(parents=True, exist_ok=True)
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root,
                        json.dumps({"tool_input": {"file_path": "src/app.ts"}}))
        result1 = self.run_python("hooks/session_end.py", project_root)
        self.assertEqual(result1.returncode, 0)
        result2 = self.run_python("hooks/session_end.py", project_root)
        self.assertEqual(result2.returncode, 0)

    def test_removes_review_artifacts(self):
        """SessionEnd removes review files created during session."""
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
        result = self.run_python("hooks/session_end.py", project_root)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(client_dir.exists())

    def test_session_end_cleans_expired_pending_reviews_before_removal(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "test-session")
        old_time = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
        append_state(
            ReviewMetadata(
                timestamp=old_time,
                reviewId="rev-expired",
                reviewPath=".claude/claude-auto-review/clients/client-test-session/reviews/review-expired.md",
                status="pending",
                files=[ReviewFileRecord(file="src/app.ts", hash="deadbeef")],
                clientId="test-session",
            ),
            project_root,
            client_id="test-session",
        )
        self.assertIn("rev-expired", [e.reviewId for e in load_state(project_root, "test-session") if e.type == "review"])
        result = self.run_python("hooks/session_end.py", project_root, client_id="test-session")
        self.assertEqual(result.returncode, 0)
        log_path = get_log_path(project_root)
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn("session_end_cleanup", log_content)
        self.assertIn("\"expired_removed\":1", log_content)

    def test_session_end_cleanup_uses_payload_session_id(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "payload-session")
        old_time = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
        append_state(
            ReviewMetadata(
                timestamp=old_time,
                reviewId="rev-expired-payload",
                reviewPath=".claude/claude-auto-review/clients/client-payload-session/reviews/review-expired.md",
                status="pending",
                files=[ReviewFileRecord(file="src/app.ts", hash="deadbeef")],
                clientId="payload-session",
            ),
            project_root,
            client_id="payload-session",
        )
        payload = json.dumps({"session_id": "payload-session"})
        result = self.run_python("hooks/session_end.py", project_root, input_text=payload, client_id="env-session")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(client_dir(project_root, "payload-session").exists())

    def test_session_end_non_dict_payload_falls_back_to_env_session(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "env-session")
        ensure_client_runtime(project_root, "other-session")

        # JSON number payload parses, but has no session_id
        result = self.run_python("hooks/session_end.py", project_root, input_text="1", client_id="env-session")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(client_dir(project_root, "env-session").exists())
        self.assertTrue(client_dir(project_root, "other-session").exists())


if __name__ == "__main__":
    unittest.main()
