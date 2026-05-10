"""Integration tests exercising cross-function state interactions.

These tests verify that multiple state functions behave consistently
when combined — e.g. append_state + get_unreviewed_files + was_hash_reviewed,
or append_review_started + pending_reviews_for_entries + mark_files_reviewed.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support import TempProjectMixin

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.paths import (
    client_reviews_dir,
    client_run_dir,
    get_client_id,
    get_client_runtime_dir,
    get_log_path,
    utc_now_iso,
)
from claude_auto_review.reviews import pending_reviews_for_entries
from claude_auto_review.state import (
    append_review_started,
    append_state,
    cancel_runtime,
    consecutive_stop_blocks,
    ensure_client_runtime,
    ensure_project_settings,
    ensure_runtime,
    get_unreviewed_files,
    load_settings,
    load_state,
    log_event,
    mark_files_reviewed,
    was_hash_reviewed,
)


class IntegrationTests(TempProjectMixin, unittest.TestCase):
    """Tests combining multiple state functions."""

    def test_ensure_runtime_creates_complete_structure(self):
        project_root = self.temp_project()

        result = ensure_runtime(project_root, REPO_ROOT)

        self.assertTrue(result["base_dir"].exists())
        self.assertTrue(result["rules_path"].exists())
        self.assertTrue(result["state_path"].parent.exists())
        self.assertTrue(result["log_path"].parent.exists())
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "state.jsonl").exists())

    def test_log_event_writes_formatted_entries(self):
        project_root = self.temp_project()

        log_event(project_root, "test_event", foo="bar", count=42)
        log_path = get_log_path(project_root)

        self.assertTrue(log_path.exists())
        content = log_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        entry = json.loads(lines[-1])
        self.assertEqual(entry["event"], "test_event")
        self.assertEqual(entry["foo"], "bar")
        self.assertEqual(entry["count"], 42)
        self.assertIn("timestamp", entry)

    def test_review_started_to_pending_detection_cycle(self):
        """append_review_started → pending_reviews_for_entries finds the review."""
        project_root = self.temp_project()
        client_id = "review-cycle"
        ensure_client_runtime(project_root, client_id)

        entry = {
            "type": "edit",
            "file": "src/main.ts",
            "hash": "abc123",
            "timestamp": utc_now_iso(),
            "reviewed": False,
        }
        append_state(entry, project_root, client_id=client_id)

        state = load_state(project_root, client_id)
        entries = [e for e in state if e.get("type") == "edit"]
        self.assertEqual(len(entries), 1)

        append_review_started(
            entries, "rev-001", "reviews/rev-001.md",
            project_root, client_id=client_id,
        )

        state = load_state(project_root, client_id)
        unreviewed = get_unreviewed_files(state)
        self.assertEqual(len(unreviewed), 1)

        reviews = pending_reviews_for_entries(state, entries)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["reviewId"], "rev-001")

    def test_mark_files_reviewed_cross_function_consistency(self):
        """mark_files_reviewed updates get_unreviewed_files and was_hash_reviewed."""
        project_root = self.temp_project()
        client_id = "mark-consistency"
        ensure_client_runtime(project_root, client_id)

        entries = []
        for file, h in [("a.ts", "h1"), ("b.ts", "h2"), ("c.ts", "h3")]:
            entry = {
                "type": "edit",
                "file": file,
                "hash": h,
                "timestamp": utc_now_iso(),
                "reviewed": False,
            }
            entries.append(entry)
            append_state(entry, project_root, client_id=client_id)

        state = load_state(project_root, client_id)
        self.assertEqual(len(get_unreviewed_files(state)), 3)

        mark_files_reviewed(
            [{"file": "b.ts", "hash": "h2"}], "rev-001", project_root,
            client_id=client_id,
        )

        state = load_state(project_root, client_id)
        self.assertTrue(was_hash_reviewed(state, "b.ts", "h2"))
        self.assertFalse(was_hash_reviewed(state, "a.ts", "h1"))
        self.assertFalse(was_hash_reviewed(state, "c.ts", "h3"))

        unreviewed = get_unreviewed_files(state)
        self.assertEqual(len(unreviewed), 2)
        unreviewed_files = {e["file"] for e in unreviewed}
        self.assertIn("a.ts", unreviewed_files)
        self.assertIn("c.ts", unreviewed_files)

    def test_ensure_project_settings_preserves_user_values(self):
        project_root = self.temp_project()

        ensure_project_settings(project_root)
        settings = load_settings(project_root)
        self.assertTrue(settings["enabled"])

        settings_file = project_root / ".claude" / "settings.json"
        settings_file.write_text(
            json.dumps({
                "claude-auto-review": {
                    "enabled": False,
                    "customKey": "value",
                },
            }),
            encoding="utf-8",
        )

        ensure_project_settings(project_root)
        settings = load_settings(project_root)
        self.assertFalse(settings["enabled"])
        self.assertEqual(settings["customKey"], "value")

    def test_cancel_runtime_removes_client_artifacts(self):
        project_root = self.temp_project()
        client_id = "cleanup-test"
        ensure_client_runtime(project_root, client_id)

        append_state({
            "type": "edit",
            "file": "x.ts",
            "hash": "deadbeef",
            "timestamp": utc_now_iso(),
            "reviewed": False,
        }, project_root, client_id=client_id)

        client_dir = get_client_runtime_dir(project_root, client_id)
        self.assertTrue(client_dir.exists())

        cancel_runtime(project_root, client_id=client_id)

        self.assertFalse(client_dir.exists())

    def test_multiple_clients_state_isolation(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "alice")
        ensure_client_runtime(project_root, "bob")

        append_state({
            "type": "edit",
            "file": "alice.txt",
            "hash": "1111",
            "timestamp": utc_now_iso(),
            "reviewed": False,
        }, project_root, client_id="alice")

        append_state({
            "type": "edit",
            "file": "bob.txt",
            "hash": "2222",
            "timestamp": utc_now_iso(),
            "reviewed": False,
        }, project_root, client_id="bob")

        state_a = load_state(project_root, "alice")
        state_b = load_state(project_root, "bob")

        files_a = {e["file"] for e in state_a if e.get("type") == "edit"}
        files_b = {e["file"] for e in state_b if e.get("type") == "edit"}

        self.assertIn("alice.txt", files_a)
        self.assertNotIn("bob.txt", files_a)
        self.assertIn("bob.txt", files_b)
        self.assertNotIn("alice.txt", files_b)

    def test_consecutive_stop_blocks_with_reviewed_edit_reset(self):
        """Verify consecutive_stop_blocks resets after marked-reviewed entry."""
        project_root = self.temp_project()
        client_id = "stop-blocks-reset"
        ensure_client_runtime(project_root, client_id)

        ts = utc_now_iso()
        e1 = {"type": "edit", "file": "a.ts", "hash": "h1",
              "timestamp": ts, "reviewed": False}
        append_state(e1, project_root, client_id=client_id)

        for _ in range(3):
            append_state({"type": "stop_blocked", "reason": "x",
                          "timestamp": utc_now_iso()},
                         project_root, client_id=client_id)

        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 3)

        e2 = {"type": "edit", "file": "a.ts", "hash": "h1",
              "timestamp": utc_now_iso(), "reviewed": True, "reviewId": "r1"}
        append_state(e2, project_root, client_id=client_id)

        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 0)

    def test_append_review_started_marks_review_state_consistently(self):
        """Results from append_review_started are immediately observable."""
        project_root = self.temp_project()
        client_id = "review-state"
        ensure_client_runtime(project_root, client_id)

        entries = [
            {"file": "f1.ts", "hash": "a"},
            {"file": "f2.ts", "hash": "b"},
        ]
        for e in entries:
            append_state({
                "type": "edit",
                "file": e["file"],
                "hash": e["hash"],
                "timestamp": utc_now_iso(),
                "reviewed": False,
            }, project_root, client_id=client_id)

        state_before = load_state(project_root, client_id)
        pending = pending_reviews_for_entries(state_before, state_before)
        self.assertEqual(len(pending), 0)

        append_review_started(entries, "rev-01", "reviews/rev-01.md",
                              project_root, client_id=client_id)

        state_after = load_state(project_root, client_id)
        edit_entries = [e for e in state_after if e.get("type") == "edit"]
        pending = pending_reviews_for_entries(state_after, edit_entries)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["reviewId"], "rev-01")

    def test_ensure_runtime_is_idempotent(self):
        project_root = self.temp_project()
        result1 = ensure_runtime(project_root, REPO_ROOT)
        result2 = ensure_runtime(project_root, REPO_ROOT)
        self.assertEqual(result1["rules_path"].read_text(encoding="utf-8"),
                         result2["rules_path"].read_text(encoding="utf-8"))

    def test_log_event_error_silent(self):
        """log_event should not raise when directory doesn't exist (OSError caught)."""
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-log-"))
        nonexistent = project_root / "nope" / "deep"
        log_event(nonexistent, "should_not_crash")
        self.assertTrue(True)  # reached without exception


if __name__ == "__main__":
    unittest.main()

