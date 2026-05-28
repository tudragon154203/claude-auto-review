import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.reviews.codex_output import _extract_codex_final_message
from claude_auto_review.stop.reviews.prompt_runner import (
    attempt_stop_autocomplete,
)
from claude_auto_review.stop.reviews.review_args import (
    _build_claude_review_args,
    _build_codex_review_args,
)


class TestPromptRunnerCodex(unittest.TestCase):
    def _ctx(self):
        return RuntimeContext(project_root=Path("/fake"), client_id="client-1")

    def test_build_codex_review_args(self):
        self.assertEqual(
            _build_codex_review_args("gpt-5"),
            ["exec", "--skip-git-repo-check", "--sandbox", "read-only", "--model", "gpt-5", "-"],
        )

    @patch(
        "claude_auto_review.stop.reviews.review_result.normalize_review_verdict_content",
        side_effect=lambda s, client_id=None, minimum_blocking_severity="medium": s,
    )
    @patch("claude_auto_review.stop.reviews.prompt_runner.run_captured")
    @patch("claude_auto_review.stop.reviews.prompt_runner.shutil.which", return_value="/usr/bin/codex")
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

    def test_build_claude_review_args(self):
        self.assertEqual(
            _build_claude_review_args("claude-sonnet-4-6")[:4],
            ["--print", "--bare", "--allowedTools", "Read"],
        )

    def test_extract_codex_final_message_uses_turn_completed_message(self):
        stdout = '{"type":"turn.completed","message":"Clean - no issues found."}\n'
        self.assertEqual(_extract_codex_final_message(stdout), "Clean - no issues found.")

    def test_extract_codex_final_message_handles_structured_msg(self):
        stdout = '{"type":"turn.completed","message":{"text":"Clean from dict."}}\n'
        self.assertEqual(_extract_codex_final_message(stdout), "Clean from dict.")

        stdout_list = '{"type":"turn.completed","message":[{"text":"Clean from list dict."}]}\n'
        self.assertEqual(_extract_codex_final_message(stdout_list), "Clean from list dict.")

    def test_extract_codex_final_message_handles_interleaved_raw_text(self):
        # Case from gpt-5.4-mini where it starts with raw text then emits JSON events
        stdout = (
            "Looking at the diff and current file snapshots, I'll analyze the changes...\n"
            '{"type":"thread.started","thread_id":"t1"}\n'
            '{"type":"turn.started"}\n'
            '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"\\n"}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":56}}\n'
        )
        result = _extract_codex_final_message(stdout)
        self.assertIn("Looking at the diff", result)
        self.assertNotIn("turn.started", result)  # JSON control events are skipped

    def test_extract_codex_final_message_keeps_brace_prefixed_lines(self):
        # Lines starting with { but not valid JSON should be kept as raw text
        stdout = "First line of output\n" "{not valid json but should be kept}\n" "Second line of output\n"
        self.assertEqual(
            _extract_codex_final_message(stdout),
            "First line of output\n{not valid json but should be kept}\nSecond line of output",
        )

    def test_extract_codex_final_message_preserves_non_dict_json_as_raw(self):
        # Lines that parse as JSON but aren't dicts may contain user content - preserve them
        stdout = "First line\n" '["a", "b"]\n' '"just a string"\n' "Second line\n"
        self.assertEqual(_extract_codex_final_message(stdout), 'First line\n["a", "b"]\n"just a string"\nSecond line')

    def test_extract_codex_final_message_strips_preamble_if_header_found(self):
        stdout = "Certainly! I will review the changes now.\n" "# Review rev-123 - 2026-05-25\n" "## Findings\n" "None."
        result = _extract_codex_final_message(stdout)
        self.assertTrue(result.startswith("# Review rev-123 - 2026-05-25"))

    def test_extract_codex_final_message_uses_last_review_header(self):
        # Model may discuss format before actual review - we want the last occurrence
        stdout = (
            "The format should be: # Review rev-OLD - old date\n"
            "No wait, the format is different. Let me check: # Review rev-123 - 2026-05-25\n"
            "## Findings\n"
            "None."
        )
        self.assertEqual(_extract_codex_final_message(stdout), "# Review rev-123 - 2026-05-25\n## Findings\nNone.")

    def test_extract_codex_final_message_accumulates_all_parts(self):
        stdout = (
            '{"type":"item.completed","item":{"type":"agent_message","text":"Part 1"}}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"Part 2"}}\n'
        )
        self.assertEqual(_extract_codex_final_message(stdout), "Part 1\nPart 2")

    def test_extract_codex_final_message_skips_empty_parts(self):
        # Empty/whitespace-only messages from JSON are skipped
        stdout = (
            '{"type":"item.completed","item":{"type":"agent_message","text":"Real content"}}\n'
            '{"type":"item.completed","item":{"id":"i1","type":"agent_message","text":"   "}}\n'
        )
        self.assertEqual(_extract_codex_final_message(stdout), "Real content")

    def test_extract_codex_final_message_falls_back_to_raw_if_no_meaningful_json(self):
        # When JSON events have no recognized message content, fall back to raw stdout
        stdout = '{"type":"turn.started"}\n{"type":"turn.completed"}\n'
        # These are skipped, so messages is empty, fallback returns original stdout
        self.assertEqual(_extract_codex_final_message(stdout), stdout)

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
    @patch("claude_auto_review.stop.reviews.prompt_runner.shutil.which", return_value="/usr/bin/codex")
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
    @patch("claude_auto_review.stop.reviews.prompt_runner.shutil.which", return_value="/usr/bin/claude")
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


if __name__ == "__main__":
    unittest.main()
