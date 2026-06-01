import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.runtime.cleanup.stale import cleanup_stale_clients  # noqa: E402
from claude_auto_review.runtime.setup import ensure_client_runtime  # noqa: E402
from claude_auto_review.state.edit_record import EditRecord  # noqa: E402
from claude_auto_review.state.store.write import append_state_event  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402
from tests.support_paths import client_dir  # noqa: E402


class TestStaleCleanup(HookTestCase, unittest.TestCase):
    def test_cleanup_stale_clients(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "stale-session")
        ensure_client_runtime(project_root, "fresh-session")

        # Mock stale session with old timestamp
        stale_time = (datetime.now().astimezone() - timedelta(hours=50)).isoformat()
        append_state_event(
            EditRecord(timestamp=stale_time, file="test.txt", hash="123"),
            project_root,
            client_id="stale-session",
        )

        # Mock fresh session with recent timestamp
        fresh_time = (datetime.now().astimezone() - timedelta(hours=10)).isoformat()
        append_state_event(
            EditRecord(timestamp=fresh_time, file="test.txt", hash="456"),
            project_root,
            client_id="fresh-session",
        )

        # Run cleanup with default 48h
        removed = cleanup_stale_clients(project_root)

        self.assertEqual(len(removed), 1)
        self.assertIn("stale-session", str(removed[0]))

        stale_dir = client_dir(project_root, "stale-session")
        fresh_dir = client_dir(project_root, "fresh-session")

        self.assertFalse(stale_dir.exists())
        self.assertTrue(fresh_dir.exists())

    def test_cleanup_stale_clients_no_state_uses_mtime(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "no-state-stale")

        stale_dir = client_dir(project_root, "no-state-stale")
        state_file = stale_dir / "state.jsonl"
        if state_file.exists():
            state_file.unlink()

        # Set mtime of directory to 3 days ago
        stale_ts = (datetime.now() - timedelta(days=3)).timestamp()
        os.utime(stale_dir, (stale_ts, stale_ts))

        removed = cleanup_stale_clients(project_root)
        self.assertEqual(len(removed), 1)
        self.assertFalse(stale_dir.exists())

    def test_session_end_triggers_stale_cleanup(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "my-session")
        ensure_client_runtime(project_root, "other-stale-session")

        stale_time = (datetime.now().astimezone() - timedelta(hours=50)).isoformat()
        append_state_event(
            EditRecord(timestamp=stale_time, file="test.txt", hash="123"),
            project_root,
            client_id="other-stale-session",
        )

        # Run session_end for my-session
        result = self.run_python("hooks/session_end.py", project_root, client_id="my-session")
        self.assertEqual(result.returncode, 0)

        # Both should be gone: my-session (because it ended) and other-stale-session (because it's stale)
        my_dir = project_root / ".claude" / "claude-auto-review" / "clients" / "client-my-session"
        stale_dir = project_root / ".claude" / "claude-auto-review" / "clients" / "client-other-stale-session"

        self.assertFalse(my_dir.exists())
        self.assertFalse(stale_dir.exists())

        # Stale cleanup is project-level; session-end cleanup falls back to the project state file after the client dir is removed.
        root_log = project_root / ".claude" / "claude-auto-review" / "state.jsonl"
        self.assertIn("stale_clients_cleaned", root_log.read_text(encoding="utf-8"))
        self.assertIn("session_end_cleanup", root_log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
