import tempfile
import unittest
from pathlib import Path

from claude_auto_review.runtime.setup import _load_hooks_document, _merge_hooks, _merge_unique_list


class TestSetupHelpers(unittest.TestCase):
    def test_load_hooks_document_returns_empty_for_invalid_json(self):
        plugin_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-hooks-"))
        hooks_path = plugin_root / "hooks"
        hooks_path.mkdir(parents=True, exist_ok=True)
        (hooks_path / "hooks.json").write_text("{not json", encoding="utf-8")

        self.assertEqual(_load_hooks_document(plugin_root), {"hooks": {}})

    def test_merge_unique_list_preserves_order_and_deduplicates_entries(self):
        existing = [{"type": "command", "value": "one"}, "plain"]
        desired = [{"type": "command", "value": "one"}, {"type": "command", "value": "two"}, "plain", "new"]

        merged = _merge_unique_list(existing, desired)

        self.assertEqual(
            merged,
            [{"type": "command", "value": "one"}, "plain", {"type": "command", "value": "two"}, "new"],
        )

    def test_merge_hooks_merges_each_hook_bucket(self):
        existing = {"post_tool_use": [{"type": "command", "value": "existing"}]}
        desired = {
            "post_tool_use": [{"type": "command", "value": "existing"}, {"type": "command", "value": "new"}],
            "stop": [{"type": "command", "value": "stop"}],
        }

        merged = _merge_hooks(existing, desired)

        self.assertEqual(
            merged,
            {
                "post_tool_use": [{"type": "command", "value": "existing"}, {"type": "command", "value": "new"}],
                "stop": [{"type": "command", "value": "stop"}],
            },
        )
