import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.reviews.runners.dispatcher import attempt_stop_autocomplete
from tests.support_paths import FAKE_ROOT


def _ctx(project_root=FAKE_ROOT, client_id="c"):
    return RuntimeContext(project_root=project_root, client_id=client_id)


class TestAutoCompleteOutput(unittest.TestCase):
    @patch("claude_auto_review.stop.reviews.types.result.log_event")
    @patch("claude_auto_review.stop.reviews.runners.cli.run_captured")
    @patch("claude_auto_review.stop.reviews.runners.claude.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_successful_completion_writes_output(self, mock_is_file, mock_write_text, mock_which, mock_run, mock_log):
        mock_run.return_value = MagicMock(returncode=0, stdout="## Verdict\nClean", stderr="")
        result = attempt_stop_autocomplete(
            _ctx(),
            review_id="r",
            review_path=Path("/fake/review.md"),
            prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
        )
        self.assertTrue(result)
        self.assertEqual(result.status, "output_written")

    @patch("claude_auto_review.stop.reviews.types.result.log_event")
    @patch("claude_auto_review.stop.reviews.runners.cli.run_captured")
    @patch("claude_auto_review.stop.reviews.runners.claude.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_contradictory_clean_verdict_with_blocking_findings_does_not_complete(
        self, mock_is_file, mock_write_text, mock_which, mock_run, mock_log
    ):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "## Findings\n"
                "### [Medium] Security issue\n"
                "**Verdict:** Confirmed\n\n"
                "## Verdict\n"
                "Clean - no issues found. Claude may stop.\n"
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
        self.assertIn(
            "Findings present. Claude must address all findings before stopping.",
            mock_write_text.call_args.args[0],
        )

    @patch("claude_auto_review.stop.reviews.types.result.log_event")
    @patch("claude_auto_review.stop.reviews.runners.cli.run_captured")
    @patch("claude_auto_review.stop.reviews.runners.claude.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_clean_verdict_with_low_findings_kept_as_clean(
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
            _ctx(),
            review_id="r",
            review_path=Path("/fake/review.md"),
            prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
        )
        self.assertTrue(result.output_written)
        self.assertNotIn(
            "Findings present",
            mock_write_text.call_args.args[0],
        )
        self.assertIn(
            "Clean - no issues found. Claude may stop.",
            mock_write_text.call_args.args[0],
        )

    @patch("claude_auto_review.stop.reviews.types.result.log_event")
    @patch("claude_auto_review.stop.reviews.runners.cli.run_captured")
    @patch("claude_auto_review.stop.reviews.runners.claude.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_completion_with_remaining_is_left_to_finalization(
        self, mock_is_file, mock_write_text, mock_which, mock_run, mock_log
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="## Verdict\nClean", stderr="")
        result = attempt_stop_autocomplete(
            _ctx(),
            review_id="r",
            review_path=Path("/fake/review.md"),
            prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
        )
        self.assertTrue(result.output_written)


if __name__ == "__main__":
    unittest.main()
