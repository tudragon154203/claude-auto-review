import json
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.runtime.setup import ensure_project_settings
from tests.unit.state.support import StateTestCase


class TestEnsureProjectSettingsEdgeCases(StateTestCase, unittest.TestCase):
    def test_handles_non_dict_json(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text('"just a string"', encoding="utf-8")
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)
        self.assertIn("hooks", settings)

    def test_handles_invalid_json(self):
        """Test that ensure_project_settings recovers from JSON parse errors."""
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("invalid json{", encoding="utf-8")
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)
        self.assertIn("hooks", settings)

    def test_handles_oserror(self):
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
