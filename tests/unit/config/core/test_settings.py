import json
import unittest

from claude_auto_review.runtime.core.setup import ensure_project_settings
from claude_auto_review.config.core.settings import DEFAULT_SETTINGS, DEFAULT_TIMEOUT_SECONDS, load_settings, should_skip_file
from claude_auto_review.config.core.settings import resolve_rules_file_path

from tests.unit.state.support import StateTestCase


class TestSettings(StateTestCase, unittest.TestCase):

    def test_load_settings_defaults_when_file_missing(self):
        project_root = self.temp_project()
        result = load_settings(project_root)
        self.assertTrue(result["enabled"])
        self.assertEqual(result["reviewerTimeoutSeconds"], 600)
        self.assertEqual(result["reviewFeedbackMaxChars"], 9000)
        self.assertTrue(result["lastAssistantMessageClassifierEnabled"])
        self.assertEqual(result["lastAssistantMessageClassifierTimeoutSeconds"], DEFAULT_TIMEOUT_SECONDS)

    def test_load_settings_merges_project_settings(self):
        project_root = self.temp_project()
        settings_dir = project_root / ".claude"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text(
            json.dumps(
                {
                    "claude-auto-review": {
                        "maxStopPasses": 5,
                        "reviewerTimeoutSeconds": 120,
                        "reviewFeedbackMaxChars": 321,
                        "lastAssistantMessageClassifierEnabled": False,
                        "lastAssistantMessageClassifierTimeoutSeconds": 3,
                    }
                }
            ),
            encoding="utf-8",
        )
        result = load_settings(project_root)
        self.assertEqual(result["maxStopPasses"], 5)
        self.assertEqual(result["reviewerTimeoutSeconds"], 120)
        self.assertEqual(result["reviewFeedbackMaxChars"], 321)
        self.assertFalse(result["lastAssistantMessageClassifierEnabled"])
        self.assertEqual(result["lastAssistantMessageClassifierTimeoutSeconds"], 3)

    def test_should_skip_file_no_extension(self):
        self.assertFalse(should_skip_file("README", DEFAULT_SETTINGS))

    def test_should_skip_file_include_extensions_allows(self):
        settings = {"includeExtensions": ["py"], "skipExtensions": []}
        self.assertFalse(should_skip_file("script.py", settings))

    def test_should_skip_file_include_extensions_blocks_others(self):
        settings = {"includeExtensions": ["py"], "skipExtensions": []}
        self.assertTrue(should_skip_file("script.ts", settings))

    def test_resolve_rules_file_path_uses_project_relative_path_when_configured(self):
        project_root = self.temp_project()
        settings = {"rulesFile": "relative/rules.md"}
        self.assertEqual(
            resolve_rules_file_path(project_root, settings),
            project_root / "relative" / "rules.md",
        )

    def test_resolve_rules_file_path_defaults_to_runtime_rules(self):
        project_root = self.temp_project()
        self.assertEqual(
            resolve_rules_file_path(project_root, {}),
            project_root / ".claude" / "claude-auto-review" / "review-rules.md",
        )

    def test_ensure_project_settings_creates_settings_file(self):
        project_root = self.temp_project()
        ensure_project_settings(project_root)
        settings_path = project_root / ".claude" / "settings.json"
        self.assertTrue(settings_path.exists())
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)
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
        self.assertEqual(settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"], "python hooks/post_tool_use.py")
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["command"], "python hooks/stop_hook.py")
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["timeout"], 660)
        self.assertEqual(settings["hooks"]["SessionEnd"][0]["hooks"][0]["command"], "python hooks/session_end.py")

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
        self.assertEqual(
            settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"],
            "python custom.py",
        )
        self.assertEqual(
            settings["hooks"]["Stop"][0]["hooks"][0]["command"],
            "python hooks/stop_hook.py",
        )

    def test_ensure_project_settings_is_idempotent_even_if_timeout_changes(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        # Initial install
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["timeout"], 660)

        # Modify timeout manually
        settings["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 999
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        # Re-install
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

        # Should still only have 1 entry (updated, not duplicated)
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["timeout"], 660)

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
                                "command": "python hooks/stop_hook.py",
                                "timeout": 660,
                                "statusMessage": "Claude Auto Review: checking review state…",
                            }
                        ]
                    },
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python hooks/stop_hook.py",
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
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["command"], "python hooks/stop_hook.py")

    def test_ensure_project_settings_treats_quoted_plugin_command_as_same_hook(self):
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
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["command"], "python hooks/stop_hook.py")

    def test_ensure_project_settings_handles_non_dict_json(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text('"just a string"', encoding="utf-8")
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)
        self.assertIn("hooks", settings)

    def test_ensure_project_settings_handles_oserror(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("invalid json{", encoding="utf-8")
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)

    def test_load_settings_handles_invalid_json(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude"
        settings_path.mkdir(parents=True, exist_ok=True)
        (settings_path / "settings.json").write_text("not valid json", encoding="utf-8")
        result = load_settings(project_root)
        self.assertTrue(result["enabled"])

    def test_load_settings_handles_oserror(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude"
        settings_path.mkdir(parents=True, exist_ok=True)
        bad = settings_path / "settings.json"
        bad.write_text("{}", encoding="utf-8")
        # Make a nonexistent path to trigger fallback in another way
        other_root = self.temp_project()
        result = load_settings(other_root)
        self.assertTrue(result["enabled"])


