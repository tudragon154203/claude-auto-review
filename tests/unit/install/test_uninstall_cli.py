import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.install.cli.uninstall import _remove_plugin_hooks, main


class TestUninstall(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.project_root = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_remove_plugin_hooks(self):
        settings = {
            "hooks": {
                "PostToolUse": [
                    {"command": "other-hook"},
                    {"hooks": [{"command": "python -m claude_auto_review.hooks.post_tool_use"}]},
                ],
                "Stop": [{"hooks": [{"command": "python -m claude_auto_review.hooks.stop_hook"}]}],
                "Other": [{"command": "something"}],
            }
        }

        modified = _remove_plugin_hooks(settings)
        self.assertTrue(modified)

        # In current logic, if all hooks in an entry are removed, the entry is removed.
        # If all entries in a hook_type are removed, the hook_type is deleted.
        hooks = settings.get("hooks", {})
        self.assertIn("PostToolUse", hooks)
        self.assertEqual(len(hooks["PostToolUse"]), 1)
        self.assertEqual(hooks["PostToolUse"][0]["command"], "other-hook")
        self.assertNotIn("Stop", hooks)
        self.assertEqual(hooks["Other"][0]["command"], "something")

    def test_remove_plugin_hooks_nested(self):
        settings = {
            "hooks": {"PostToolUse": [{"hooks": [{"command": "python -m claude_auto_review.hooks.post_tool_use"}]}]}
        }
        modified = _remove_plugin_hooks(settings)
        self.assertTrue(modified)
        # Everything removed -> "hooks" itself should be removed from settings if empty
        self.assertNotIn("hooks", settings)

    @patch("claude_auto_review.install.cli.uninstall.get_project_root")
    @patch("claude_auto_review.install.cli.uninstall.log_event")
    @patch("claude_auto_review.install.cli.uninstall.ensure_gitignore_entries")
    def test_main_uninstall_full(self, mock_gitignore, mock_log, mock_get_root):
        mock_get_root.return_value = self.project_root

        # Setup .claude/settings.json
        claude_dir = self.project_root / ".claude"
        claude_dir.mkdir()
        settings_path = claude_dir / "settings.json"
        settings_path.write_text(
            json.dumps({"hooks": {"Stop": [{"command": "python -m claude_auto_review.hooks.stop_hook"}]}}),
            encoding="utf-8",
        )

        # Setup runtime dir
        runtime_dir = claude_dir / "claude-auto-review"
        runtime_dir.mkdir()
        (runtime_dir / "state.jsonl").touch()

        # Setup .gitignore
        (self.project_root / ".gitignore").touch()

        with patch("sys.stdout", MagicMock()):
            exit_code = main()

        self.assertEqual(exit_code, 0)

        # Verify settings cleaned
        updated_settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertNotIn("Stop", updated_settings.get("hooks", {}))

        # Verify runtime dir removed (it might be ignored_errors=True in rmtree)
        self.assertFalse(runtime_dir.exists())

        # Verify gitignore called
        mock_gitignore.assert_called()


if __name__ == "__main__":
    unittest.main()
