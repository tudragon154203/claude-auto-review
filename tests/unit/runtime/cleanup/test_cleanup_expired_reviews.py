import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.runtime.core.client_dirs import client_state_path
from claude_auto_review.runtime.pending_cleanup import cleanup_expired_pending_reviews
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.state.store.read import load_state

from tests.unit.state.support import StateTestCase


class TestCleanupExpiredPendingReviews(StateTestCase, unittest.TestCase):

    def test_cleanup_expired_pending_reviews_preserves_invalid_lines(self):
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
