import unittest

from claude_auto_review.runtime.setup import ensure_client_runtime, ensure_runtime
from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.records.file import ReviewFileRecord
from claude_auto_review.state.records.review import ReviewMetadata
from claude_auto_review.state.reviews.matching import pending_reviews_for_entries
from claude_auto_review.state.store.queries import latest_review_entries_by_id, was_hash_reviewed
from claude_auto_review.state.store.read import load_state
from claude_auto_review.state.store.write import append_review_started, mark_files_reviewed
from tests.unit.state.support import StateTestCase


class TestReviewCycle(StateTestCase, unittest.TestCase):
    def test_recognizes_hashes_reviewed_in_earlier_entries(self):
        project_root = self.temp_project()
        ensure_runtime(project_root)
        entry = EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="11111111", reviewed=False)
        mark_files_reviewed([entry], "rev-1", project_root)
        self.assertTrue(was_hash_reviewed(load_state(project_root), "a.ts", "11111111"))

    def test_append_review_started_writes_review_entry(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "test-client")
        entries = [EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="xyz123")]
        append_review_started(entries, "rev-test", "review.md", project_root, client_id="test-client")
        state = load_state(project_root, "test-client")
        review_entry = next(e for e in state if isinstance(e, ReviewMetadata))
        self.assertEqual(review_entry.reviewId, "rev-test")
        self.assertEqual(review_entry.clientId, "test-client")

    def test_pending_reviews_for_entries_no_matching_review(self):
        state = [
            ReviewMetadata(
                timestamp="2026-05-05T08:00:00+07:00",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="pending",
                files=[ReviewFileRecord(file="a.ts", hash="1")],
            )
        ]
        entries = [EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="2")]
        result = pending_reviews_for_entries(state, entries)
        self.assertEqual(result, [])

    def test_pending_reviews_for_entries_excludes_non_pending_reviews(self):
        state = [
            ReviewMetadata(
                timestamp="2026-05-05T08:00:00+07:00",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="completed",
                files=[ReviewFileRecord(file="a.ts", hash="1")],
            )
        ]
        entries = [EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="1")]
        result = pending_reviews_for_entries(state, entries)
        self.assertEqual(result, [])

    def test_pending_reviews_for_entries_uses_latest_review_status(self):
        state = [
            ReviewMetadata(
                timestamp="2026-05-05T08:00:00+07:00",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="pending",
                files=[ReviewFileRecord(file="a.ts", hash="1")],
            ),
            ReviewMetadata(
                timestamp="2026-05-05T08:01:00+07:00",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="completed",
                files=[ReviewFileRecord(file="a.ts", hash="1")],
            ),
        ]
        entries = [EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="1")]
        result = pending_reviews_for_entries(state, entries)
        self.assertEqual(result, [])

    def test_latest_review_entries_by_id_prefers_chronological_timestamp(self):
        state = [
            ReviewMetadata(
                timestamp="2026-05-05T08:00:00+07:00",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="pending",
                files=[],
            ),
            ReviewMetadata(
                timestamp="2026-05-05T02:30:00+00:00",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="completed",
                files=[],
            ),
        ]
        latest = latest_review_entries_by_id(state)
        self.assertEqual(latest["x"].status, "completed")

    def test_latest_review_entries_by_id_keeps_valid_timestamp_over_later_invalid_timestamp(self):
        state = [
            ReviewMetadata(
                timestamp="2026-05-05T08:00:00+07:00",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="pending",
                files=[],
            ),
            ReviewMetadata(
                timestamp="not-a-timestamp",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="completed",
                files=[],
            ),
        ]
        latest = latest_review_entries_by_id(state)
        self.assertEqual(latest["x"].status, "pending")

    def test_latest_review_entries_by_id_prefers_valid_timestamp_over_earlier_invalid_timestamp(self):
        state = [
            ReviewMetadata(
                timestamp="not-a-timestamp",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="pending",
                files=[],
            ),
            ReviewMetadata(
                timestamp="2026-05-05T08:00:00+07:00",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="completed",
                files=[],
            ),
        ]
        latest = latest_review_entries_by_id(state)
        self.assertEqual(latest["x"].status, "completed")

    def test_latest_review_entries_by_id_prefers_later_invalid_timestamp_over_earlier_invalid_timestamp(self):
        state = [
            ReviewMetadata(
                timestamp="zzz-not-iso",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="pending",
                files=[],
            ),
            ReviewMetadata(
                timestamp="aaa-not-iso",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="completed",
                files=[],
            ),
        ]
        latest = latest_review_entries_by_id(state)
        self.assertEqual(latest["x"].status, "completed")

    def test_append_review_started_without_client_id_auto_generates(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "auto-id")
        entries = [EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="x.ts", hash="abc")]
        append_review_started(entries, "rev-auto", "review.md", project_root, client_id="auto-id")
        state = load_state(project_root, "auto-id")
        self.assertTrue(any(isinstance(e, ReviewMetadata) and e.reviewId == "rev-auto" for e in state))
