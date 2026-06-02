import json
import unittest
from unittest.mock import patch

from claude_auto_review.runtime.hook_context import build_hook_runtime_context
from tests.unit.state.support import StateTestCase


class TestBuildHookRuntimeContext(StateTestCase, unittest.TestCase):
    def test_build_hook_runtime_context_resolves_payload_client_and_settings(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"enabled": False}}),
            encoding="utf-8",
        )

        with patch("claude_auto_review.runtime.hook_context.get_project_root", return_value=project_root):
            ctx = build_hook_runtime_context(json.dumps({"session_id": "session-1"}))

        self.assertEqual(ctx.project_root, project_root)
        self.assertEqual(ctx.client_id, "session-1")
        self.assertFalse(ctx.settings.core.enabled)
        self.assertEqual(ctx.payload["session_id"], "session-1")
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "clients").exists())

    def test_build_hook_runtime_context_can_skip_client_creation(self):
        project_root = self.temp_project()

        with patch("claude_auto_review.runtime.hook_context.get_project_root", return_value=project_root):
            ctx = build_hook_runtime_context(json.dumps({"session_id": "session-1"}), ensure_client=False)

        self.assertEqual(ctx.client_id, "session-1")
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "clients").exists())


if __name__ == "__main__":
    unittest.main()
