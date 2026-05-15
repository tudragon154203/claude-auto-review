import subprocess
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from claude_auto_review.stop.orchestration.core.context import RuntimeContext
from claude_auto_review.stop.reviews.core.prompt_runner import _run_claude_cli, attempt_stop_autocomplete


def _ctx(project_root=Path("/fake"), client_id="c"):
    return RuntimeContext(project_root=project_root, client_id=client_id)


class TestAutoComplete(unittest.TestCase):
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured")
    def test_run_claude_cli_uses_append_system_prompt_file(self, mock_run):
        prompt_file = Path("/fake/prompt.md")
        _run_claude_cli("/usr/bin/claude", prompt_file, "finish review", Path("/cwd"), 42)

        mock_run.assert_called_once_with(
            [
                "/usr/bin/claude",
                "--print",
                "--bare",
                "--allowedTools",
                "Read",
                "Grep",
                "Glob",
                "Bash",
                "--model",
                "fast",
                "--effort",
                "low",
                "--append-system-prompt-file",
                str(prompt_file),
                "finish review",
            ],
            cwd=Path("/cwd"),
            timeout=42.0,
        )

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value=None)
    def test_claude_cli_not_found(self, mock_which, mock_log):
        result = attempt_stop_autocomplete(
            _ctx(), review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(Path("/fake"), "stop_hook_claude_cli_not_found")

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    def test_prompt_file_not_found(self, mock_which, mock_log):
        result = attempt_stop_autocomplete(
            _ctx(), review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/nonexistent.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(Path("/fake"), "stop_hook_prompt_not_found", path=str(Path("/nonexistent.md")))

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=600))
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_subprocess_timeout(self, mock_is_file, mock_which, mock_run, mock_log):
        result = attempt_stop_autocomplete(
            _ctx(), review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(Path("/fake"), "stop_hook_claude_cli_timeout", reviewId="r")

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_passes_configured_timeout_to_subprocess(self, mock_is_file, mock_which, mock_run, mock_log):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        attempt_stop_autocomplete(
            _ctx(), review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            covered_entries=[], user_prompt="finish", reviewer_timeout_seconds=42,
        )
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 42.0)

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_general_exception(self, mock_is_file, mock_which, mock_run, mock_log):
        mock_run.side_effect = OSError("boom")
        result = attempt_stop_autocomplete(
            _ctx(), review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(Path("/fake"), "stop_hook_claude_cli_error", error="boom")

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.apply_completed_review", return_value=[])
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_successful_completion(self, mock_is_file, mock_write_text, mock_which, mock_run, mock_log, mock_apply):
        mock_run.return_value = MagicMock(returncode=0, stdout="## Verdict\nClean", stderr="")
        result = attempt_stop_autocomplete(
            _ctx(), review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertTrue(result)

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.apply_completed_review")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_contradictory_clean_verdict_with_findings_does_not_complete(
        self, mock_is_file, mock_write_text, mock_which, mock_run, mock_log, mock_apply
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
            covered_entries=[], user_prompt="finish",
        )
        self.assertFalse(result)
        mock_apply.assert_not_called()

    @patch("claude_auto_review.stop.reviews.core.prompt_runner.apply_completed_review", return_value=[{"file": "still.ts"}])
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.log_event")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.core.prompt_runner.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_completion_with_remaining_returns_false(self, mock_is_file, mock_write_text, mock_which, mock_run, mock_log, mock_apply):
        mock_run.return_value = MagicMock(returncode=0, stdout="## Verdict\nClean", stderr="")
        result = attempt_stop_autocomplete(
            _ctx(), review_id="r",
            review_path=Path("/fake/review.md"), prompt_file=Path("/fake/prompt.md"),
            covered_entries=[], user_prompt="finish",
        )
        self.assertFalse(result)

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
            covered_entries=[],
            user_prompt="finish",
        )

        self.assertFalse(result)
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
            covered_entries=[],
            user_prompt="finish",
        )

        self.assertFalse(result)
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
