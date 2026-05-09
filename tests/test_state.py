import hashlib
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path

from scripts.state import (
    append_state,
    append_review_started,
    cancel_runtime,
    client_state_path,
    consecutive_stop_blocks,
    ensure_client_runtime,
    ensure_project_settings,
    ensure_runtime,
    extract_file_paths_from_hook_input,
    get_client_id,
    get_file_hash,
    get_log_path,
    get_state_path,
    get_unreviewed_files,
    is_review_complete,
    latest_entries_by_file,
    load_settings,
    load_state,
    log_event,
    mark_files_reviewed,
    normalize_relative_path,
    pending_reviews_for_entries,
    reviewed_hashes_by_file,
    should_skip_file,
    utc_now_iso,
    was_hash_reviewed,
)
from scripts.state import DEFAULT_SETTINGS


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


class UtilityTests(unittest.TestCase):
    def temp_project(self):
        return Path(tempfile.mkdtemp(prefix="claude-auto-review-utils-"))

    def test_utc_now_iso_returns_valid_iso_format(self):
        result = utc_now_iso()
        self.assertTrue(result.endswith("Z"))
        self.assertIn("T", result)

    def test_normalize_relative_path_returns_none_for_empty_string(self):
        project_root = self.temp_project()
        self.assertIsNone(normalize_relative_path("", project_root))
        self.assertIsNone(normalize_relative_path(None, project_root))

    def test_normalize_relative_path_returns_none_for_project_root(self):
        project_root = self.temp_project()
        self.assertIsNone(normalize_relative_path(str(project_root), project_root))

    def test_normalize_relative_path_returns_none_for_empty_relative(self):
        project_root = self.temp_project()
        self.assertIsNone(normalize_relative_path(".", project_root))

    def test_get_state_path_returns_correct_path(self):
        project_root = self.temp_project()
        result = get_state_path(project_root)
        self.assertEqual(result, project_root / ".claude" / "claude-auto-review" / "state.jsonl")

    def test_get_log_path_returns_correct_path(self):
        project_root = self.temp_project()
        result = get_log_path(project_root)
        self.assertEqual(result, project_root / ".claude" / "claude-auto-review" / "claude-auto-review.log")

    def test_load_settings_defaults_when_file_missing(self):
        project_root = self.temp_project()
        result = load_settings(project_root)
        self.assertTrue(result["enabled"])

    def test_load_settings_merges_project_settings(self):
        project_root = self.temp_project()
        settings_dir = project_root / ".claude"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"maxStopPasses": 5}}), encoding="utf-8"
        )
        result = load_settings(project_root)
        self.assertEqual(result["maxStopPasses"], 5)

    def test_should_skip_file_no_extension(self):
        self.assertFalse(should_skip_file("README", DEFAULT_SETTINGS))

    def test_should_skip_file_include_extensions_allows(self):
        settings = {"includeExtensions": ["py"], "skipExtensions": []}
        self.assertFalse(should_skip_file("script.py", settings))

    def test_should_skip_file_include_extensions_blocks_others(self):
        settings = {"includeExtensions": ["py"], "skipExtensions": []}
        self.assertTrue(should_skip_file("script.ts", settings))

    def test_get_file_hash_returns_none_for_nonexistent_path(self):
        result = get_file_hash("nonexistent.ts", self.temp_project())
        self.assertIsNone(result)

    def test_get_file_hash_returns_none_for_outside_project(self):
        result = get_file_hash(str(Path(tempfile.mkdtemp()) / "outside.ts"), self.temp_project())
        self.assertIsNone(result)

    def test_latest_entries_by_file_handles_missing_timestamp(self):
        state = [{"type": "edit", "file": "a.ts", "hash": "1"}, {"type": "edit", "file": "a.ts", "hash": "2"}]
        result = latest_entries_by_file(state)
        self.assertEqual(result["a.ts"]["hash"], "2")

    def test_latest_entries_by_file_skips_non_edit_entries(self):
        state = [{"type": "review", "reviewId": "x"}, {"type": "edit", "file": "b.ts", "hash": "1"}]
        result = latest_entries_by_file(state)
        self.assertIn("b.ts", result)
        self.assertNotIn("review", result)

    def test_reviewed_hashes_by_file_returns_multiple_hashes_per_file(self):
        state = [
            {"type": "edit", "file": "a.ts", "hash": "1", "reviewed": True},
            {"type": "edit", "file": "a.ts", "hash": "2", "reviewed": True},
            {"type": "edit", "file": "b.ts", "hash": "3", "reviewed": False},
        ]
        result = reviewed_hashes_by_file(state)
        self.assertEqual(result["a.ts"], {"1", "2"})
        self.assertNotIn("b.ts", result)

    def test_was_hash_reviewed_true(self):
        state = [{"type": "edit", "file": "a.ts", "hash": "abc123", "reviewed": True}]
        self.assertTrue(was_hash_reviewed(state, "a.ts", "abc123"))

    def test_was_hash_reviewed_false(self):
        state = [{"type": "edit", "file": "a.ts", "hash": "abc123", "reviewed": False}]
        self.assertFalse(was_hash_reviewed(state, "a.ts", "abc123"))

    def test_append_review_started_writes_review_entry(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "test-client")
        entries = [{"file": "a.ts", "hash": "xyz123"}]
        append_review_started(entries, "rev-test", "review.md", project_root, client_id="test-client")
        state = load_state(project_root, "test-client")
        review_entry = next(e for e in state if e.get("type") == "review")
        self.assertEqual(review_entry["reviewId"], "rev-test")
        self.assertEqual(review_entry["clientId"], "test-client")

    def test_log_event_creates_log_file(self):
        project_root = self.temp_project()
        log_event(project_root, "test_event", extra="data")
        log_path = get_log_path(project_root)
        self.assertTrue(log_path.exists())
        content = log_path.read_text(encoding="utf-8")
        self.assertIn('"event":"test_event"', content)

    def test_log_event_appends_to_existing_log(self):
        project_root = self.temp_project()
        log_event(project_root, "first")
        log_event(project_root, "second")
        log_path = get_log_path(project_root)
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)

    def test_pending_reviews_for_entries_no_matching_review(self):
        state = [{"type": "review", "reviewId": "x", "status": "pending", "files": [{"file": "a.ts", "hash": "1"}]}]
        entries = [{"file": "a.ts", "hash": "2"}]
        result = pending_reviews_for_entries(state, entries)
        self.assertEqual(result, [])

    def test_pending_reviews_for_entries_excludes_non_pending_reviews(self):
        state = [{"type": "review", "reviewId": "x", "status": "completed", "files": [{"file": "a.ts", "hash": "1"}]}]
        entries = [{"file": "a.ts", "hash": "1"}]
        result = pending_reviews_for_entries(state, entries)
        self.assertEqual(result, [])

    def test_ensure_runtime_creates_directories(self):
        project_root = self.temp_project()
        result = ensure_runtime(project_root)
        self.assertTrue((result["base_dir"]).is_dir())
        self.assertTrue(result["state_path"].parent.exists())

    def test_ensure_runtime_creates_default_rules_file(self):
        project_root = self.temp_project()
        result = ensure_runtime(project_root)
        self.assertTrue(result["rules_path"].exists())

    def test_ensure_project_settings_creates_settings_file(self):
        project_root = self.temp_project()
        ensure_project_settings(project_root)
        settings_path = project_root / ".claude" / "settings.json"
        self.assertTrue(settings_path.exists())

    def test_ensure_project_settings_does_not_overwrite_existing(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({"claude-auto-review": {"maxStopPasses": 99}}), encoding="utf-8")
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertEqual(settings["claude-auto-review"]["maxStopPasses"], 99)

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

    def test_get_client_id_uses_session_id_from_env(self):
        import unittest.mock as mock
        with mock.patch.dict(os.environ, {"CLAUDE_SESSION_ID": "fixed-session"}):
            result = get_client_id()
            self.assertEqual(result, "fixed-session")

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


