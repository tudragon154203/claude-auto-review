import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.paths import client_reviews_dir, client_run_dir, client_state_path
from claude_auto_review.runtime.cleanup import cancel_runtime, cancel_session, cleanup_expired_pending_reviews
from claude_auto_review.runtime.setup import ensure_client_runtime, ensure_runtime
from claude_auto_review.state.store_read import load_state

from tests.unit.state.support import StateTestCase


class TestRuntime(StateTestCase, unittest.TestCase):

    def test_ensure_runtime_creates_directories(self):
        project_root = self.temp_project()
        result = ensure_runtime(project_root)
        self.assertTrue((result["base_dir"]).is_dir())
        self.assertTrue(result["state_path"].parent.exists())

    def test_ensure_runtime_creates_default_rules_file(self):
        project_root = self.temp_project()
        result = ensure_runtime(project_root)
        self.assertTrue(result["rules_path"].exists())
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "state.jsonl").exists())

    def test_ensure_runtime_without_default_rules_creates_fallback(self):
        project_root = self.temp_project()
        fake_plugin = self.temp_project()
        # No rules/review-rules.md in fake_plugin
        ensure_runtime(project_root, plugin_root=fake_plugin)
        rules_path = project_root / ".claude" / "claude-auto-review" / "rules.md"
        self.assertTrue(rules_path.exists())
        content = rules_path.read_text(encoding="utf-8")
        self.assertIn("Review semantic correctness", content)

    def test_cancel_runtime_removes_state_and_directories(self):
        project_root = self.temp_project()
        ensure_runtime(project_root)
        cancel_runtime(project_root)
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "state.jsonl").exists())

    def test_cancel_runtime_removes_client_data(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "test-client")
        cancel_runtime(project_root, client_id="test-client")
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-client").exists())

    def test_cancel_runtime_removes_empty_runtime_directory(self):
        project_root = self.temp_project()
        runtime_dir = project_root / ".claude" / "claude-auto-review"
        for child in ("run", "reviews", "clients"):
            (runtime_dir / child).mkdir(parents=True, exist_ok=True)

        removed = cancel_runtime(project_root)

        self.assertIn(runtime_dir, removed)
        self.assertFalse(runtime_dir.exists())

    def test_cancel_session_removes_client_state(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "session-a")
        ensure_client_runtime(project_root, "session-b")

        removed = cancel_session(project_root, client_id="session-a")

        self.assertFalse(
            (project_root / ".claude" / "claude-auto-review" / "clients" / "client-session-a").exists()
        )
        self.assertTrue(
            (project_root / ".claude" / "claude-auto-review" / "clients" / "client-session-b").exists()
        )
        self.assertGreater(len(removed), 0)

    def test_cancel_session_noop_when_no_data(self):
        project_root = self.temp_project()
        removed = cancel_session(project_root, client_id="nonexistent")
        self.assertEqual(removed, [])

    def test_cancel_session_does_not_overmatch_underscore_suffix(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "team_alpha")
        ensure_client_runtime(project_root, "other_alpha")

        removed = cancel_session(project_root, client_id="team_alpha")

        self.assertFalse(
            (project_root / ".claude" / "claude-auto-review" / "clients" / "client-team_alpha").exists()
        )
        self.assertTrue(
            (project_root / ".claude" / "claude-auto-review" / "clients" / "client-other_alpha").exists()
        )
        self.assertGreater(len(removed), 0)

    def test_remove_tree_oserror_suppressed(self):
        from claude_auto_review.runtime.cleanup import _remove_tree
        project_root = self.temp_project()
        target = project_root / "fake-dir"
        target.mkdir()
        with (
            patch("claude_auto_review.runtime.cleanup.shutil.rmtree", side_effect=OSError("no perms")),
            patch("claude_auto_review.runtime.cleanup.log_failure") as mock_log,
        ):
            result = _remove_tree(target, project_root=project_root)
            self.assertFalse(result)
            mock_log.assert_called_once()
            self.assertEqual(mock_log.call_args.args[1], "runtime_cleanup_failed")
            self.assertEqual(mock_log.call_args.kwargs["operation"], "remove_tree")
            self.assertEqual(mock_log.call_args.kwargs["target"], str(target))

    def test_cancel_runtime_logs_failed_runtime_dir_removal(self):
        project_root = self.temp_project()
        runtime_dir = project_root / ".claude" / "claude-auto-review"
        for child in ("run", "reviews", "clients"):
            (runtime_dir / child).mkdir(parents=True, exist_ok=True)

        with (
            patch("pathlib.Path.rmdir", side_effect=OSError("busy")),
            patch("claude_auto_review.runtime.cleanup.log_failure") as mock_log,
        ):
            removed = cancel_runtime(project_root)

        self.assertIn(runtime_dir / "run", removed)
        self.assertIn(runtime_dir / "reviews", removed)
        self.assertIn(runtime_dir / "clients", removed)
        self.assertNotIn(runtime_dir, removed)
        self.assertTrue(runtime_dir.exists())
        mock_log.assert_called_once()
        self.assertEqual(mock_log.call_args.args[1], "runtime_cleanup_failed")
        self.assertEqual(mock_log.call_args.kwargs["operation"], "rmdir")
        self.assertEqual(mock_log.call_args.kwargs["target"], str(runtime_dir))

    def test_remove_tree_unlink_file(self):
        from claude_auto_review.runtime.cleanup import _remove_tree
        project_root = self.temp_project()
        f = project_root / "temp.txt"
        f.write_text("hi", encoding="utf-8")
        result = _remove_tree(f)
        self.assertTrue(result)
        self.assertFalse(f.exists())

    def test_remove_tree_nonexistent(self):
        from claude_auto_review.runtime.cleanup import _remove_tree
        result = _remove_tree(Path("/nonexistent/nope"))
        self.assertFalse(result)

    def test_helpers_log_event_oserror_suppression(self):
        from claude_auto_review.runtime.helpers import log_event
        with patch("claude_auto_review.runtime.helpers.get_log_path", side_effect=OSError("no write")):
            try:
                log_event(Path("/fake"), "test_event")
            except Exception:
                self.fail("log_event should suppress OSError")

    def test_cleanup_expired_pending_reviews_preserves_invalid_lines(self):
        from datetime import datetime, timedelta

        project_root = self.temp_project()
        client_id = "cleanup-invalid"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        expired_time = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
        current_time = datetime.now().astimezone().isoformat()
        state_path.write_text(
            "\n".join(
                [
                    '{"type":"review","reviewId":"expired","reviewPath":"review.md","timestamp":"'
                    + expired_time
                    + '","status":"pending","files":[{"file":"a.ts","hash":"1"}]}',
                    "not-json",
                    '{"type":"edit","file":"a.ts","hash":"1","timestamp":"'
                    + current_time
                    + '","reviewed":false}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        removed = cleanup_expired_pending_reviews(project_root, client_id=client_id)

        self.assertEqual(removed, 1)
        content = state_path.read_text(encoding="utf-8").splitlines()
        self.assertIn("not-json", content)
        self.assertEqual(len(load_state(project_root, client_id)), 1)

    def test_cleanup_expired_pending_reviews_logs_write_failure_and_fails_open(self):
        from datetime import datetime, timedelta
        from pathlib import Path

        project_root = self.temp_project()
        client_id = "cleanup-write-failure"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        expired_time = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
        state_path.write_text(
            '{"type":"review","reviewId":"expired","reviewPath":"review.md","timestamp":"'
            + expired_time
            + '","status":"pending","files":[{"file":"a.ts","hash":"1"}]}\n',
            encoding="utf-8",
        )

        original_open = Path.open

        def fail_on_state_write(self, *args, **kwargs):
            if self == state_path and args and args[0] == "w":
                raise OSError("disk full")
            return original_open(self, *args, **kwargs)

        with (
            patch("pathlib.Path.open", new=fail_on_state_write),
            patch("claude_auto_review.runtime.cleanup.log_failure") as mock_log,
        ):
            removed = cleanup_expired_pending_reviews(project_root, client_id=client_id)

        self.assertEqual(removed, 0)
        mock_log.assert_called_once()
        self.assertEqual(mock_log.call_args.args[1], "runtime_cleanup_failed")
        self.assertEqual(mock_log.call_args.kwargs["operation"], "rewrite_state")
        self.assertEqual(mock_log.call_args.kwargs["target"], str(state_path))


