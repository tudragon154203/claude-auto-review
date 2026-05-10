import unittest

from claude_auto_review.state.store_read import extract_file_paths_from_hook_input

from tests.unit.state.support import StateTestCase


class TestHookInputExtraction(StateTestCase, unittest.TestCase):

    def test_extracts_paths_from_claude_hook_payload_shapes(self):
        self.assertEqual(extract_file_paths_from_hook_input({"file_path": "a.ts"}), ["a.ts"])
        self.assertEqual(extract_file_paths_from_hook_input({"tool_input": {"file_path": "b.ts"}}), ["b.ts"])
        self.assertEqual(
            extract_file_paths_from_hook_input({"tool_input": {"edits": [{"file_path": "c.ts"}, {"path": "d.ts"}]}}),
            ["c.ts", "d.ts"],
        )

    def test_extracts_unique_paths_only(self):
        payload = {"tool_input": {"file_path": "a.ts", "edits": [{"file_path": "a.ts"}, {"file_path": "b.ts"}]}}
        self.assertEqual(extract_file_paths_from_hook_input(payload), ["a.ts", "b.ts"])

    def test_extract_file_paths_from_hook_input_uses_payload_directly_if_no_tool_input(self):
        payload = {"file_path": "direct.ts"}
        result = extract_file_paths_from_hook_input(payload)
        self.assertEqual(result, ["direct.ts"])

    def test_extract_file_paths_from_hook_input_handles_empty_tool_input(self):
        payload = {"tool_input": {}}
        result = extract_file_paths_from_hook_input(payload)
        self.assertEqual(result, [])

    def test_extract_file_paths_from_hook_input_ignores_null_edit_entries(self):
        payload = {"tool_input": {"edits": [{"file_path": "a.ts"}, None, {"file_path": "b.ts"}]}}
        result = extract_file_paths_from_hook_input(payload)
        self.assertEqual(result, ["a.ts", "b.ts"])

    def test_extract_file_paths_from_hook_input_ignores_null_values(self):
        payload = {"tool_input": {"edits": [{"file_path": None}, {"file_path": "valid.ts"}]}}
        result = extract_file_paths_from_hook_input(payload)
        self.assertEqual(result, ["valid.ts"])


