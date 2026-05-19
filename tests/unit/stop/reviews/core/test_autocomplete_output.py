import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.core.context import RuntimeContext
from claude_auto_review.stop.reviews.core.prompt_runner import attempt_stop_autocomplete


def _ctx(project_root=Path("/fake"), client_id="c"):
    return RuntimeContext(project_root=project_root, client_id=client_id)


class TestAutoCompleteOutput(unittest.TestCase):

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_successful_completion_writes_output(self, mock_is_file, mock_write_text, mock_which, mock_run, mock_log):
        mock_run.return_value = MagicMock(returncode=0, stdout="## Verdict\nClean", stderr="")
        result = attempt_stop_autocomplete(
            _ctx(), review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
        )
        self.assertTrue(result)
        self.assertEqual(result.status, "output_written")

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_contradictory_clean_verdict_with_findings_does_not_complete(
        self, mock_is_file, mock_write_text, mock_which, mock_run, mock_log
    ):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "## Findings\n"
                "### [Low] Unused import\n"
                "**Verdict:** Confirmed\n\n"
                "## Verdict\n"
                "Clean - no issues found. Claude may stop.\n"
            ),
            stderr="",
        )
        result = attempt_stop_autocomplete(
            _ctx(), review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
        )
        self.assertTrue(result.output_written)
        self.assertIn(
            "Findings present. Claude must address all findings before stopping.",
            mock_write_text.call_args.args[0],
        )

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_completion_with_remaining_is_left_to_finalization(self, mock_is_file, mock_write_text, mock_which, mock_run, mock_log):
        mock_run.return_value = MagicMock(returncode=0, stdout="## Verdict\nClean", stderr="")
        result = attempt_stop_autocomplete(
            _ctx(), review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
        )
        self.assertTrue(result.output_written)

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_non_empty_stdout_overwrites_review_file_even_without_verdict(
        self, mock_is_file, mock_write_text, mock_which, mock_run, mock_log
    ):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="I need to inspect more files before I can finish this review.\n",
            stderr="",
        )

        result = attempt_stop_autocomplete(
            _ctx(),
            review_id="r",
            review_path=Path("/fake/review.md"),
            prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
        )

        self.assertTrue(result.output_written)
        mock_write_text.assert_called_once_with(
            "I need to inspect more files before I can finish this review.\n",
            encoding="utf-8",
            newline="\n",
        )

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_structured_review_without_verdict_is_persisted_as_is(
        self, mock_is_file, mock_write_text, mock_which, mock_run, mock_log
    ):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "# Review rev-1\n\n"
                "## Files Reviewed\n"
                "- README.md (hash: abc123)\n\n"
                "## Findings\n"
                "1. **Low** - Flowchart misses a stop branch.\n"
            ),
            stderr="",
        )

        result = attempt_stop_autocomplete(
            _ctx(),
            review_id="r",
            review_path=Path("/fake/review.md"),
            prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
        )

        self.assertTrue(result.output_written)
        mock_write_text.assert_called_once_with(
            "# Review rev-1\n\n"
            "## Files Reviewed\n"
            "- README.md (hash: abc123)\n\n"
            "## Findings\n"
            "1. **Low** - Flowchart misses a stop branch.\n",
            encoding="utf-8",
            newline="\n",
        )


if __name__ == "__main__":
    unittest.main()
