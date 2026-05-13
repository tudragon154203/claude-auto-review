import unittest

from claude_auto_review.runtime.setup import ensure_client_runtime, ensure_runtime
from claude_auto_review.state.reviews import pending_reviews_for_entries
from claude_auto_review.state.store_read import latest_review_entries_by_id, load_state, was_hash_reviewed
from claude_auto_review.state.store_write import append_review_started, mark_files_reviewed

from tests.unit.state.support import StateTestCase


class TestReviewCycle(StateTestCase, unittest.TestCase):

    def test_recognizes_hashes_reviewed_in_earlier_entries(self):
        project_root = self.temp_project()
        ensure_runtime(project_root)
        entry = {"type": "edit", "file": "a.ts", "hash": "11111111", "timestamp": "2026-05-05T08:00:00+07:00", "reviewed": False}
        mark_files_reviewed([entry], "rev-1", project_root)
        self.assertTrue(was_hash_reviewed(load_state(project_root), "a.ts", "11111111"))

    def test_append_review_started_writes_review_entry(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "test-client")
        entries = [{"file": "a.ts", "hash": "xyz123"}]
        append_review_started(entries, "rev-test", "review.md", project_root, client_id="test-client")
        state = load_state(project_root, "test-client")
        review_entry = next(e for e in state if e.get("type") == "review")
        self.assertEqual(review_entry["reviewId"], "rev-test")
        self.assertEqual(review_entry["clientId"], "test-client")

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

    def test_pending_reviews_for_entries_uses_latest_review_status(self):
        state = [
            {"type": "review", "reviewId": "x", "status": "pending", "timestamp": "2026-05-05T08:00:00+07:00", "files": [{"file": "a.ts", "hash": "1"}]},
            {"type": "review", "reviewId": "x", "status": "completed", "timestamp": "2026-05-05T08:01:00+07:00", "files": [{"file": "a.ts", "hash": "1"}]},
        ]
        entries = [{"file": "a.ts", "hash": "1"}]
        result = pending_reviews_for_entries(state, entries)
        self.assertEqual(result, [])

    def test_latest_review_entries_by_id_prefers_chronological_timestamp(self):
        state = [
            {"type": "review", "reviewId": "x", "status": "pending", "timestamp": "2026-05-05T08:00:00+07:00"},
            {"type": "review", "reviewId": "x", "status": "completed", "timestamp": "2026-05-05T02:30:00+00:00"},
        ]
        latest = latest_review_entries_by_id(state)
        self.assertEqual(latest["x"]["status"], "completed")

    def test_append_review_started_without_client_id_auto_generates(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "auto-id")
        entries = [{"file": "x.ts", "hash": "abc"}]
        append_review_started(entries, "rev-auto", "review.md", project_root, client_id="auto-id")
        state = load_state(project_root, "auto-id")
        self.assertTrue(any(e.get("reviewId") == "rev-auto" for e in state))
