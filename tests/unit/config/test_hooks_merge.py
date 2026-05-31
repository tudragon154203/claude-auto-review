import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.config.hooks_merge import (
    load_hooks_document,
    merge_hook_buckets,
    merge_unique_hook_list,
)


class TestLoadHooksDocument(unittest.TestCase):
    def test_valid_json_returns_parsed_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "hooks.json"
            p.write_text('{"hooks": {"PreToolUse": [{"command": "echo"}]}}', encoding="utf-8")
            result = load_hooks_document(p)
            self.assertEqual(result, {"hooks": {"PreToolUse": [{"command": "echo"}]}})

    def test_empty_file_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "hooks.json"
            p.write_text("", encoding="utf-8")
            result = load_hooks_document(p)
            self.assertEqual(result, {})

    def test_whitespace_only_file_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "hooks.json"
            p.write_text("  \n  ", encoding="utf-8")
            result = load_hooks_document(p)
            self.assertEqual(result, {})

    def test_invalid_json_returns_empty_hooks(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "hooks.json"
            p.write_text("{bad json", encoding="utf-8")
            result = load_hooks_document(p)
            self.assertEqual(result, {"hooks": {}})

    def test_non_dict_json_returns_empty_hooks(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "hooks.json"
            p.write_text("[1, 2, 3]", encoding="utf-8")
            result = load_hooks_document(p)
            self.assertEqual(result, {"hooks": {}})

    def test_missing_file_returns_empty_hooks(self):
        result = load_hooks_document(Path("/nonexistent/hooks.json"))
        self.assertEqual(result, {"hooks": {}})


class TestMergeUniqueHookList(unittest.TestCase):
    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", return_value=False)
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="")
    def test_both_empty(self, _mock_script, _mock_plugin):
        self.assertEqual(merge_unique_hook_list([], []), [])

    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", return_value=False)
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="")
    def test_existing_only(self, _mock_script, _mock_plugin):
        items = [{"command": "echo hello"}]
        self.assertEqual(merge_unique_hook_list(items, []), items)

    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", return_value=False)
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="")
    def test_desired_only(self, _mock_script, _mock_plugin):
        items = [{"command": "echo hello"}]
        self.assertEqual(merge_unique_hook_list([], items), items)

    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", return_value=False)
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="")
    def test_deduplicates_identical_entries(self, _mock_script, _mock_plugin):
        existing = [{"command": "echo hello"}]
        desired = [{"command": "echo hello"}]
        result = merge_unique_hook_list(existing, desired)
        self.assertEqual(len(result), 1)

    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", return_value=False)
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="")
    def test_merges_distinct_entries(self, _mock_script, _mock_plugin):
        existing = [{"command": "echo a"}]
        desired = [{"command": "echo b"}]
        result = merge_unique_hook_list(existing, desired)
        self.assertEqual(len(result), 2)

    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", side_effect=[True, True])
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="script.sh")
    def test_plugin_entry_replaces_same_plugin(self, _mock_script, _mock_plugin):
        existing = [{"command": "echo a"}]
        desired = [{"command": "echo b"}]
        result = merge_unique_hook_list(existing, desired)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {"command": "echo b"})

    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", side_effect=[True, False])
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="script.sh")
    def test_plain_entry_does_not_replace_plugin(self, _mock_script, _mock_plugin):
        existing = [{"command": "echo a"}]
        desired = [{"command": "echo b"}]
        result = merge_unique_hook_list(existing, desired)
        self.assertEqual(len(result), 2)

    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", return_value=False)
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="")
    def test_non_list_input_treated_as_empty(self, _mock_script, _mock_plugin):
        result = merge_unique_hook_list(None, [{"command": "echo"}])
        self.assertEqual(len(result), 1)
        result2 = merge_unique_hook_list([{"command": "echo"}], None)
        self.assertEqual(len(result2), 1)

    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", return_value=False)
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="")
    def test_existing_duplicates_deduped(self, _mock_script, _mock_plugin):
        existing = [{"command": "echo"}, {"command": "echo"}]
        result = merge_unique_hook_list(existing, [])
        self.assertEqual(len(result), 1)


class TestMergeHookBuckets(unittest.TestCase):
    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", return_value=False)
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="")
    def test_both_empty(self, _mock_script, _mock_plugin):
        self.assertEqual(merge_hook_buckets({}, {}), {})

    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", return_value=False)
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="")
    def test_merges_new_bucket(self, _mock_script, _mock_plugin):
        existing = {"PreToolUse": [{"command": "a"}]}
        desired = {"PostToolUse": [{"command": "b"}]}
        result = merge_hook_buckets(existing, desired)
        self.assertIn("PreToolUse", result)
        self.assertIn("PostToolUse", result)

    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", return_value=False)
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="")
    def test_merges_same_bucket_entries(self, _mock_script, _mock_plugin):
        existing = {"PreToolUse": [{"command": "a"}]}
        desired = {"PreToolUse": [{"command": "b"}]}
        result = merge_hook_buckets(existing, desired)
        self.assertEqual(len(result["PreToolUse"]), 2)

    @patch("claude_auto_review.config.hooks_merge.is_plugin_hook", return_value=False)
    @patch("claude_auto_review.config.hooks_merge.plugin_script_name_from_hook", return_value="")
    def test_non_dict_input_treated_as_empty(self, _mock_script, _mock_plugin):
        result = merge_hook_buckets(None, {"PreToolUse": [{"command": "a"}]})
        self.assertIn("PreToolUse", result)


if __name__ == "__main__":
    unittest.main()
