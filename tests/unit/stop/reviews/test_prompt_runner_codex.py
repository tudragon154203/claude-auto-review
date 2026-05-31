import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.reviews.prompt_runner import (
    attempt_stop_autocomplete,
)
from claude_auto_review.stop.reviews.review_args import (
    _build_claude_review_args,
    _build_codex_review_args,
    _build_opencode_review_args,
)


class TestPromptRunnerCodex(unittest.TestCase):
    def _ctx(self):
        return RuntimeContext(project_root=Path("/fake"), client_id="client-1")

    def test_build_codex_review_args(self):
        self.assertEqual(
            _build_codex_review_args("gpt-5"),
            ["exec", "--skip-git-repo-check", "--sandbox", "read-only", "--model", "gpt-5", "-"],
        )

    def test_build_claude_review_args(self):
        self.assertEqual(
            _build_claude_review_args("claude-sonnet-4-6")[:4],
            ["--print", "--bare", "--allowedTools", "Read"],
        )

    def test_attempt_stop_autocomplete_rejects_unknown_backend(self):
        review_path = Path(tempfile.gettempdir()) / "review-unknown.md"
        prompt_file = Path(tempfile.gettempdir()) / "prompt-unknown.md"
        prompt_file.write_text("system prompt", encoding="utf-8")

        with self.assertRaises(ValueError):
            attempt_stop_autocomplete(
                self._ctx(),
                "rev-3",
                review_path,
                prompt_file,
                "user prompt",
                reviewer_timeout_seconds=5,
                model="claude-sonnet-4-6",
                backend="codexx",
            )

    @patch(
        "claude_auto_review.stop.reviews.review_result.normalize_review_verdict_content",
        side_effect=lambda s, client_id=None, minimum_blocking_severity="medium": s,
    )
    @patch("claude_auto_review.stop.reviews.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.prompt_runner_codex.shutil.which", return_value="/usr/bin/codex")
    def test_attempt_stop_autocomplete_prefers_codex_last_message_file(self, mock_which, mock_run, _mock_norm):
        review_path = Path(tempfile.gettempdir()) / "review-last-message.md"
        prompt_file = Path(tempfile.gettempdir()) / "prompt-last-message.md"
        prompt_file.write_text("system prompt", encoding="utf-8")

        def _fake_run(*args, **kwargs):
            command = args[0]
            output_idx = command.index("--output-last-message")
            Path(command[output_idx + 1]).write_text("Clean - no issues found.", encoding="utf-8")
            return MagicMock(
                stdout='{"type":"turn.completed","message":{"text":"planning only"}}\n',
                stderr="",
                returncode=0,
                args=command,
            )

        mock_run.side_effect = _fake_run

        result = attempt_stop_autocomplete(
            self._ctx(),
            "rev-file",
            review_path,
            prompt_file,
            "user prompt",
            reviewer_timeout_seconds=5,
            model="gpt-5",
            backend="codex",
        )

        self.assertEqual(result.status, "output_written")
        self.assertEqual(review_path.read_text(encoding="utf-8"), "Clean - no issues found.")
        self.assertIn("--output-last-message", mock_run.call_args.args[0])
        mock_which.assert_called_once_with("codex")

    @patch(
        "claude_auto_review.stop.reviews.review_result.normalize_review_verdict_content",
        side_effect=lambda s, client_id=None, minimum_blocking_severity="medium": s,
    )
    @patch("claude_auto_review.stop.reviews.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.prompt_runner_codex.shutil.which", return_value="/usr/bin/codex")
    def test_attempt_stop_autocomplete_uses_codex_backend(self, mock_which, mock_run, _mock_norm):
        review_path = Path(tempfile.gettempdir()) / "review.md"
        prompt_file = Path(tempfile.gettempdir()) / "prompt.md"
        prompt_file.write_text("system prompt", encoding="utf-8")
        mock_run.return_value = MagicMock(
            stdout='{"type":"turn.completed","message":{"text":"Clean - no issues found."}}\n',
            stderr="",
            returncode=0,
            args=["/usr/bin/codex"],
        )

        result = attempt_stop_autocomplete(
            self._ctx(),
            "rev-1",
            review_path,
            prompt_file,
            "user prompt",
            reviewer_timeout_seconds=5,
            model="gpt-5",
            backend="codex",
        )

        self.assertEqual(result.status, "output_written")
        mock_which.assert_called_once_with("codex")
        self.assertNotIn("--json", mock_run.call_args.args[0])
        self.assertIn("--skip-git-repo-check", mock_run.call_args.args[0])
        self.assertEqual(mock_run.call_args.kwargs["input"], "system prompt\n\nuser prompt")

    @patch(
        "claude_auto_review.stop.reviews.review_result.normalize_review_verdict_content",
        side_effect=lambda s, client_id=None, minimum_blocking_severity="medium": s,
    )
    @patch("claude_auto_review.stop.reviews.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.prompt_runner_claude.shutil.which", return_value="/usr/bin/claude")
    def test_attempt_stop_autocomplete_uses_claude_backend(self, mock_which, mock_run, _mock_norm):
        review_path = Path(tempfile.gettempdir()) / "review-claude.md"
        prompt_file = Path(tempfile.gettempdir()) / "prompt-claude.md"
        prompt_file.write_text("system prompt", encoding="utf-8")
        mock_run.return_value = MagicMock(stdout="Clean - no issues found.", stderr="", returncode=0)

        result = attempt_stop_autocomplete(
            self._ctx(),
            "rev-2",
            review_path,
            prompt_file,
            "user prompt",
            reviewer_timeout_seconds=5,
            model="claude-sonnet-4-6",
            backend="claude",
        )

        self.assertEqual(result.status, "output_written")
        mock_which.assert_called_once_with("claude")
        self.assertEqual(mock_run.call_args.kwargs.get("input"), None)
        self.assertIn("user prompt", mock_run.call_args.args[0])


