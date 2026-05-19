import unittest

from claude_auto_review.state.models import EditRecord, ReviewFileRecord, ReviewMetadata
from claude_auto_review.state.reviews.matching import (
    best_pending_review_covering_entries,
    best_pending_review_exactly_matching_entries,
    best_pending_review_for_entries,
    entry_file_hash_pairs,
    pending_reviews_exactly_matching_entries,
    pending_reviews_for_entries,
    review_file_hash_pairs,
)


class TestPendingMatching(unittest.TestCase):

    def test_entry_and_review_hash_pair_helpers_ignore_invalid_items(self):
        entries = [
            ReviewFileRecord(file="a.ts", hash="111"),
            ReviewFileRecord(file="", hash="222"),
            ReviewFileRecord(file="b.ts", hash=""),
        ]
        review_entry = ReviewMetadata(
            timestamp="2026-05-11T10:00:00+07:00",
            reviewId="r1",
            reviewPath="reviews/r1.md",
            clientId="c",
            files=[
                ReviewFileRecord(file="a.ts", hash="111"),
                ReviewFileRecord(file="", hash="222"),
                ReviewFileRecord(file="b.ts", hash=""),
            ],
        )

        self.assertEqual(entry_file_hash_pairs(entries), {("a.ts", "111")})
        self.assertEqual(review_file_hash_pairs(review_entry), {("a.ts", "111")})

    def test_pending_reviews_for_entries_requires_full_coverage_and_sorts_newest_first(self):
        import datetime
        from datetime import timedelta, timezone
        now = datetime.datetime.now(timezone.utc)
        state = [
            ReviewMetadata(
                timestamp=(now - timedelta(hours=2)).isoformat(),
                reviewId="older",
                reviewPath="reviews/older.md",
                clientId="c",
                status="pending",
                files=[
                    ReviewFileRecord(file="a.ts", hash="111"),
                    ReviewFileRecord(file="b.ts", hash="222"),
                ],
            ),
            ReviewMetadata(
                timestamp=now.isoformat(),
                reviewId="newer",
                reviewPath="reviews/newer.md",
                clientId="c",
                status="pending",
                files=[
                    ReviewFileRecord(file="a.ts", hash="111"),
                    ReviewFileRecord(file="b.ts", hash="222"),
                ],
            ),
            ReviewMetadata(
                timestamp=now.isoformat(),
                reviewId="partial",
                reviewPath="reviews/partial.md",
                clientId="c",
                status="pending",
                files=[ReviewFileRecord(file="a.ts", hash="111")],
            ),
            ReviewMetadata(
                timestamp=now.isoformat(),
                reviewId="done",
                reviewPath="reviews/done.md",
                clientId="c",
                status="completed",
                files=[
                    ReviewFileRecord(file="a.ts", hash="111"),
                    ReviewFileRecord(file="b.ts", hash="222"),
                ],
            ),
        ]
        entries = [
            EditRecord(timestamp=now.isoformat(), file="a.ts", hash="111"),
            EditRecord(timestamp=now.isoformat(), file="b.ts", hash="222"),
        ]

        matches = pending_reviews_for_entries(state, entries)

        self.assertEqual([entry.reviewId for entry in matches], ["newer", "older"])

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

    def test_best_pending_review_covering_entries_prefers_more_overlap_then_newer(self):
        import datetime
        from datetime import timedelta, timezone
        now = datetime.datetime.now(timezone.utc)
        state = [
            ReviewMetadata(
                timestamp=(now - timedelta(minutes=10)).isoformat(),
                reviewId="one-overlap-old",
                reviewPath="reviews/one-overlap-old.md",
                clientId="c",
                status="pending",
                files=[ReviewFileRecord(file="a.ts", hash="111")],
            ),
            ReviewMetadata(
                timestamp=now.isoformat(),
                reviewId="two-overlap-new",
                reviewPath="reviews/two-overlap-new.md",
                clientId="c",
                status="pending",
                files=[
                    ReviewFileRecord(file="a.ts", hash="111"),
                    ReviewFileRecord(file="b.ts", hash="222"),
                ],
            ),
            ReviewMetadata(
                timestamp=(now - timedelta(minutes=1)).isoformat(),
                reviewId="two-overlap-old",
                reviewPath="reviews/two-overlap-old.md",
                clientId="c",
                status="pending",
                files=[
                    ReviewFileRecord(file="a.ts", hash="111"),
                    ReviewFileRecord(file="b.ts", hash="222"),
                ],
            ),
        ]
        entries = [
            EditRecord(timestamp=now.isoformat(), file="a.ts", hash="111"),
            EditRecord(timestamp=now.isoformat(), file="b.ts", hash="222"),
        ]

        best = best_pending_review_covering_entries(state, entries)

        self.assertIsNotNone(best)
        self.assertEqual(best.reviewId, "two-overlap-new")

    def test_best_pending_review_for_entries_returns_none_for_no_overlap(self):
        import datetime
        from datetime import timezone as tz
        now = datetime.datetime.now(tz.utc)
        state = [
            ReviewMetadata(
                timestamp=now.isoformat(),
                reviewId="unrelated",
                reviewPath="reviews/unrelated.md",
                clientId="c",
                status="pending",
                files=[ReviewFileRecord(file="z.ts", hash="999")],
            )
        ]
        entries = [EditRecord(timestamp=now.isoformat(), file="a.ts", hash="111")]

        self.assertIsNone(best_pending_review_for_entries(state, entries))


if __name__ == "__main__":
    unittest.main()
