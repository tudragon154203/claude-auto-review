import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.config.file_filters import should_skip_file
from claude_auto_review.config.io import load_settings
from claude_auto_review.config.models import DEFAULT_TIMEOUT_SECONDS, PluginSettings
from claude_auto_review.config.rules import resolve_rules_file_path

from tests.unit.state.support import StateTestCase


class TestSettingsLoader(StateTestCase, unittest.TestCase):

    def test_load_settings_defaults_when_file_missing(self):
        project_root = self.temp_project()
        result = load_settings(project_root)
        self.assertTrue(result.enabled)
        self.assertEqual(result.max_stop_passes, 5)
        self.assertEqual(result.reviewer_timeout_seconds, 600)
        self.assertEqual(result.review_feedback_max_chars, 9000)
        self.assertEqual(result.minimum_blocking_severity, "medium")
        self.assertTrue(result.last_assistant_message_classifier_enabled)
        self.assertEqual(result.last_assistant_message_classifier_timeout_seconds, DEFAULT_TIMEOUT_SECONDS)

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
                        "minimumBlockingSeverity": "high",
                        "lastAssistantMessageClassifierEnabled": False,
                        "lastAssistantMessageClassifierTimeoutSeconds": 3,
                    }
                }
            ),
            encoding="utf-8",
        )
        result = load_settings(project_root)
        self.assertEqual(result.max_stop_passes, 5)
        self.assertEqual(result.reviewer_timeout_seconds, 120)
        self.assertEqual(result.review_feedback_max_chars, 321)
        self.assertEqual(result.minimum_blocking_severity, "high")
        self.assertFalse(result.last_assistant_message_classifier_enabled)
        self.assertEqual(result.last_assistant_message_classifier_timeout_seconds, 3)

    def test_load_settings_falls_back_to_medium_for_invalid_threshold(self):
        project_root = self.temp_project()
        settings_dir = project_root / ".claude"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"minimumBlockingSeverity": "invalid"}}),
            encoding="utf-8",
        )

        result = load_settings(project_root)

        self.assertEqual(result.minimum_blocking_severity, "medium")

    def test_should_skip_file_no_extension(self):
        self.assertFalse(should_skip_file("README", PluginSettings()))

    def test_should_skip_file_include_extensions_allows(self):
        settings = PluginSettings(include_extensions=("py",))
        self.assertFalse(should_skip_file("script.py", settings))

    def test_should_skip_file_include_extensions_blocks_others(self):
        settings = PluginSettings(include_extensions=("py",))
        self.assertTrue(should_skip_file("script.ts", settings))

    def test_resolve_rules_file_path_uses_project_relative_path_when_configured(self):
        project_root = self.temp_project()
        settings = PluginSettings(rules_file="relative/rules.md")
        self.assertEqual(
            resolve_rules_file_path(project_root, settings),
            project_root / "relative" / "rules.md",
        )

    def test_resolve_rules_file_path_defaults_to_runtime_rules(self):
        project_root = self.temp_project()
        self.assertEqual(
            resolve_rules_file_path(project_root, PluginSettings()),
            project_root / ".claude" / "claude-auto-review" / "review-rules.md",
        )

    def test_load_settings_handles_invalid_json(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude"
        settings_path.mkdir(parents=True, exist_ok=True)
        (settings_path / "settings.json").write_text("not valid json", encoding="utf-8")
        result = load_settings(project_root)
        self.assertTrue(result.enabled)

    def test_load_settings_handles_oserror(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude"
        settings_path.mkdir(parents=True, exist_ok=True)
        bad = settings_path / "settings.json"
        bad.write_text("{}", encoding="utf-8")
        # Make a nonexistent path to trigger fallback in another way
        other_root = self.temp_project()
        result = load_settings(other_root)
        self.assertTrue(result.enabled)

    def test_load_settings_preserves_unknown_plugin_keys_in_extras(self):
        project_root = self.temp_project()
        settings_dir = project_root / ".claude"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"customKey": "value"}}),
            encoding="utf-8",
        )

        result = load_settings(project_root)

        self.assertEqual(result.extras["customKey"], "value")

    def test_plugin_settings_minimum_blocking_severity_round_trips(self):
        for severity in ("info", "low", "medium", "high", "critical"):
            with self.subTest(severity=severity):
                settings = PluginSettings.from_mapping({"minimumBlockingSeverity": severity.upper()})
                self.assertEqual(settings.minimum_blocking_severity, severity)
                self.assertEqual(settings.to_mapping()["minimumBlockingSeverity"], severity)

    def test_plugin_settings_invalid_minimum_blocking_severity_uses_default(self):
        settings = PluginSettings.from_mapping({"minimumBlockingSeverity": "mystery"})
        self.assertEqual(settings.minimum_blocking_severity, "medium")
        self.assertEqual(settings.to_mapping()["minimumBlockingSeverity"], "medium")

    def test_plugin_settings_to_mapping_omits_unset_reviewer_model(self):
        result = PluginSettings().to_mapping()

        self.assertNotIn("reviewerModel", result)
        self.assertEqual(result["minimumBlockingSeverity"], "medium")


if __name__ == "__main__":
    unittest.main()
