import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.install.cli.setup import main


class TestSetupCli(unittest.TestCase):
    def test_main_creates_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            base_dir = project_root / ".claude" / "claude-auto-review"

            with (
                patch("claude_auto_review.paths.path_utils.ProjectContext.from_environment", return_value=MagicMock(project_root=project_root, plugin_root=project_root)),
                patch("claude_auto_review.install.cli.setup.ensure_runtime", return_value={"base_dir": base_dir}),
                patch("claude_auto_review.install.cli.setup.ensure_project_settings"),
                patch("claude_auto_review.install.cli.setup.write_runtime_shims"),
                patch("claude_auto_review.install.cli.setup.copy_if_changed"),
                patch("claude_auto_review.install.cli.setup.ensure_gitignore_entries"),
                patch("claude_auto_review.install.cli.setup.log_event") as mock_log,
                patch("builtins.print") as mock_print,
            ):
                result = main()

        self.assertEqual(result, 0)
        mock_log.assert_called_once_with(project_root, "setup_completed")
        self.assertIn("claude-auto-review", str(mock_print.call_args))


if __name__ == "__main__":
    unittest.main()
