import os
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.client_dirs import client_reviews_dir, client_run_dir, client_state_path
from claude_auto_review.runtime.cleanup import cancel_runtime, cancel_session, cleanup_expired_pending_reviews, cleanup_stale_clients
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
        rules_path = project_root / ".claude" / "claude-auto-review" / "review-rules.md"
        self.assertTrue(rules_path.exists())
        content = rules_path.read_text(encoding="utf-8")
        self.assertIn("Review semantic correctness", content)

    def test_cancel_runtime_removes_state_and_directories(self):
        project_root = self.temp_project()
        ensure_runtime(project_root)
        cancel_runtime(project_root)
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "state.jsonl").exists())

    def test_cancel_runtime_removes_client_data(self):
        from tests.support import client_dir

        project_root = self.temp_project()
        ensure_client_runtime(project_root, "test-client")
        target = client_dir(project_root, "test-client")
        self.assertTrue(target.exists())
        cancel_runtime(project_root, client_id="test-client")
        self.assertFalse(target.exists())

    def test_cancel_runtime_removes_empty_runtime_directory(self):
        project_root = self.temp_project()
        runtime_dir = project_root / ".claude" / "claude-auto-review"
        for child in ("run", "reviews", "clients"):
            (runtime_dir / child).mkdir(parents=True, exist_ok=True)

        removed = cancel_runtime(project_root)

        self.assertIn(runtime_dir, removed)
        self.assertFalse(runtime_dir.exists())

    def test_cancel_session_removes_client_state(self):
        from tests.support import client_dir as _client_dir

        project_root = self.temp_project()
        ensure_client_runtime(project_root, "session-a")
        ensure_client_runtime(project_root, "session-b")

        removed = cancel_session(project_root, client_id="session-a")

        self.assertFalse(_client_dir(project_root, "session-a").exists())
        self.assertTrue(_client_dir(project_root, "session-b").exists())
        self.assertGreater(len(removed), 0)

    def test_cancel_session_noop_when_no_data(self):
        project_root = self.temp_project()
        removed = cancel_session(project_root, client_id="nonexistent")
        self.assertEqual(removed, [])

    def test_cancel_session_does_not_overmatch_underscore_suffix(self):
        from tests.support import client_dir as _client_dir

        project_root = self.temp_project()
        ensure_client_runtime(project_root, "team_alpha")
        ensure_client_runtime(project_root, "other_alpha")

        removed = cancel_session(project_root, client_id="team_alpha")

        self.assertFalse(_client_dir(project_root, "team_alpha").exists())
        self.assertTrue(_client_dir(project_root, "other_alpha").exists())
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

    def test_iter_runtime_cleanup_targets_returns_expected_paths(self):
        from claude_auto_review.runtime.cleanup import _iter_runtime_cleanup_targets

        runtime = Path("/fake/runtime")
        targets = list(_iter_runtime_cleanup_targets(runtime))

        self.assertEqual(
            targets,
            [
                runtime / "run",
                runtime / "reviews",
                runtime / "clients",
            ],
        )

    def test_is_client_state_stale_uses_parent_mtime_when_state_missing(self):
        from claude_auto_review.runtime.cleanup import _is_client_state_stale

        project_root = self.temp_project()
        client_id = "stale-by-dir"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        if state_path.exists():
            state_path.unlink()

        stale_ts = (project_root.stat().st_mtime - 3 * 24 * 60 * 60)
        os.utime(state_path.parent, (stale_ts, stale_ts))

        self.assertTrue(_is_client_state_stale(state_path, timeout_hours=48))

    def test_cleanup_stale_clients_skips_unreadable_state(self):
        project_root = self.temp_project()
        client_id = "stale-unreadable"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        state_path.write_text("{}", encoding="utf-8")

        with patch("claude_auto_review.state.store_read.read_jsonl_records", side_effect=OSError("boom")):
            removed = cleanup_stale_clients(project_root)

        self.assertEqual(removed, [])
        self.assertTrue(state_path.parent.exists())

    def test_helpers_log_event_oserror_suppression(self):
        from claude_auto_review.runtime.events import log_event
        with patch("claude_auto_review.runtime.events.get_log_path", side_effect=OSError("no write")):
            self.assertFalse(log_event(Path("/fake"), "test_event"))

    def test_helpers_log_failure_propagates_log_failure(self):
        from claude_auto_review.runtime.events import log_failure
        with patch("claude_auto_review.runtime.events.get_log_path", side_effect=OSError("no write")):
            self.assertFalse(log_failure(Path("/fake"), "test_event", ValueError("boom")))

    def test_run_fail_open_logs_handler_failure_before_fallback(self):
        from claude_auto_review.runtime.process import run_fail_open

        def callback():
            raise ValueError("boom")

        def on_error(error):
            raise RuntimeError("handler boom")

        with patch("claude_auto_review.runtime.events.log_failure") as mock_log:
            result = run_fail_open(
                callback,
                project_root=Path("/fake"),
                event_type="test_event",
                on_error=on_error,
                fallback=7,
            )

        self.assertEqual(result, 7)
        self.assertEqual(mock_log.call_count, 2)
        self.assertEqual(mock_log.call_args_list[0].args[1], "test_event_handler_failed")
        self.assertEqual(mock_log.call_args_list[1].args[1], "test_event")

    def test_run_fail_open_treats_truthy_handler_as_handled(self):
        from claude_auto_review.runtime.process import run_fail_open

        def callback():
            raise ValueError("boom")

        def on_error(error):
            return True

        with patch("claude_auto_review.runtime.events.log_failure") as mock_log:
            result = run_fail_open(
                callback,
                project_root=Path("/fake"),
                event_type="test_event",
                on_error=on_error,
                fallback=7,
            )

        self.assertEqual(result, 7)
        mock_log.assert_not_called()

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
            patch("claude_auto_review.runtime.pending_cleanup.log_failure") as mock_log,
        ):
            removed = cleanup_expired_pending_reviews(project_root, client_id=client_id)

        self.assertEqual(removed, 0)
        mock_log.assert_called_once()
        self.assertEqual(mock_log.call_args.args[1], "runtime_cleanup_failed")
        self.assertEqual(mock_log.call_args.kwargs["operation"], "rewrite_state")
        self.assertEqual(mock_log.call_args.kwargs["target"], str(state_path))

    def test_cleanup_expired_pending_reviews_keeps_reviews_completed_later(self):
        from datetime import datetime, timedelta

        project_root = self.temp_project()
        client_id = "cleanup-completed-review"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        expired_time = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
        completed_time = datetime.now().astimezone().isoformat()
        state_path.write_text(
            "\n".join(
                [
                    '{"type":"review","reviewId":"rid","reviewPath":"review.md","timestamp":"'
                    + expired_time
                    + '","status":"pending","files":[{"file":"a.ts","hash":"1"}],"clientId":"'
                    + client_id
                    + '"}',
                    '{"type":"review","reviewId":"rid","reviewPath":"review.md","timestamp":"'
                    + completed_time
                    + '","status":"completed","files":[{"file":"a.ts","hash":"1"}],"clientId":"'
                    + client_id
                    + '"}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        removed = cleanup_expired_pending_reviews(project_root, client_id=client_id)

        self.assertEqual(removed, 0)
        self.assertEqual(len(load_state(project_root, client_id)), 2)


