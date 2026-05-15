import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from claude_auto_review.install.setup_cli import main


class TestSetupCli(unittest.TestCase):
    @patch("claude_auto_review.install.setup_cli.log_event")
    @patch("claude_auto_review.install.setup_cli.ensure_gitignore_entries")
    @patch("claude_auto_review.install.setup_cli.copy_if_changed")
    @patch("claude_auto_review.install.setup_cli.write_runtime_shims")
    @patch("claude_auto_review.install.setup_cli.ensure_project_settings")
    @patch("claude_auto_review.install.setup_cli.ensure_runtime", return_value={"base_dir": Path("/fake/project/.claude/claude-auto-review")})
    @patch("claude_auto_review.install.setup_cli.get_project_root", return_value=Path("/fake/project"))
    def test_main_creates_runtime(self, mock_root, mock_runtime, mock_settings, mock_shims, mock_copy, mock_gitignore, mock_log):
        with patch("builtins.print") as mock_print:
            result = main()
        self.assertEqual(result, 0)
        mock_runtime.assert_called_once()
        mock_settings.assert_called_once()
        mock_shims.assert_called_once()
        mock_copy.assert_called_once()
        mock_gitignore.assert_called_once()
        mock_log.assert_called_once_with(Path("/fake/project"), "setup_completed")
        self.assertIn("claude-auto-review", str(mock_print.call_args))


if __name__ == "__main__":
    unittest.main()
