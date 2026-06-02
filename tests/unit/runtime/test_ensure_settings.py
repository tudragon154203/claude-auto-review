import json
import unittest

from claude_auto_review.runtime.setup import ensure_project_settings
from tests.unit.state.support import StateTestCase


class TestEnsureProjectSettingsCreation(StateTestCase, unittest.TestCase):
    def test_creates_settings_file(self):
        project_root = self.temp_project()
        ensure_project_settings(project_root)
        settings_path = project_root / ".claude" / "settings.json"
        self.assertTrue(settings_path.exists())
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)
        self.assertEqual(settings["claude-auto-review"]["maxStopPasses"], 5)
        self.assertEqual(settings["claude-auto-review"]["minimumBlockingSeverity"], "medium")
        self.assertIn("reviewerModel", settings["claude-auto-review"])
        self.assertIn("hooks", settings)
        self.assertIn("PostToolUse", settings["hooks"])
        self.assertIn("Stop", settings["hooks"])
        self.assertIn("SessionEnd", settings["hooks"])

    def test_installs_claude_hooks_into_settings_json(self):
        project_root = self.temp_project()

        ensure_project_settings(project_root)

        settings_path = project_root / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertIn("hooks", settings)
        self.assertEqual(
            settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"],
            "python -m claude_auto_review.hooks.post_tool_use",
        )
        self.assertEqual(
            settings["hooks"]["Stop"][0]["hooks"][0]["command"], "python -m claude_auto_review.hooks.stop_hook"
        )
        self.assertIsNotNone(settings["hooks"]["Stop"][0]["hooks"][0]["timeout"])
        self.assertEqual(
            settings["hooks"]["SessionEnd"][0]["hooks"][0]["command"], "python -m claude_auto_review.hooks.session_end"
        )


class TestEnsureProjectSettingsPreservation(StateTestCase, unittest.TestCase):
    def test_does_not_overwrite_existing(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(
                {
                    "claude-auto-review": {"maxStopPasses": 99, "minimumBlockingSeverity": "critical"},
                    "hooks": {
                        "PostToolUse": [
                            {
                                "matcher": "Write",
                                "hooks": [{"type": "command", "command": "python custom.py"}],
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
        self.assertEqual(settings["claude-auto-review"]["minimumBlockingSeverity"], "critical")
        self.assertIn("hooks", settings)
        post_use_commands = [h["command"] for entry in settings["hooks"]["PostToolUse"] for h in entry["hooks"]]
        self.assertIn("python custom.py", post_use_commands)
        self.assertIn("python -m claude_auto_review.hooks.post_tool_use", post_use_commands)
        self.assertEqual(
            settings["hooks"]["Stop"][0]["hooks"][0]["command"],
            "python -m claude_auto_review.hooks.stop_hook",
        )

    def test_preserves_unknown_plugin_keys(self):
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
        self.assertEqual(settings["claude-auto-review"]["minimumBlockingSeverity"], "medium")

    def test_is_idempotent_even_if_timeout_changes(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        original_timeout = settings["hooks"]["Stop"][0]["hooks"][0]["timeout"]

        settings["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 999
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["timeout"], original_timeout)

    def test_deduplicates_existing_plugin_hooks(self):
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

        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(
            settings["hooks"]["Stop"][0]["hooks"][0]["command"], "python -m claude_auto_review.hooks.stop_hook"
        )

    def test_treats_quoted_plugin_command_as_same_hook(self):
        """Verify that a quoted legacy command path is normalized to the canonical module form.

        The hook identity logic strips quotes and resolves ``hooks/stop_hook.py`` to
        ``python -m claude_auto_review.hooks.stop_hook``, so re-install should not
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

        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(
            settings["hooks"]["Stop"][0]["hooks"][0]["command"], "python -m claude_auto_review.hooks.stop_hook"
        )


if __name__ == "__main__":
    unittest.main()