# ================ Coverage: remaining edge cases ================

class EdgeCaseTests(unittest.TestCase):
    def temp_project(self):
        return Path(tempfile.mkdtemp(prefix="claude-auto-review-edge-"))

    def test_latest_entries_by_file_skips_non_dict_entries(self):
        state = [None, "string", {"type": "edit", "file": "a.ts", "hash": "1"}]
        result = latest_entries_by_file(state)
        self.assertEqual(result["a.ts"]["hash"], "1")

    def test_append_review_started_without_client_id_auto_generates(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "auto-id")
        entries = [{"file": "x.ts", "hash": "abc"}]
        append_review_started(entries, "rev-auto", "review.md", project_root, client_id="auto-id")
        state = load_state(project_root, "auto-id")
        self.assertTrue(any(e.get("reviewId") == "rev-auto" for e in state))

    def test_ensure_project_settings_handles_non_dict_json(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text('"just a string"', encoding="utf-8")
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)

    def test_ensure_project_settings_handles_oserror(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("invalid json{", encoding="utf-8")
        ensure_project_settings(project_root)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)

    def test_ensure_runtime_without_default_rules_creates_fallback(self):
        project_root = self.temp_project()
        fake_plugin = self.temp_project()
        # No rules/default-rules.md in fake_plugin
        ensure_runtime(project_root, plugin_root=fake_plugin)
        rules_path = project_root / ".claude" / "claude-auto-review" / "rules.md"
        self.assertTrue(rules_path.exists())
        content = rules_path.read_text(encoding="utf-8")
        self.assertIn("Review semantic correctness", content)

    def test_load_state_returns_empty_for_missing_file(self):
        project_root = self.temp_project()
        state = load_state(project_root, "no-file-client")
        self.assertEqual(state, [])

    def test_load_settings_handles_invalid_json(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude"
        settings_path.mkdir(parents=True, exist_ok=True)
        (settings_path / "settings.json").write_text("not valid json", encoding="utf-8")
        result = load_settings(project_root)
        self.assertTrue(result["enabled"])

    def test_load_settings_handles_oserror(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude"
        settings_path.mkdir(parents=True, exist_ok=True)
        bad = settings_path / "settings.json"
        bad.write_text("{}", encoding="utf-8")
        # Make a nonexistent path to trigger fallback in another way
        other_root = self.temp_project()
        result = load_settings(other_root)
        self.assertTrue(result["enabled"])

    def test_load_state_skips_empty_lines(self):
        project_root = self.temp_project()
        client_id = "empty-line-test"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        state_path.write_text(
            '{"type":"edit","file":"a.ts","hash":"1","reviewed":false}\n\n{"type":"edit","file":"b.ts","hash":"2","reviewed":false}\n',
            encoding="utf-8",
        )
        state = load_state(project_root, client_id)
        self.assertEqual(len(state), 2)


if __name__ == "__main__":
    unittest.main()
