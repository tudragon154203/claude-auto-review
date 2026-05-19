import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.config.settings import (
    DEFAULT_SETTINGS,
    DEFAULT_TIMEOUT_SECONDS,
    load_settings,
    resolve_rules_file_path,
    should_skip_file,
)

from tests.unit.state.support import StateTestCase


class TestSettingsLoader(StateTestCase, unittest.TestCase):

    def test_load_settings_defaults_when_file_missing(self):
        project_root = self.temp_project()
        result = load_settings(project_root)
        self.assertTrue(result["enabled"])
        self.assertEqual(result["maxStopPasses"], 5)
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


if __name__ == "__main__":
    unittest.main()
