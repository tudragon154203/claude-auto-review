import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.pending import resolve_pending_review


class TestResolvePendingReview(unittest.TestCase):
    base_kwargs = {
        "project_root": Path("/fake"),
        "client_id": "c",
        "payload": {},
        "state": [],
        "unreviewed": [{"file": "a.ts", "hash": "1"}],
        "timeout_hours": 1,
        "review_prompt_script": Path("/fake/script"),
    }

    @patch("claude_auto_review.stop.orchestration.pending.find_pending_review_for_files")
    @patch("claude_auto_review.stop.orchestration.pending._run_review_prompt")
    @patch("claude_auto_review.stop.orchestration.pending.log_event")
    def test_timeout_returns_exit_code_2(self, mock_log, mock_run, mock_find):
        mock_find.return_value = None
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="review_prompt.py", timeout=60)
        result = resolve_pending_review(**self.base_kwargs)
        self.assertEqual(result.exit_code, 2)

    @patch("claude_auto_review.stop.orchestration.pending.find_pending_review_for_files")
    @patch("claude_auto_review.stop.orchestration.pending._run_review_prompt")
    @patch("claude_auto_review.stop.orchestration.pending.log_event")
    def test_general_error_returns_exit_code_2(self, mock_log, mock_run, mock_find):
        mock_find.return_value = None
        mock_run.side_effect = Exception("boom")
        result = resolve_pending_review(**self.base_kwargs)
        self.assertEqual(result.exit_code, 2)

    @patch("claude_auto_review.stop.orchestration.pending.find_pending_review_for_files")
    @patch("claude_auto_review.stop.orchestration.pending._reload_client_state")
    @patch("claude_auto_review.stop.orchestration.pending._run_review_prompt")
    @patch("claude_auto_review.stop.orchestration.pending.log_event")
    def test_no_unreviewed_after_review_returns_exit_code_0(self, mock_log, mock_run, mock_reload, mock_find):
        mock_find.return_value = None
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        mock_reload.return_value = ([], [])
        result = resolve_pending_review(**self.base_kwargs)
        self.assertEqual(result.exit_code, 0)

    @patch("claude_auto_review.stop.orchestration.pending.find_pending_review_for_files")
    def test_existing_pending_review_returns_review(self, mock_find):
        review = {"reviewId": "r1", "reviewPath": "/fake/r.md"}
        mock_find.return_value = review
        result = resolve_pending_review(**self.base_kwargs)
        self.assertEqual(result.review, review)
        self.assertIsNone(result.exit_code)

    @patch("claude_auto_review.stop.orchestration.pending.find_pending_review_for_files")
    @patch("claude_auto_review.stop.orchestration.pending._reload_client_state")
    @patch("claude_auto_review.stop.orchestration.pending._run_review_prompt")
    def test_new_pending_review_returns_review(self, mock_run, mock_reload, mock_find):
        review = {"reviewId": "r1", "reviewPath": "/fake/r.md"}
        mock_find.return_value = review
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        mock_reload.return_value = ([{"type": "edit"}], [{"file": "a.ts", "hash": "1"}])
        result = resolve_pending_review(**self.base_kwargs)
        self.assertEqual(result.review, review)

    @patch("claude_auto_review.stop.orchestration.pending._reload_client_state")
    @patch("claude_auto_review.stop.orchestration.pending._run_review_prompt")
    @patch("claude_auto_review.stop.orchestration.pending.find_pending_review_for_files")
    def test_payload_session_id_passed_to_env(self, mock_find, mock_run, mock_reload):
        mock_find.return_value = None
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        mock_reload.return_value = ([{"type": "edit", "file": "a.ts", "hash": "1"}], [{"file": "a.ts", "hash": "1"}])
        result = resolve_pending_review(
            **dict(self.base_kwargs, payload={"session_id": "sid-123"})
        )
        call_env = mock_run.call_args[1].get("env") or mock_run.call_args[0][2]
        self.assertEqual(call_env.get("CLAUDE_SESSION_ID"), "sid-123")

    @patch("claude_auto_review.stop.orchestration.pending._block_review_prompt_failure")
    @patch("claude_auto_review.stop.orchestration.pending.find_pending_review_for_files")
    @patch("claude_auto_review.stop.orchestration.pending._reload_client_state")
    @patch("claude_auto_review.stop.orchestration.pending._run_review_prompt")
    def test_missing_review_after_prompt_blocks_failure(self, mock_run, mock_reload, mock_find, mock_block):
        mock_find.side_effect = [None, None]
        mock_run.return_value = MagicMock(stdout="review output", stderr="", returncode=0)
        mock_reload.return_value = ([{"type": "edit"}], [{"file": "a.ts", "hash": "1"}])

        result = resolve_pending_review(**self.base_kwargs)

        self.assertEqual(result.exit_code, 2)
        mock_block.assert_called_once()
