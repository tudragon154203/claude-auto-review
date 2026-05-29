import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.reviews.prompt_runner import attempt_stop_autocomplete


def _ctx(project_root=Path("/fake"), client_id="c"):
    return RuntimeContext(project_root=project_root, client_id=client_id)


class TestAutoCompleteCLI(unittest.TestCase):
    @patch("claude_auto_review.stop.reviews.prompt_runner_claude.log_event")
    @patch("claude_auto_review.stop.reviews.prompt_runner_claude.shutil.which", return_value=None)
    def test_claude_cli_not_found(self, mock_which, mock_log):
        result = attempt_stop_autocomplete(
            _ctx(),
            review_id="r",
            review_path=Path("/fake/review.md"),
            prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(Path("/fake"), "stop_hook_reviewer_not_found", client_id="c", backend="claude")

    @patch("claude_auto_review.stop.reviews.prompt_runner_claude.log_event")
    @patch("claude_auto_review.stop.reviews.prompt_runner_claude.shutil.which", return_value="/usr/bin/claude")
    def test_prompt_file_not_found(self, mock_which, mock_log):
        result = attempt_stop_autocomplete(
            _ctx(),
            review_id="r",
            review_path=Path("/fake/review.md"),
            prompt_file=Path("/nonexistent.md"),
            user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(
            Path("/fake"), "stop_hook_prompt_not_found", client_id="c", path=str(Path("/nonexistent.md"))
        )

    @patch("claude_auto_review.stop.reviews.prompt_runner_claude.log_event")
    @patch(
        "claude_auto_review.stop.reviews.prompt_runner.run_captured",
        side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=600),
    )
    @patch("claude_auto_review.stop.reviews.prompt_runner_claude.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_subprocess_timeout(self, mock_is_file, mock_which, mock_run, mock_log):
        result = attempt_stop_autocomplete(
            _ctx(),
            review_id="r",
            review_path=Path("/fake/review.md"),
            prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(
            Path("/fake"), "stop_hook_reviewer_timeout", client_id="c", reviewId="r", backend="claude"
        )

    @patch("claude_auto_review.stop.reviews.prompt_runner_claude.log_event")
    @patch("claude_auto_review.stop.reviews.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.prompt_runner_claude.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_passes_configured_timeout_to_subprocess(self, mock_is_file, mock_which, mock_run, mock_log):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        attempt_stop_autocomplete(
            _ctx(),
            review_id="r",
            review_path=Path("/fake/review.md"),
            prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
            reviewer_timeout_seconds=42,
        )
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 42.0)

    @patch("claude_auto_review.stop.reviews.prompt_runner_claude.log_event")
    @patch("claude_auto_review.stop.reviews.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.prompt_runner_claude.shutil.which", return_value="/usr/bin/claude")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_general_exception(self, mock_is_file, mock_which, mock_run, mock_log):
        mock_run.side_effect = OSError("boom")
        result = attempt_stop_autocomplete(
            _ctx(),
            review_id="r",
            review_path=Path("/fake/review.md"),
            prompt_file=Path("/fake/prompt.md"),
            user_prompt="finish",
        )
        self.assertFalse(result)
        mock_log.assert_called_with(
            Path("/fake"), "stop_hook_reviewer_error", client_id="c", error="boom", backend="claude", reviewId="r"
        )

    @patch("claude_auto_review.stop.reviews.prompt_runner.run_captured")
    def test_run_claude_cli_uses_append_system_prompt_file(self, mock_run):
        prompt_file = Path("/fake/prompt.md")
        from claude_auto_review.stop.reviews.prompt_runner_claude import _run_claude_cli

        _run_claude_cli("/usr/bin/claude", prompt_file, "finish review", Path("/cwd"), 42, "claude-sonnet-4-6")

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
                "claude-sonnet-4-6",
                "--effort",
                "low",
                "--append-system-prompt-file",
                str(prompt_file),
                "finish review",
            ],
            cwd=Path("/cwd"),
            timeout=42.0,
            input=None,
        )


if __name__ == "__main__":
    unittest.main()
