import json
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.runtime.setup import ensure_project_settings

from tests.unit.state.support import StateTestCase


class TestEnsureProjectSettings(StateTestCase, unittest.TestCase):

    def test_ensure_project_settings_creates_settings_file(self):
        project_root = self.temp_project()
        ensure_project_settings(project_root)
        settings_path = project_root / ".claude" / "settings.json"
        self.assertTrue(settings_path.exists())
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)
        self.assertEqual(settings["claude-auto-review"]["maxStopPasses"], 5)
        self.assertIn("hooks", settings)
        self.assertIn("PostToolUse", settings["hooks"])
        self.assertIn("Stop", settings["hooks"])
        self.assertIn("SessionEnd", settings["hooks"])

    def test_ensure_project_settings_installs_claude_hooks_into_settings_json(self):
        project_root = self.temp_project()

        ensure_project_settings(project_root)

        settings_path = project_root / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertIn("hooks", settings)
        self.assertEqual(settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"], "python -m claude_auto_review.hooks.post_tool_use")
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["command"], "python -m claude_auto_review.hooks.stop_hook")
        self.assertIsNotNone(settings["hooks"]["Stop"][0]["hooks"][0]["timeout"])
        self.assertEqual(settings["hooks"]["SessionEnd"][0]["hooks"][0]["command"], "python -m claude_auto_review.hooks.session_end")

    def test_ensure_project_settings_does_not_overwrite_existing(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(
                {
                    "claude-auto-review": {"maxStopPasses": 99},
                    "hooks": {
                        "PostToolUse": [
                            {
                                "matcher": "Write",
                                "hooks": [
                                    {"type": "command", "command": "python custom.py"}
                                ],
                            }
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertEqual(settings["claude-auto-review"]["maxStopPasses"], 99)
        self.assertIn("hooks", settings)
        # Custom PostToolUse hook must be preserved
        post_use_commands = [
            h["command"]
            for entry in settings["hooks"]["PostToolUse"]
            for h in entry["hooks"]
        ]
        self.assertIn("python custom.py", post_use_commands)
        # Plugin PostToolUse hook must also be added alongside the custom one
        self.assertIn("python -m claude_auto_review.hooks.post_tool_use", post_use_commands)
        self.assertEqual(
            settings["hooks"]["Stop"][0]["hooks"][0]["command"],
            "python -m claude_auto_review.hooks.stop_hook",
        )

    def test_ensure_project_settings_preserves_unknown_plugin_keys(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps({"claude-auto-review": {"customKey": "value"}}),
            encoding="utf-8",
        )

        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(settings["claude-auto-review"]["customKey"], "value")
        self.assertEqual(settings["claude-auto-review"]["reviewerTimeoutSeconds"], 600)

    def test_ensure_project_settings_is_idempotent_even_if_timeout_changes(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        # Initial install
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        original_timeout = settings["hooks"]["Stop"][0]["hooks"][0]["timeout"]

        # Modify timeout manually
        settings["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 999
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        # Re-install
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

        # Should still only have 1 entry (updated, not duplicated)
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["timeout"], original_timeout)

    def test_ensure_project_settings_deduplicates_existing_plugin_hooks(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        # Pre-populate settings with duplicate plugin hooks
        initial = {
            "hooks": {
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python -m claude_auto_review.hooks.stop_hook",
                                "timeout": 660,
                                "statusMessage": "Claude Auto Review: checking review state…",
                            }
                        ]
                    },
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python -m claude_auto_review.hooks.stop_hook",
                                "timeout": 660,
                                "statusMessage": "Claude Auto Review: checking review state…",
                            }
                        ]
                    },
                ]
            }
        }
        settings_path.write_text(json.dumps(initial), encoding="utf-8")

        # Re-run install
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

        # Should collapse to a single Stop plugin hook (non-plugin preserved)
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["command"], "python -m claude_auto_review.hooks.stop_hook")

    def test_ensure_project_settings_treats_quoted_plugin_command_as_same_hook(self):
        """Verify that a quoted legacy command path is normalized to the canonical module form.

        The hook identity logic strips quotes and resolves `hooks/stop_hook.py` to
        `python -m claude_auto_review.hooks.stop_hook`, so re-install should not
        create a duplicate entry.
        """
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        initial = {
            "hooks": {
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'python "hooks/stop_hook.py"',
                                "timeout": 660,
                            }
                        ]
                    }
                ]
            }
        }
        settings_path.write_text(json.dumps(initial), encoding="utf-8")

        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

        # Should recognize the quoted path as the same plugin hook and normalize it
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["command"], "python -m claude_auto_review.hooks.stop_hook")

    def test_ensure_project_settings_handles_non_dict_json(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text('"just a string"', encoding="utf-8")
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)
        self.assertIn("hooks", settings)

    def test_ensure_project_settings_handles_invalid_json(self):
        """Test that ensure_project_settings recovers from JSON parse errors."""
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("invalid json{", encoding="utf-8")
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)
        self.assertIn("hooks", settings)

    def test_ensure_project_settings_handles_oserror(self):
        """Test that ensure_project_settings recovers from OS errors when reading settings.

        _load_settings_document catches OSError internally and returns {}.
        We trigger a real OSError by making settings_path.read_text() raise,
        while leaving all other file reads (hooks.json, etc.) unaffected.
        """
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("{}", encoding="utf-8")

        call_count = 0
        original_read_text = Path.read_text

        def selective_read_text(self, *args, **kwargs):
            nonlocal call_count
            # Raise OSError only on the first read of this specific file
            if str(self) == str(settings_path) and call_count == 0:
                call_count += 1
                raise OSError("permission denied")
            return original_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", selective_read_text):
            ensure_project_settings(project_root)

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)
        self.assertIn("hooks", settings)


if __name__ == "__main__":
    unittest.main()
