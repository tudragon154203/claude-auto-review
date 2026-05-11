import subprocess
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from claude_auto_review.stop.autocomplete import attempt_stop_autocomplete


class TestAutoComplete(unittest.TestCase):
    @patch("claude_auto_review.stop.autocomplete.log_event")
    @patch("claude_auto_review.stop.autocomplete.shutil.which", return_value=None)
    def test_claude_cli_not_found(self, mock_which, mock_log):
        result = attempt_stop_autocomplete(
            project_root=Path("/fake"), client_id="c", review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(Path("/fake"), "stop_hook_claude_cli_not_found")

    @patch("claude_auto_review.stop.autocomplete.log_event")
    @patch("claude_auto_review.stop.autocomplete.shutil.which", return_value="/usr/bin/claude")
    def test_prompt_file_not_found(self, mock_which, mock_log):
        result = attempt_stop_autocomplete(
            project_root=Path("/fake"), client_id="c", review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/nonexistent.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(Path("/fake"), "stop_hook_prompt_not_found", path=str(Path("/nonexistent.md")))

    @patch("claude_auto_review.stop.autocomplete.log_event")
    @patch("claude_auto_review.stop.autocomplete.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=600))
    @patch("claude_auto_review.stop.autocomplete.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_subprocess_timeout(self, mock_is_file, mock_which, mock_run, mock_log):
        result = attempt_stop_autocomplete(
            project_root=Path("/fake"), client_id="c", review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(Path("/fake"), "stop_hook_claude_cli_timeout", reviewId="r")

    @patch("claude_auto_review.stop.autocomplete.log_event")
    @patch("claude_auto_review.stop.autocomplete.subprocess.run")
    @patch("claude_auto_review.stop.autocomplete.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_general_exception(self, mock_is_file, mock_which, mock_run, mock_log):
        mock_run.side_effect = Exception("boom")
        result = attempt_stop_autocomplete(
            project_root=Path("/fake"), client_id="c", review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(Path("/fake"), "stop_hook_claude_cli_error", error="boom")

    @patch("claude_auto_review.stop.autocomplete.apply_completed_review", return_value=[])
    @patch("claude_auto_review.stop.autocomplete.is_review_complete", return_value=True)
    @patch("claude_auto_review.stop.autocomplete.log_event")
    @patch("claude_auto_review.stop.autocomplete.subprocess.run")
    @patch("claude_auto_review.stop.autocomplete.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_successful_completion(self, mock_is_file, mock_which, mock_run, mock_log, mock_complete, mock_apply):
        mock_run.return_value = MagicMock(returncode=0, stdout="## Verdict\nClean", stderr="")
        result = attempt_stop_autocomplete(
            project_root=Path("/fake"), client_id="c", review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertTrue(result)

    @patch("claude_auto_review.stop.autocomplete.apply_completed_review", return_value=[{"file": "still.ts"}])
    @patch("claude_auto_review.stop.autocomplete.is_review_complete", return_value=True)
    @patch("claude_auto_review.stop.autocomplete.log_event")
    @patch("claude_auto_review.stop.autocomplete.subprocess.run")
    @patch("claude_auto_review.stop.autocomplete.shutil.which", return_value="/usr/bin/claude")
    def test_completion_with_remaining_returns_false(self, mock_which, mock_run, mock_log, mock_complete, mock_apply):
        mock_run.return_value = MagicMock(returncode=0, stdout="## Verdict\nClean", stderr="")
        result = attempt_stop_autocomplete(
            project_root=Path("/fake"), client_id="c", review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()