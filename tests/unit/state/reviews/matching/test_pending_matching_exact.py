import unittest

from claude_auto_review.state.edit_record import EditRecord
from claude_auto_review.state.file_record import ReviewFileRecord
from claude_auto_review.state.review_records import ReviewMetadata
from claude_auto_review.state.reviews.matching import (
    best_pending_review_exactly_matching_entries,
    pending_reviews_exactly_matching_entries,
)


class TestPendingMatchingExact(unittest.TestCase):
    def test_pending_reviews_exactly_matching_entries_requires_exact_file_hash_set(self):
        import datetime
        from datetime import timedelta, timezone

        now = datetime.datetime.now(timezone.utc)
        state = [
            ReviewMetadata(
                timestamp=(now - timedelta(minutes=5)).isoformat(),
                reviewId="exact-old",
                reviewPath="reviews/exact-old.md",
                clientId="c",
                status="pending",
                files=[
                    ReviewFileRecord(file="a.ts", hash="111"),
                    ReviewFileRecord(file="b.ts", hash="222"),
                ],
            ),
            ReviewMetadata(
                timestamp=now.isoformat(),
                reviewId="exact-new",
                reviewPath="reviews/exact-new.md",
                clientId="c",
                status="pending",
                files=[
                    ReviewFileRecord(file="a.ts", hash="111"),
                    ReviewFileRecord(file="b.ts", hash="222"),
                ],
            ),
            ReviewMetadata(
                timestamp=now.isoformat(),
                reviewId="superset",
                reviewPath="reviews/superset.md",
                clientId="c",
                status="pending",
                files=[
                    ReviewFileRecord(file="a.ts", hash="111"),
                    ReviewFileRecord(file="b.ts", hash="222"),
                    ReviewFileRecord(file="c.ts", hash="333"),
                ],
            ),
        ]
        entries = [
            EditRecord(timestamp=now.isoformat(), file="a.ts", hash="111"),
            EditRecord(timestamp=now.isoformat(), file="b.ts", hash="222"),
        ]

        matches = pending_reviews_exactly_matching_entries(state, entries)
        best = best_pending_review_exactly_matching_entries(state, entries)

        self.assertEqual([entry.reviewId for entry in matches], ["exact-new", "exact-old"])
        self.assertIsNotNone(best)
        self.assertEqual(best.reviewId, "exact-new")


if __name__ == "__main__":
    unittest.main()
