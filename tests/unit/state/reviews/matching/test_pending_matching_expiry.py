import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.state.models import EditRecord, ReviewFileRecord, ReviewMetadata
from claude_auto_review.state.reviews.matching import (
    pending_review_candidates_for_entries,
    pending_reviews_for_entries,
)


class TestPendingMatchingExpiry(unittest.TestCase):

    def test_pending_review_candidates_for_entries_skips_expired_reviews(self):
        now = datetime.now(timezone.utc)
        expired = ReviewMetadata(
            timestamp=(now - timedelta(hours=2)).isoformat(),
            reviewId="expired",
            reviewPath="reviews/expired.md",
            clientId="c",
            status="pending",
            files=[ReviewFileRecord(file="a.ts", hash="111")],
        )
        fresh = ReviewMetadata(
            timestamp=now.isoformat(),
            reviewId="fresh",
            reviewPath="reviews/fresh.md",
            clientId="c",
            status="pending",
            files=[ReviewFileRecord(file="a.ts", hash="111")],
        )
        entries = [EditRecord(timestamp=now.isoformat(), file="a.ts", hash="111")]
        state = [expired, fresh]

        with patch("claude_auto_review.state.reviews.matching.is_review_expired", side_effect=lambda entry, timeout_hours: entry.reviewId == "expired"):
            candidates = pending_review_candidates_for_entries(state, entries, project_root=Path(tempfile.mkdtemp()), timeout_hours=1)

        self.assertEqual([candidate["review"].reviewId for candidate in candidates], ["fresh"])
        self.assertEqual(candidates[0]["overlap_count"], 1)


if __name__ == "__main__":
    unittest.main()
