import os
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.runtime.cleanup.paths import _iter_runtime_cleanup_targets, _remove_tree
from claude_auto_review.runtime.cleanup.session import cancel_runtime, cancel_session
from claude_auto_review.runtime.client_dirs import client_state_path
from claude_auto_review.runtime.setup import ensure_client_runtime, ensure_runtime

from tests.unit.state.support import StateTestCase


class TestCleanupSession(StateTestCase, unittest.TestCase):

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

    def test_cancel_runtime_logs_failed_runtime_dir_removal(self):
        project_root = self.temp_project()
        runtime_dir = project_root / ".claude" / "claude-auto-review"
        for child in ("run", "reviews", "clients"):
            (runtime_dir / child).mkdir(parents=True, exist_ok=True)

        with (
            patch("pathlib.Path.rmdir", side_effect=OSError("busy")),
            patch("claude_auto_review.runtime.cleanup.paths.log_failure") as mock_log,
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
        project_root = self.temp_project()
        target = project_root / "fake-dir"
        target.mkdir()
        with (
            patch("claude_auto_review.runtime.cleanup.paths.shutil.rmtree", side_effect=OSError("no perms")),
            patch("claude_auto_review.runtime.cleanup.paths.log_failure") as mock_log,
        ):
            result = _remove_tree(target, project_root=project_root)
            self.assertFalse(result)
            mock_log.assert_called_once()
            self.assertEqual(mock_log.call_args.args[1], "runtime_cleanup_failed")
            self.assertEqual(mock_log.call_args.kwargs["operation"], "remove_tree")
            self.assertEqual(mock_log.call_args.kwargs["target"], str(target))

    def test_remove_tree_unlink_file(self):
        project_root = self.temp_project()
        f = project_root / "temp.txt"
        f.write_text("hi", encoding="utf-8")
        result = _remove_tree(f)
        self.assertTrue(result)
        self.assertFalse(f.exists())

    def test_remove_tree_nonexistent(self):
        result = _remove_tree(Path("/nonexistent/nope"))
        self.assertFalse(result)

    def test_iter_runtime_cleanup_targets_returns_expected_paths(self):
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
