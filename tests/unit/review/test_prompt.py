import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.state.models import EditRecord
from claude_auto_review.review.prompt import _log_failure, _run_review_prompt, main
from claude_auto_review.stop.feedback import build_unreviewed_files_string


class TestReviewPrompt(unittest.TestCase):
    def test_build_unreviewed_files_string_joins_filenames(self):
        entries = [
            EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="src/a.ts", hash="1"),
            EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="src/b.ts", hash="2"),
        ]
        result = build_unreviewed_files_string(entries)
        self.assertEqual(result, "src/a.ts, src/b.ts")

    def test_build_unreviewed_files_string_empty(self):
        result = build_unreviewed_files_string([])
        self.assertEqual(result, "")

    def test_log_failure_handles_logging_error(self):
        with patch("claude_auto_review.review.prompt.log_failure", return_value=False):
            with patch("builtins.print") as mock_print:
                _log_failure(Path("/fake"), "c1", ValueError("test"))
        # On error, prints to stderr twice (message + traceback)
        self.assertEqual(mock_print.call_count, 2)

    def test_log_failure_prints_message_on_success(self):
        with patch("claude_auto_review.review.prompt.log_failure", return_value=True):
            with patch("builtins.print") as mock_print:
                _log_failure(Path("/fake"), "c1", ValueError("test"))
        mock_print.assert_called_once()
        self.assertEqual(mock_print.call_args.kwargs["file"], sys.stderr)

    @patch("claude_auto_review.review.prompt.log_event")
    @patch("claude_auto_review.review.prompt.write_project_script_shim")
    @patch("claude_auto_review.review.prompt.ensure_client_runtime")
    @patch("claude_auto_review.review.prompt.load_settings", return_value=PluginSettings(enabled=False))
    def test_run_review_prompt_disabled(self, mock_settings, mock_ensure, mock_shim, mock_log):
        with patch("builtins.print"):
            result = _run_review_prompt(Path("/fake/project"), "c1")
        self.assertEqual(result, 0)

    @patch("claude_auto_review.review.prompt.log_event")
    @patch("claude_auto_review.review.prompt.write_project_script_shim")
    @patch("claude_auto_review.review.prompt.ensure_client_runtime")
    @patch("claude_auto_review.review.prompt.load_settings", return_value=PluginSettings(enabled=True))
    @patch("claude_auto_review.review.prompt.get_unreviewed_files", return_value=[])
    @patch("claude_auto_review.review.prompt.load_state", return_value=[])
    def test_run_review_prompt_no_unreviewed(self, mock_state, mock_unrev, mock_settings, mock_ensure, mock_shim, mock_log):
        with patch("builtins.print"):
            result = _run_review_prompt(Path("/fake/project"), "c1")
        self.assertEqual(result, 0)

    @patch("claude_auto_review.review.prompt.log_event")
    @patch("claude_auto_review.review.prompt.write_project_script_shim")
    @patch("claude_auto_review.review.prompt.ensure_client_runtime")
    @patch("claude_auto_review.review.prompt.load_settings", return_value=PluginSettings(enabled=True))
    @patch("claude_auto_review.review.prompt.get_unreviewed_files", return_value=[{"file": "a.ts", "hash": "1"}])
    @patch("claude_auto_review.review.prompt.load_state", return_value=[])
    @patch("claude_auto_review.review.prompt.create_review_prompt_files")
    @patch("claude_auto_review.review.prompt.append_review_started")
    def test_run_review_prompt_normal_flow(self, mock_append, mock_create, mock_state, mock_unrev, mock_settings, mock_ensure, mock_shim, mock_log):
        mock_create.return_value = MagicMock(
            review_id="rev1", review_path=Path("/fake/review.md"),
            prompt_path=Path("/fake/prompt.md"), files=["a.ts"],
        )
        with patch("builtins.print") as mock_print:
            result = _run_review_prompt(Path("/fake/project"), "c1")
        self.assertEqual(result, 0)
        mock_append.assert_called_once()
        printed = "\n".join(call.args[0] for call in mock_print.call_args_list)
        self.assertIn("fix all Confirmed findings", printed)
        self.assertNotIn("CRITICAL or HIGH", printed)

    @patch("claude_auto_review.review.prompt._log_failure")
    @patch("claude_auto_review.review.prompt.get_client_id", return_value="c1")
    @patch("claude_auto_review.review.prompt.get_project_root", return_value=Path("/fake/project"))
    @patch("claude_auto_review.review.prompt.ensure_client_runtime")
    @patch("claude_auto_review.review.prompt.write_project_script_shim")
    @patch("claude_auto_review.review.prompt.load_settings", side_effect=RuntimeError("boom"))
    def test_main_catches_exception_and_logs(self, mock_settings, mock_shim, mock_ensure, mock_root, mock_client_id, mock_fail):
        result = main()
        self.assertEqual(result, 1)
        mock_fail.assert_called_once()


if __name__ == "__main__":
    unittest.main()
