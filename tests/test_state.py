import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.state import (
    append_state,
    client_state_path,
    consecutive_stop_blocks,
    ensure_client_runtime,
    ensure_runtime,
    extract_file_paths_from_hook_input,
    get_file_hash,
    get_unreviewed_files,
    is_review_complete,
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

    def test_normalizes_file_url_paths_inside_project_root(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        self.assertEqual(normalize_relative_path(f"file://{target}", project_root), "src/app.ts")

    def test_rejects_relative_path_traversal_outside_project_root(self):
        project_root = self.temp_project()
        self.assertIsNone(normalize_relative_path("../outside.ts", project_root))

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

    def test_extracts_unique_paths_only(self):
        payload = {"tool_input": {"file_path": "a.ts", "edits": [{"file_path": "a.ts"}, {"file_path": "b.ts"}]}}
        self.assertEqual(extract_file_paths_from_hook_input(payload), ["a.ts", "b.ts"])

    def test_ignores_corrupt_state_lines(self):
        project_root = self.temp_project()
        client_id = "test-corrupt"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        state_path.write_text('{"type":"edit","file":"a.ts","hash":"1","reviewed":false}\nnot-json\n', encoding="utf-8")
        self.assertEqual(len(load_state(project_root, client_id)), 1)


class IsReviewCompleteTests(unittest.TestCase):
    def temp_project(self):
        return Path(tempfile.mkdtemp(prefix="claude-auto-review-isreview-"))

    def test_returns_false_when_review_file_missing(self):
        project_root = self.temp_project()
        missing = project_root / "no-such-review.md"
        self.assertFalse(is_review_complete(missing))

    def test_returns_false_when_verdict_heading_missing(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("# Files\n\nSome notes\n", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_is_empty(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\n", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_equals_pending_uppercase(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nPending", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_equals_pending_with_period(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nPending.", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_has_pending_word_in_context(self):
        # Substring checks would incorrectly fail; confirm we pass
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nAll issues addressed. No pending items.", encoding="utf-8")
        self.assertTrue(is_review_complete(path), "Should pass when 'pending' is just a word, not the literal placeholder")

    def test_returns_true_when_verdict_is_clean_message(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nClean - no issues found.", encoding="utf-8")
        self.assertTrue(is_review_complete(path))

    def test_returns_true_when_verdict_is_a_fixed_message(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nAll fixes applied.", encoding="utf-8")
        self.assertTrue(is_review_complete(path))

    def test_is_case_insensitive(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nPENDING", encoding="utf-8")
        self.assertFalse(is_review_complete(path))
        path.write_text("## Verdict\nPEnDInG.", encoding="utf-8")
        self.assertFalse(is_review_complete(path))


class ConsecutiveStopBlocksTests(unittest.TestCase):
    def temp_project(self):
        return Path(tempfile.mkdtemp(prefix="claude-auto-review-blocks-"))

    def ensure_client(self, project_root, client_id):
        ensure_client_runtime(project_root, client_id)
        return project_root

    def test_returns_zero_for_empty_state(self):
        project_root = self.temp_project()
        client_id = "client-zero"
        self.ensure_client(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(load_state(project_root, client_id)), 0)

    def test_counts_blocks_since_last_reviewed_edit(self):
        project_root = self.temp_project()
        client_id = "client-batch"
        self.ensure_client(project_root, client_id)
        append_state({"type": "edit", "file": "a.ts", "hash": "1", "reviewed": False}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "no_pending_review"}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        append_state({"type": "edit", "file": "b.ts", "hash": "2", "reviewed": False}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "no_pending_review"}, project_root, client_id=client_id)
        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 4)

    def test_ignores_blocks_before_latest_review_completion(self):
        project_root = self.temp_project()
        client_id = "client-reset"
        self.ensure_client(project_root, client_id)
        append_state({"type": "edit", "file": "x.ts", "hash": "x", "reviewed": False}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        append_state({"type": "edit", "file": "x.ts", "hash": "x", "reviewed": True, "reviewId": "rev-1"}, project_root, client_id=client_id)
        append_state({"type": "edit", "file": "y.ts", "hash": "y", "reviewed": False}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "no_pending_review"}, project_root, client_id=client_id)
        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 1)

    def test_ignores_non_dict_entries(self):
        project_root = self.temp_project()
        client_id = "client-ignore"
        self.ensure_client(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        # Manually corrupt the state file to include non-dict entries
        with state_path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write("just a string\nnull\n")
        # Add valid block entries on top
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 2)


if __name__ == "__main__":
    unittest.main()
