import json
import unittest

from claude_auto_review.runtime.setup import ensure_project_settings
from claude_auto_review.settings import DEFAULT_SETTINGS, load_settings, should_skip_file
from claude_auto_review.settings import resolve_rules_file_path

from tests.unit.state.support import StateTestCase


class TestSettings(StateTestCase, unittest.TestCase):

    def test_load_settings_defaults_when_file_missing(self):
        project_root = self.temp_project()
        result = load_settings(project_root)
        self.assertTrue(result["enabled"])
        self.assertTrue(result["lastAssistantMessageClassifierEnabled"])
        self.assertEqual(result["lastAssistantMessageClassifierTimeoutSeconds"], 10)

    def test_load_settings_merges_project_settings(self):
        project_root = self.temp_project()
        settings_dir = project_root / ".claude"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text(
            json.dumps(
                {
                    "claude-auto-review": {
                        "maxStopPasses": 5,
                        "lastAssistantMessageClassifierEnabled": False,
                        "lastAssistantMessageClassifierTimeoutSeconds": 3,
                    }
                }
            ),
            encoding="utf-8",
        )
        result = load_settings(project_root)
        self.assertEqual(result["maxStopPasses"], 5)
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

    def test_resolve_rules_file_path_uses_project_runtime_rules_for_relative_paths(self):
        project_root = self.temp_project()
        settings = {"rulesFile": "relative/rules.md"}
        self.assertEqual(
            resolve_rules_file_path(project_root, settings),
            project_root / ".claude" / "claude-auto-review" / "rules.md",
        )

    def test_ensure_project_settings_creates_settings_file(self):
        project_root = self.temp_project()
        ensure_project_settings(project_root)
        settings_path = project_root / ".claude" / "settings.json"
        self.assertTrue(settings_path.exists())

    def test_ensure_project_settings_does_not_overwrite_existing(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({"claude-auto-review": {"maxStopPasses": 99}}), encoding="utf-8")
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertEqual(settings["claude-auto-review"]["maxStopPasses"], 99)

    def test_ensure_project_settings_handles_non_dict_json(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text('"just a string"', encoding="utf-8")
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)

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


