import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.state import append_state, ensure_client_runtime, load_state  # noqa: E402
from tests.hooks.support import HookTestCase  # noqa: E402


def find_client_dir(project_root, session_id):
    """Find the client directory for a session_id (by suffix or exact)."""
    clients_dir = project_root / ".claude" / "claude-auto-review" / "clients"
    # Old style: client-{timestamp}_{session_id}
    matches = sorted(clients_dir.glob(f"client-*_{session_id}"))
    if matches:
        return matches[-1]
    # New style: client-{session_id}
    exact = clients_dir / f"client-{session_id}"
    if exact.is_dir():
        return exact
    return None


class TestSessionEndHook(HookTestCase, unittest.TestCase):
    def test_session_end_fails_open_on_invalid_json_payload(self):
        project_root = self.temp_project()
        result = self.run_python("hooks/session_end.py", project_root, input_text="{not-json")
        self.assertEqual(result.returncode, 0)
        log_path = project_root / ".claude" / "claude-auto-review" / "claude-auto-review.log"
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
        corrupt_state = project_root / ".claude" / "claude-auto-review" / "clients" / "client-corrupt-test" / "state.jsonl"
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
        log_path = project_root / ".claude" / "claude-auto-review" / "claude-auto-review.log"
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
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        append_state(
            {
                "type": "review",
                "reviewId": "rev-expired",
                "reviewPath": str(
                    project_root
                    / ".claude"
                    / "claude-auto-review"
                    / "clients"
                    / "client-test-session"
                    / "reviews"
                    / "review-expired.md"
                ),
                "timestamp": old_time,
                "status": "pending",
                "files": [{"file": "src/app.ts", "hash": "deadbeef"}],
            },
            project_root,
            client_id="test-session",
        )
        self.assertIn("rev-expired", [e.get("reviewId") for e in load_state(project_root, "test-session") if e.get("type") == "review"])
        result = self.run_python("hooks/session_end.py", project_root, client_id="test-session")
        self.assertEqual(result.returncode, 0)
        log_path = project_root / ".claude" / "claude-auto-review" / "claude-auto-review.log"
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn("session_end_cleanup", log_content)
        self.assertIn("\"expired_removed\":1", log_content)

    def test_session_end_cleanup_uses_payload_session_id(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "payload-session")
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        append_state(
            {
                "type": "review",
                "reviewId": "rev-expired-payload",
                "reviewPath": str(
                    project_root
                    / ".claude"
                    / "claude-auto-review"
                    / "clients"
                    / "client-payload-session"
                    / "reviews"
                    / "review-expired.md"
                ),
                "timestamp": old_time,
                "status": "pending",
                "files": [{"file": "src/app.ts", "hash": "deadbeef"}],
            },
            project_root,
            client_id="payload-session",
        )
        payload = json.dumps({"session_id": "payload-session"})
        result = self.run_python("hooks/session_end.py", project_root, input_text=payload, client_id="env-session")
        self.assertEqual(result.returncode, 0)
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "clients" / "client-payload-session").exists())

    def test_session_end_non_dict_payload_falls_back_to_env_session(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "env-session")
        ensure_client_runtime(project_root, "other-session")

        # JSON number payload parses, but has no session_id
        result = self.run_python("hooks/session_end.py", project_root, input_text="1", client_id="env-session")
        self.assertEqual(result.returncode, 0)
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "clients" / "client-env-session").exists())
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "clients" / "client-other-session").exists())


if __name__ == "__main__":
    unittest.main()
