import os
import subprocess
import unittest
from unittest.mock import patch, MagicMock, call
from pathlib import Path

from claude_auto_review.stop.flow_logic import (
    StopFlowResolution,
    resolve_pending_review,
    finalize_review_stop,
    block_response,
    build_unreviewed_files_string,
    build_review_completion_prompt,
    _review_prompt_command,
    _review_prompt_path,
    _reload_client_state,
    _block_review_prompt_failure,
    _run_review_prompt,
)


class TestStopFlowResolution(unittest.TestCase):
    def test_is_terminal_when_exit_code_set(self):
        r = StopFlowResolution(state=[], unreviewed=[], exit_code=2)
        self.assertTrue(r.is_terminal)

    def test_is_not_terminal_when_no_exit_code(self):
        r = StopFlowResolution(state=[], unreviewed=[], review={"reviewId": "r1"})
        self.assertFalse(r.is_terminal)


class TestHelpers(unittest.TestCase):
    def test_build_unreviewed_files_string(self):
        entries = [{"file": "a.ts", "hash": "1"}, {"file": "b.ts", "hash": "2"}]
        self.assertEqual(build_unreviewed_files_string(entries), "a.ts, b.ts")

    def test_build_review_completion_prompt(self):
        review_path = Path("/fake/review.md")
        prompt = build_review_completion_prompt(review_path)
        self.assertIn(str(review_path), prompt)
        self.assertIn("non-Pending Verdict", prompt)

    def test_review_prompt_command(self):
        import sys
        result = _review_prompt_command(Path("/fake/script.py"))
        self.assertEqual(result, [sys.executable, str(Path("/fake/script.py"))])

    def test_review_prompt_path(self):
        result = _review_prompt_path(Path("/fake"), "c1", "rev123")
        self.assertEqual(result.name, "review-rev123-prompt.md")

    def test_block_response_outputs_json(self):
        with patch("builtins.print") as mock_print:
            block_response("msg", "feedback")
        self.assertEqual(mock_print.call_count, 2)

    def test_block_review_prompt_failure(self):
        with patch("claude_auto_review.stop.flow_logic.block_response") as mock_block:
            _block_review_prompt_failure("a.ts", MagicMock(stdout="out", stderr="err"))
        mock_block.assert_called_once()


