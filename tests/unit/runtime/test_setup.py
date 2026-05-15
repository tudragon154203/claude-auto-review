import unittest
from pathlib import Path

from claude_auto_review.runtime.setup import ensure_client_runtime, ensure_runtime

from tests.unit.state.support import StateTestCase


class TestRuntimeSetup(StateTestCase, unittest.TestCase):

    def test_ensure_runtime_creates_directories(self):
        project_root = self.temp_project()
        result = ensure_runtime(project_root)
        self.assertTrue((result["base_dir"]).is_dir())
        self.assertTrue(result["state_path"].parent.exists())

    def test_ensure_runtime_creates_default_rules_file(self):
        project_root = self.temp_project()
        result = ensure_runtime(project_root)
        self.assertTrue(result["rules_path"].exists())
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "state.jsonl").exists())

    def test_ensure_runtime_without_default_rules_creates_fallback(self):
        project_root = self.temp_project()
        fake_plugin = self.temp_project()
        ensure_runtime(project_root, plugin_root=fake_plugin)
        rules_path = project_root / ".claude" / "claude-auto-review" / "review-rules.md"
        self.assertTrue(rules_path.exists())
        content = rules_path.read_text(encoding="utf-8")
        self.assertIn("Review semantic correctness", content)

    def test_ensure_client_runtime_creates_client_directory(self):
        project_root = self.temp_project()
        client_dir = ensure_client_runtime(project_root, "test-client")
        self.assertTrue(client_dir.exists())
        self.assertTrue((client_dir / "state.jsonl").exists())
