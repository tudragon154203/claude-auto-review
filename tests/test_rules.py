import json
import tempfile
import unittest
from pathlib import Path

from scripts.state import ensure_runtime, load_settings, should_skip_file


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


if __name__ == "__main__":
    unittest.main()
