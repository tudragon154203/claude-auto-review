import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.state import (
    append_state,
    ensure_runtime,
    extract_file_paths_from_hook_input,
    get_file_hash,
    get_unreviewed_files,
    load_state,
    mark_files_reviewed,
    normalize_relative_path,
    was_hash_reviewed,
)


class StateTests(unittest.TestCase):
    def temp_project(self):
        return Path(tempfile.mkdtemp(prefix="claude-auto-review-"))

    def test_normalizes_paths_inside_project_root(self):
        project_root = self.temp_project()
        self.assertEqual(normalize_relative_path("src/app.ts", project_root), "src/app.ts")
        self.assertEqual(normalize_relative_path(project_root / "src" / "app.ts", project_root), "src/app.ts")
        self.assertIsNone(normalize_relative_path(project_root.parent / "outside.ts", project_root))

    def test_hashes_existing_file_content(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.parent.mkdir()
        target.write_text("export const value = 1;\n", encoding="utf-8")
        expected = hashlib.sha256(target.read_bytes()).hexdigest()[:8]
        self.assertEqual(get_file_hash("src/app.ts", project_root), expected)

    def test_loads_latest_unreviewed_file_entries(self):
        project_root = self.temp_project()
        ensure_runtime(project_root)
        append_state({"type": "edit", "file": "a.ts", "hash": "11111111", "timestamp": "2026-05-05T01:00:00Z", "reviewed": False}, project_root)
        append_state({"type": "edit", "file": "a.ts", "hash": "22222222", "timestamp": "2026-05-05T02:00:00Z", "reviewed": True, "reviewId": "rev-1"}, project_root)
        append_state({"type": "edit", "file": "b.ts", "hash": "33333333", "timestamp": "2026-05-05T03:00:00Z", "reviewed": False}, project_root)

        self.assertEqual(get_unreviewed_files(load_state(project_root))[0]["file"], "b.ts")

    def test_recognizes_hashes_reviewed_in_earlier_entries(self):
        project_root = self.temp_project()
        ensure_runtime(project_root)
        entry = {"type": "edit", "file": "a.ts", "hash": "11111111", "timestamp": "2026-05-05T01:00:00Z", "reviewed": False}
        mark_files_reviewed([entry], "rev-1", project_root)
        self.assertTrue(was_hash_reviewed(load_state(project_root), "a.ts", "11111111"))

    def test_extracts_paths_from_claude_hook_payload_shapes(self):
        self.assertEqual(extract_file_paths_from_hook_input({"file_path": "a.ts"}), ["a.ts"])
        self.assertEqual(extract_file_paths_from_hook_input({"tool_input": {"file_path": "b.ts"}}), ["b.ts"])
        self.assertEqual(
            extract_file_paths_from_hook_input({"tool_input": {"edits": [{"file_path": "c.ts"}, {"path": "d.ts"}]}}),
            ["c.ts", "d.ts"],
        )

    def test_ignores_corrupt_state_lines(self):
        project_root = self.temp_project()
        ensure_runtime(project_root)
        state_path = project_root / ".claude" / "claude-auto-review" / "state.jsonl"
        state_path.write_text('{"type":"edit","file":"a.ts","hash":"1","reviewed":false}\nnot-json\n', encoding="utf-8")
        self.assertEqual(len(load_state(project_root)), 1)


if __name__ == "__main__":
    unittest.main()
