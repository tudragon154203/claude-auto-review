import unittest
from datetime import datetime, timedelta

from claude_auto_review.state.review_records import ReviewMetadata
from claude_auto_review.state.reviews.expiry import is_review_expired


class TestReviewsExpiry(unittest.TestCase):
    def test_is_review_expired_with_timeout_zero(self):
        entry = ReviewMetadata(
            timestamp="2024-01-01T07:00:00+07:00",
            reviewId="r1",
            reviewPath="reviews/r1.md",
            files=[],
            clientId="c",
        )
        self.assertFalse(is_review_expired(entry, 0))

    def test_is_review_expired_missing_timestamp(self):
        entry = ReviewMetadata(
            timestamp="",
            reviewId="r1",
            reviewPath="reviews/r1.md",
            files=[],
            clientId="c",
        )
        self.assertFalse(is_review_expired(entry, 1))

    def test_is_review_expired_invalid_timestamp(self):
        entry = ReviewMetadata(
            timestamp="not-a-date",
            reviewId="r1",
            reviewPath="reviews/r1.md",
            files=[],
            clientId="c",
        )
        self.assertFalse(is_review_expired(entry, 1))

    def test_is_review_expired_old_review(self):
        old_time = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
        entry = ReviewMetadata(
            timestamp=old_time,
            reviewId="r1",
            reviewPath="reviews/r1.md",
            files=[],
            clientId="c",
        )
        self.assertTrue(is_review_expired(entry, 1))

    def test_is_review_expired_recent_review(self):
        recent_time = (datetime.now().astimezone() - timedelta(minutes=30)).isoformat()
        entry = ReviewMetadata(
            timestamp=recent_time,
            reviewId="r1",
            reviewPath="reviews/r1.md",
            files=[],
            clientId="c",
        )
        self.assertFalse(is_review_expired(entry, 1))

    def test_is_review_expired_non_review_metadata_fallback(self):
        from claude_auto_review.state.edit_record import EditRecord

        entry = EditRecord(timestamp="2024-01-01T07:00:00+07:00", file="a.ts", hash="aaa")
        self.assertFalse(is_review_expired(entry, 1))


if __name__ == "__main__":
    unittest.main()
