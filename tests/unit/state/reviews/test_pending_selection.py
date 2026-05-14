import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.state.models import EditRecord, ReviewMetadata
from claude_auto_review.state.reviews import (
    best_pending_review_exactly_matching_entries,
    best_pending_review_for_entries,
    entry_file_hash_pairs,
    is_review_clean,
    pending_reviews_exactly_matching_entries,
    pending_review_candidates_for_entries,
    pending_reviews_for_entries,
    review_file_hash_pairs,
)


class TestPendingReviewSelection(unittest.TestCase):
    def test_entry_and_review_hash_pair_helpers_ignore_invalid_items(self):
        entries = [
            {"file": "a.ts", "hash": "111"},
            {"file": "", "hash": "222"},
            {"file": "b.ts"},
            "not-a-dict",
        ]
        review_entry = ReviewMetadata(
            timestamp="2026-05-11T10:00:00+07:00",
            reviewId="r1",
            reviewPath="reviews/r1.md",
            clientId="c",
            files=[{"file": "a.ts", "hash": "111"}, {"file": "b.ts", "hash": "222"}],
        )

        self.assertEqual(entry_file_hash_pairs(entries), {("a.ts", "111")})
        self.assertEqual(review_file_hash_pairs(review_entry), {("a.ts", "111"), ("b.ts", "222")})

    def test_pending_reviews_for_entries_requires_full_coverage_and_sorts_newest_first(self):
        now = datetime.now().astimezone()
        state = [
            ReviewMetadata(
                timestamp=(now - timedelta(hours=2)).isoformat(),
                reviewId="older",
                reviewPath="reviews/older.md",
                clientId="c",
                status="pending",
                files=[{"file": "a.ts", "hash": "1"}, {"file": "b.ts", "hash": "2"}],
            ),
            ReviewMetadata(
                timestamp=(now - timedelta(hours=1)).isoformat(),
                reviewId="newer",
                reviewPath="reviews/newer.md",
                clientId="c",
                status="pending",
                files=[{"file": "a.ts", "hash": "1"}, {"file": "b.ts", "hash": "2"}],
            ),
            ReviewMetadata(
                timestamp=now.isoformat(),
                reviewId="partial",
                reviewPath="reviews/partial.md",
                clientId="c",
                status="pending",
                files=[{"file": "a.ts", "hash": "1"}],
            ),
        ]
        entries = [EditRecord(timestamp=now.isoformat(), file="a.ts", hash="1"), EditRecord(timestamp=now.isoformat(), file="b.ts", hash="2")]

        result = pending_reviews_for_entries(state, entries)

        self.assertEqual([entry.reviewId for entry in result], ["newer", "older"])

    def test_pending_review_candidates_rank_by_overlap_and_skip_expired(self):
        now = datetime.now().astimezone()
        state = [
            ReviewMetadata(
                timestamp=now.isoformat(),
                reviewId="best",
                reviewPath="reviews/best.md",
                clientId="c",
                status="pending",
                files=[{"file": "a.ts", "hash": "1"}, {"file": "b.ts", "hash": "2"}],
            ),
            ReviewMetadata(
                timestamp=(now + timedelta(minutes=1)).isoformat(),
                reviewId="partial",
                reviewPath="reviews/partial.md",
                clientId="c",
                status="pending",
                files=[{"file": "a.ts", "hash": "1"}],
            ),
            ReviewMetadata(
                timestamp=(now - timedelta(hours=3)).isoformat(),
                reviewId="expired",
                reviewPath="reviews/expired.md",
                clientId="c",
                status="pending",
                files=[{"file": "a.ts", "hash": "1"}],
            ),
        ]
        entries = [EditRecord(timestamp=now.isoformat(), file="a.ts", hash="1"), EditRecord(timestamp=now.isoformat(), file="b.ts", hash="2")]

        with patch("claude_auto_review.state.review_matching.log_event") as mock_log:
            candidates = pending_review_candidates_for_entries(
                state,
                entries,
                project_root=Path(tempfile.mkdtemp(prefix="claude-auto-review-reviews-")),
                timeout_hours=1,
            )

        self.assertEqual([item["review"].reviewId for item in candidates], ["best", "partial"])
        mock_log.assert_called_once()

    def test_best_pending_review_for_entries_returns_highest_overlap(self):
        state = [
            ReviewMetadata(
                timestamp="2026-05-11T10:00:00+07:00",
                reviewId="best",
                reviewPath="reviews/best.md",
                clientId="c",
                status="pending",
                files=[{"file": "a.ts", "hash": "1"}, {"file": "b.ts", "hash": "2"}],
            ),
            ReviewMetadata(
                timestamp="2026-05-11T11:00:00+07:00",
                reviewId="runner-up",
                reviewPath="reviews/runner-up.md",
                clientId="c",
                status="pending",
                files=[{"file": "a.ts", "hash": "1"}],
            ),
        ]
        entries = [EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="a.ts", hash="1"), EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="b.ts", hash="2")]

        best = best_pending_review_for_entries(state, entries)

        self.assertEqual(best.reviewId, "best")

    def test_pending_reviews_exactly_matching_entries_rejects_superset_review(self):
        state = [
            ReviewMetadata(
                timestamp="2026-05-11T11:00:00+07:00",
                reviewId="superset",
                reviewPath="reviews/superset.md",
                clientId="c",
                status="pending",
                files=[
                    {"file": "a.ts", "hash": "1"},
                    {"file": "b.ts", "hash": "2"},
                ],
            ),
            ReviewMetadata(
                timestamp="2026-05-11T12:00:00+07:00",
                reviewId="exact",
                reviewPath="reviews/exact.md",
                clientId="c",
                status="pending",
                files=[{"file": "a.ts", "hash": "1"}],
            ),
        ]
        entries = [EditRecord(timestamp="2026-05-11T12:00:00+07:00", file="a.ts", hash="1")]

        matches = pending_reviews_exactly_matching_entries(state, entries)
        best = best_pending_review_exactly_matching_entries(state, entries)

        self.assertEqual([entry.reviewId for entry in matches], ["exact"])
        self.assertEqual(best.reviewId, "exact")

    def test_pending_reviews_ignore_review_ids_completed_later(self):
        state = [
            ReviewMetadata(
                timestamp="2026-05-11T11:00:00+07:00",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="pending",
                files=[{"file": "a.ts", "hash": "1"}],
            ),
            ReviewMetadata(
                timestamp="2026-05-11T11:01:00+07:00",
                reviewId="x",
                reviewPath="reviews/x.md",
                clientId="c",
                status="completed",
                files=[{"file": "a.ts", "hash": "1"}],
            ),
        ]
        entries = [EditRecord(timestamp="2026-05-11T11:00:00+07:00", file="a.ts", hash="1")]

        matches = pending_reviews_for_entries(state, entries)

        self.assertEqual(matches, [])

    def test_is_review_clean_checks_verdict_prefix(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-reviews-"))
        review_path = project_root / "review.md"
        review_path.write_text("## Verdict\nClean - no issues found.\n", encoding="utf-8")
        self.assertTrue(is_review_clean(review_path))

        review_path.write_text("## Verdict\nNeeds more work.\n", encoding="utf-8")
        self.assertFalse(is_review_clean(review_path))
