import unittest

from scripts.state import (
    cancel_runtime,
    cancel_session,
    client_state_path,
    client_run_dir,
    client_reviews_dir,
    ensure_client_runtime,
    ensure_runtime,
    load_state,
)

from tests.state.support import StateTestCase


class TestRuntime(StateTestCase, unittest.TestCase):

    def test_ensure_runtime_creates_directories(self):
        project_root = self.temp_project()
        result = ensure_runtime(project_root)
        self.assertTrue((result["base_dir"]).is_dir())
        self.assertTrue(result["state_path"].parent.exists())

    def test_ensure_runtime_creates_default_rules_file(self):
        project_root = self.temp_project()
        result = ensure_runtime(project_root)
        self.assertTrue(result["rules_path"].exists())

    def test_ensure_runtime_without_default_rules_creates_fallback(self):
        project_root = self.temp_project()
        fake_plugin = self.temp_project()
        # No rules/default-rules.md in fake_plugin
        ensure_runtime(project_root, plugin_root=fake_plugin)
        rules_path = project_root / ".claude" / "claude-auto-review" / "rules.md"
        self.assertTrue(rules_path.exists())
        content = rules_path.read_text(encoding="utf-8")
        self.assertIn("Review semantic correctness", content)

    def test_cancel_runtime_removes_state_and_directories(self):
        project_root = self.temp_project()
        ensure_runtime(project_root)
        cancel_runtime(project_root)
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "state.jsonl").exists())

    def test_cancel_runtime_removes_client_data(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "test-client")
        cancel_runtime(project_root, client_id="test-client")
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-client").exists())

    def test_cancel_session_removes_client_state(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "session-a")
        ensure_client_runtime(project_root, "session-b")

        removed = cancel_session(project_root, client_id="session-a")

        self.assertFalse(
            (project_root / ".claude" / "claude-auto-review" / "clients" / "client-session-a").exists()
        )
        self.assertTrue(
            (project_root / ".claude" / "claude-auto-review" / "clients" / "client-session-b").exists()
        )
        self.assertGreater(len(removed), 0)

    def test_cancel_session_noop_when_no_data(self):
        project_root = self.temp_project()
        removed = cancel_session(project_root, client_id="nonexistent")
        self.assertEqual(removed, [])