class TestResolvePendingReview(unittest.TestCase):
    @patch("claude_auto_review.stop.flow_logic.log_event")
    @patch("claude_auto_review.stop.flow_logic.block_response")
    @patch("claude_auto_review.stop.flow_logic._run_review_prompt")
    @patch("claude_auto_review.stop.flow_logic.find_pending_review_for_files", return_value=None)
    def test_timeout_returns_exit_code_2(self, mock_find, mock_run, mock_block, mock_log):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="review_prompt.py", timeout=60)
        result = resolve_pending_review(
            project_root=Path("/fake"), client_id="c", payload={},
            state=[], unreviewed=[{"file": "a.ts", "hash": "1"}],
            timeout_hours=1, review_prompt_script=Path("/fake/script"),
        )
        self.assertEqual(result.exit_code, 2)

    @patch("claude_auto_review.stop.flow_logic.log_event")
    @patch("claude_auto_review.stop.flow_logic.block_response")
    @patch("claude_auto_review.stop.flow_logic._run_review_prompt")
    @patch("claude_auto_review.stop.flow_logic.find_pending_review_for_files", return_value=None)
    def test_general_error_returns_exit_code_2(self, mock_find, mock_run, mock_block, mock_log):
        mock_run.side_effect = Exception("boom")
        result = resolve_pending_review(
            project_root=Path("/fake"), client_id="c", payload={},
            state=[], unreviewed=[{"file": "a.ts", "hash": "1"}],
            timeout_hours=1, review_prompt_script=Path("/fake/script"),
        )
        self.assertEqual(result.exit_code, 2)

    @patch("claude_auto_review.stop.flow_logic.log_event")
    @patch("claude_auto_review.stop.flow_logic._reload_client_state")
    @patch("claude_auto_review.stop.flow_logic._run_review_prompt")
    @patch("claude_auto_review.stop.flow_logic.find_pending_review_for_files", return_value=None)
    def test_no_unreviewed_after_review_returns_exit_code_0(self, mock_find, mock_run, mock_reload, mock_log):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        mock_reload.return_value = ([], [])
        result = resolve_pending_review(
            project_root=Path("/fake"), client_id="c", payload={},
            state=[], unreviewed=[{"file": "a.ts", "hash": "1"}],
            timeout_hours=1, review_prompt_script=Path("/fake/script"),
        )
        self.assertEqual(result.exit_code, 0)

    @patch("claude_auto_review.stop.flow_logic.log_event")
    @patch("claude_auto_review.stop.flow_logic._block_review_prompt_failure")
    @patch("claude_auto_review.stop.flow_logic._reload_client_state")
    @patch("claude_auto_review.stop.flow_logic._run_review_prompt")
    @patch("claude_auto_review.stop.flow_logic.find_pending_review_for_files")
    def test_no_pending_review_found_returns_exit_code_2(self, mock_find_outer, mock_run, mock_reload, mock_block, mock_log):
        # First call (before _run): returns None so _run_review_prompt runs
        # Second call (after _reload): returns None so block fires
        mock_find_outer.side_effect = [None, None]
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=1)
        mock_reload.return_value = (
            [{"type": "edit", "file": "a.ts", "hash": "1"}],
            [{"file": "a.ts", "hash": "1"}],
        )
        result = resolve_pending_review(
            project_root=Path("/fake"), client_id="c", payload={},
            state=[], unreviewed=[{"file": "a.ts", "hash": "1"}],
            timeout_hours=1, review_prompt_script=Path("/fake/script"),
        )
        self.assertEqual(result.exit_code, 2)
        mock_block.assert_called_once()

    @patch("claude_auto_review.stop.flow_logic.find_pending_review_for_files")
    def test_existing_pending_review_returns_review(self, mock_find):
        review = {"reviewId": "r1", "reviewPath": "/fake/r.md"}
        mock_find.return_value = review
        result = resolve_pending_review(
            project_root=Path("/fake"), client_id="c", payload={},
            state=[], unreviewed=[{"file": "a.ts", "hash": "1"}],
            timeout_hours=1, review_prompt_script=Path("/fake/script"),
        )
        self.assertEqual(result.review, review)
        self.assertIsNone(result.exit_code)

    @patch("claude_auto_review.stop.flow_logic.find_pending_review_for_files")
    @patch("claude_auto_review.stop.flow_logic._reload_client_state")
    @patch("claude_auto_review.stop.flow_logic._run_review_prompt")
    def test_new_pending_review_returns_review(self, mock_run, mock_reload, mock_find):
        review = {"reviewId": "r1", "reviewPath": "/fake/r.md"}
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        mock_reload.return_value = ([{"type": "edit"}], [{"file": "a.ts", "hash": "1"}])
        mock_find.return_value = review
        result = resolve_pending_review(
            project_root=Path("/fake"), client_id="c", payload={},
            state=[], unreviewed=[{"file": "a.ts", "hash": "1"}],
            timeout_hours=1, review_prompt_script=Path("/fake/script"),
        )
        self.assertEqual(result.review, review)

    @patch("claude_auto_review.stop.flow_logic._run_review_prompt")
    @patch("claude_auto_review.stop.flow_logic.find_pending_review_for_files", return_value=None)
    def test_payload_session_id_passed_to_env(self, mock_find, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        resolve_pending_review(
            project_root=Path("/fake"), client_id="c",
            payload={"session_id": "sid-123"},
            state=[], unreviewed=[{"file": "a.ts", "hash": "1"}],
            timeout_hours=1, review_prompt_script=Path("/fake/script"),
        )
        call_args = mock_run.call_args
        env = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("env")
        if env is None:
            env = call_args[0][2]
        self.assertEqual(env.get("CLAUDE_SESSION_ID"), "sid-123")


class TestFinalizeReviewStop(unittest.TestCase):
    @patch("claude_auto_review.stop.flow_logic.classify_last_assistant_message")
    @patch("claude_auto_review.stop.flow_logic.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.flow_logic.is_review_clean", return_value=True)
    @patch("claude_auto_review.stop.flow_logic.is_review_complete", return_value=True)
    @patch("claude_auto_review.stop.flow_logic.apply_completed_review", return_value=[])
    def test_completed_no_remaining_returns_0(self, mock_apply, mock_complete, mock_clean, mock_covered, mock_classify):
        resolution = StopFlowResolution(
            state=[], unreviewed=[],
            review={"reviewId": "r1", "reviewPath": "/fake/r.md"},
        )
        result = finalize_review_stop(Path("/fake"), "c", resolution, {}, {})
        self.assertEqual(result, 0)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.flow_logic.classify_last_assistant_message")
    @patch("claude_auto_review.stop.flow_logic.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.flow_logic.is_review_clean", return_value=True)
    @patch("claude_auto_review.stop.flow_logic.is_review_complete", return_value=True)
    @patch("claude_auto_review.stop.flow_logic.apply_completed_review", return_value=[{"file": "still.ts"}])
    def test_completed_with_remaining_returns_2(self, mock_apply, mock_complete, mock_clean, mock_covered, mock_classify):
        resolution = StopFlowResolution(
            state=[], unreviewed=[{"file": "still.ts", "hash": "1"}],
            review={"reviewId": "r1", "reviewPath": "/fake/r.md"},
        )
        result = finalize_review_stop(Path("/fake"), "c", resolution, {"last_assistant_message": "done"}, {})
        self.assertEqual(result, 2)
        mock_classify.assert_called_once()

    @patch("claude_auto_review.stop.flow_logic.classify_last_assistant_message")
    @patch("claude_auto_review.stop.flow_logic.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.flow_logic.attempt_stop_autocomplete", return_value=True)
    @patch("claude_auto_review.stop.flow_logic.is_review_complete", return_value=False)
    def test_autocomplete_succeeds_returns_0(self, mock_complete, mock_auto, mock_covered, mock_classify):
        resolution = StopFlowResolution(
            state=[], unreviewed=[{"file": "a.ts", "hash": "1"}],
            review={"reviewId": "r1", "reviewPath": "/fake/r.md"},
        )
        result = finalize_review_stop(Path("/fake"), "c", resolution, {"last_assistant_message": "done"}, {})
        self.assertEqual(result, 0)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.flow_logic.classify_last_assistant_message")
    @patch("claude_auto_review.stop.flow_logic.append_state")
    @patch("claude_auto_review.stop.flow_logic.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.flow_logic.attempt_stop_autocomplete", return_value=False)
    @patch("claude_auto_review.stop.flow_logic.is_review_complete", return_value=False)
    def test_autocomplete_fails_blocks_stop(self, mock_complete, mock_auto, mock_covered, mock_append, mock_classify):
        resolution = StopFlowResolution(
            state=[], unreviewed=[{"file": "a.ts", "hash": "1"}],
            review={"reviewId": "r1", "reviewPath": "/fake/r.md"},
        )
        result = finalize_review_stop(Path("/fake"), "c", resolution, {"last_assistant_message": "done"}, {})
        self.assertEqual(result, 2)
        mock_append.assert_called_once()
        mock_classify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
