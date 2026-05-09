import unittest

from scripts.state import append_review_started, ensure_client_runtime, ensure_runtime, load_state, mark_files_reviewed, pending_reviews_for_entries, was_hash_reviewed

from tests.state.support import StateTestCase


class TestReviewCycle(StateTestCase, unittest.TestCase):

    def test_recognizes_hashes_reviewed_in_earlier_entries(self):
        project_root = self.temp_project()
        ensure_runtime(project_root)
        entry = {"type": "edit", "file": "a.ts", "hash": "11111111", "timestamp": "2026-05-05T01:00:00Z", "reviewed": False}
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

    def test_append_review_started_without_client_id_auto_generates(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "auto-id")
        entries = [{"file": "x.ts", "hash": "abc"}]
        append_review_started(entries, "rev-auto", "review.md", project_root, client_id="auto-id")
        state = load_state(project_root, "auto-id")
        self.assertTrue(any(e.get("reviewId") == "rev-auto" for e in state))

