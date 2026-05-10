import json
import tempfile
import unittest
from pathlib import Path

from claude_auto_review.runtime.setup import ensure_runtime
from claude_auto_review.settings import load_settings, should_skip_file


class RulesTests(unittest.TestCase):
    def test_initializes_project_rules_from_default_rules(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-rules-"))
        runtime = ensure_runtime(project_root, Path(__file__).resolve().parent.parent)
        self.assertIn("# Claude Auto Review Rules", runtime["rules_path"].read_text(encoding="utf-8"))

    def test_loads_project_settings_and_applies_skip_extensions(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-settings-"))
        settings_dir = project_root / ".claude"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"skipExtensions": [".MD"]}}),
            encoding="utf-8",
        )

        settings = load_settings(project_root)
        self.assertTrue(should_skip_file("README.md", settings))
        self.assertFalse(should_skip_file("src/app.ts", settings))

    def test_include_extensions_allowlist_filters_unlisted_files(self):
        settings = {"includeExtensions": ["py"], "skipExtensions": []}
        self.assertFalse(should_skip_file("claude_auto_review/paths.py", settings))
        self.assertTrue(should_skip_file("src/app.ts", settings))

    def test_skip_extensions_override_include_extensions(self):
        settings = {"includeExtensions": ["py"], "skipExtensions": ["py"]}
        self.assertTrue(should_skip_file("claude_auto_review/paths.py", settings))

    def test_malformed_settings_fall_back_to_defaults(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-settings-"))
        settings_dir = project_root / ".claude"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text("{not-json", encoding="utf-8")

        settings = load_settings(project_root)
        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["skipExtensions"], [])


if __name__ == "__main__":
    unittest.main()
