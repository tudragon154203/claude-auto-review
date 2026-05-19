import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


class TestHookConfigsStatic(unittest.TestCase):
    def test_hook_configs_match_delete_and_remove_tools(self):
        plugin_config = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        hooks_config = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))

        plugin_matcher = plugin_config["hooks"]["PostToolUse"][0]["matcher"]
        hooks_matcher = hooks_config["hooks"]["PostToolUse"][0]["matcher"]
        for tool_name in ("Write", "Edit", "MultiEdit", "Delete", "Remove"):
            self.assertIn(tool_name, plugin_matcher)
            self.assertIn(tool_name, hooks_matcher)


if __name__ == "__main__":
    unittest.main()