class TestBuildOpencodeReviewArgs(unittest.TestCase):
    def test_returns_run_with_file_flag(self):
        prompt_file = Path("/tmp/prompt.md")
        args = _build_opencode_review_args("claude-sonnet-4-6", prompt_file)
        self.assertEqual(args[0], "run")
        self.assertEqual(args[1], "--pure")
        self.assertIn("--model", args)
        model_idx = args.index("--model")
        self.assertEqual(args[model_idx + 1], "claude-sonnet-4-6")
        self.assertIn("--file", args)
        file_idx = args.index("--file")
        self.assertEqual(args[file_idx + 1], str(prompt_file))

    def test_passes_model_argument_through(self):
        args = _build_opencode_review_args("gpt-5", Path("/tmp/prompt.md"))
        self.assertIn("--model", args)
        model_idx = args.index("--model")
        self.assertEqual(args[model_idx + 1], "gpt-5")

    def test_skips_model_when_default(self):
        args = _build_opencode_review_args("default", Path("/tmp/prompt.md"))
        self.assertNotIn("--model", args)

    def test_skips_model_when_none_string(self):
        args = _build_opencode_review_args("none", Path("/tmp/prompt.md"))
        self.assertNotIn("--model", args)

    def test_skips_model_when_empty(self):
        args = _build_opencode_review_args("", Path("/tmp/prompt.md"))
        self.assertNotIn("--model", args)

    def test_no_sandbox_or_allowed_tools(self):
        args = _build_opencode_review_args("my-model", Path("/tmp/prompt.md"))
        self.assertNotIn("--sandbox", args)
        self.assertNotIn("--allowedTools", args)
        self.assertNotIn("--print", args)

    def test_no_stdin_dash(self):
        args = _build_opencode_review_args("my-model", Path("/tmp/prompt.md"))
        self.assertNotIn("-", args)


if __name__ == "__main__":
    unittest.main()
