import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support_paths import FAKE_ROOT

from claude_auto_review.config.settings.models import PluginSettings
from claude_auto_review.stop.orchestration.response_actions import (
    _format_failure_hint,
    prepare_pending_review_block,
)
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus
from claude_auto_review.stop.reviews.types.result import AutocompleteResult


def _ctx():
    return RuntimeContext(
        project_root=FAKE_ROOT,
        client_id="c",
        settings=PluginSettings(),
        payload={},
    )


def _unreviewed():
    mock = MagicMock()
    mock.file = "src/example.py"
    return [mock]


class TestFormatFailureHint(unittest.TestCase):
    def test_none_yields_empty(self):
        self.assertEqual(_format_failure_hint(None), "")

    def test_output_written_yields_empty(self):
        result = AutocompleteResult(status=AutocompleteStatus.OUTPUT_WRITTEN)
        self.assertEqual(_format_failure_hint(result), "")

    def test_cli_not_found_mentions_path(self):
        result = AutocompleteResult(status=AutocompleteStatus.CLI_NOT_FOUND)
        hint = _format_failure_hint(result)
        self.assertIn("PATH", hint)

    def test_timeout_mentions_setting(self):
        result = AutocompleteResult(status=AutocompleteStatus.TIMEOUT)
        hint = _format_failure_hint(result)
        self.assertIn("timed out", hint)
        self.assertIn("reviewerTimeoutSeconds", hint)

    def test_nonzero_includes_returncode_and_stderr(self):
        result = AutocompleteResult(
            status=AutocompleteStatus.NONZERO,
            stderr="Error: Missing optional dependency @openai/codex-win32-x64",
            returncode=1,
        )
        hint = _format_failure_hint(result)
        self.assertIn("code 1", hint)
        self.assertIn("Missing optional dependency", hint)

    def test_empty_stdout_includes_stripped_stderr(self):
        result = AutocompleteResult(
            status=AutocompleteStatus.EMPTY_STDOUT,
            stderr="\x1b[0m\n> build · big-pickle\n\x1b[0m\n",
        )
        hint = _format_failure_hint(result)
        self.assertIn("no output", hint)
        self.assertIn("build", hint)
        self.assertNotIn("\x1b[0m", hint)

    def test_error_includes_stderr(self):
        result = AutocompleteResult(status=AutocompleteStatus.ERROR, stderr="FileNotFoundError: boom")
        hint = _format_failure_hint(result)
        self.assertIn("error", hint)
        self.assertIn("FileNotFoundError", hint)

    def test_long_stderr_is_truncated(self):
        result = AutocompleteResult(status=AutocompleteStatus.ERROR, stderr="x" * 2000)
        hint = _format_failure_hint(result)
        self.assertLessEqual(len(hint), 600)
        self.assertTrue(hint.endswith("..."))


class TestPreparePendingReviewBlock(unittest.TestCase):
    def test_no_failure_info_matches_original_message(self):
        result = prepare_pending_review_block(
            _ctx(), "rev1",
            Path(FAKE_ROOT) / "review.md",
            Path(FAKE_ROOT) / "prompt.md",
            _unreviewed(),
        )
        self.assertNotIn("could not complete", result.feedback)
        self.assertIn("placeholder until the review is completed", result.feedback)
        self.assertIn("prompt.md", result.feedback)

    def test_failure_info_inserts_hint_paragraph(self):
        failure = AutocompleteResult(
            status=AutocompleteStatus.NONZERO,
            stderr="Error: codex is broken",
            returncode=2,
        )
        result = prepare_pending_review_block(
            _ctx(), "rev1",
            Path(FAKE_ROOT) / "review.md",
            Path(FAKE_ROOT) / "prompt.md",
            _unreviewed(),
            failure_info=failure,
        )
        self.assertIn("could not complete the review", result.feedback)
        self.assertIn("code 2", result.feedback)
        self.assertIn("codex is broken", result.feedback)
        self.assertIn("placeholder until the review is completed", result.feedback)

    def test_output_written_failure_info_omits_hint(self):
        failure = AutocompleteResult(status=AutocompleteStatus.OUTPUT_WRITTEN)
        result = prepare_pending_review_block(
            _ctx(), "rev1",
            Path(FAKE_ROOT) / "review.md",
            Path(FAKE_ROOT) / "prompt.md",
            _unreviewed(),
            failure_info=failure,
        )
        self.assertNotIn("could not complete", result.feedback)


if __name__ == "__main__":
    unittest.main()
