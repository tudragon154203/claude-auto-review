import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from claude_auto_review.install.cancel_cli import main


class TestCancelCli(unittest.TestCase):
    @patch("claude_auto_review.install.cancel_cli.log_event")
    @patch("claude_auto_review.install.cancel_cli.cancel_runtime", return_value=[Path("/fake/a"), Path("/fake/b")])
    @patch("claude_auto_review.install.cancel_cli.get_client_id", return_value="test-client")
    @patch("claude_auto_review.install.cancel_cli.get_project_root", return_value=Path("/fake/project"))
    def test_main_removes_and_prints(self, mock_root, mock_client_id, mock_cancel, mock_log):
        with patch("builtins.print") as mock_print:
            result = main()
        self.assertEqual(result, 0)
        mock_cancel.assert_called_once_with(Path("/fake/project"), client_id="test-client")
        mock_log.assert_called_once()
        mock_print.assert_any_call("Claude Auto Review cancelled. Removed:")
        mock_print.assert_any_call(f"- {Path('/fake/a')}")

    @patch("claude_auto_review.install.cancel_cli.log_event")
    @patch("claude_auto_review.install.cancel_cli.cancel_runtime", return_value=[])
    @patch("claude_auto_review.install.cancel_cli.get_client_id", return_value="no-client")
    @patch("claude_auto_review.install.cancel_cli.get_project_root", return_value=Path("/fake/project"))
    def test_main_prints_noop_when_no_runtime(self, mock_root, mock_client_id, mock_cancel, mock_log):
        with patch("builtins.print") as mock_print:
            result = main()
        self.assertEqual(result, 0)
        mock_print.assert_called_with("Claude Auto Review: no active runtime state found.")


if __name__ == "__main__":
    unittest.main()
