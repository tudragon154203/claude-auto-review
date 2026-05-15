import unittest
from pathlib import Path

from claude_auto_review.state.models import EditRecord, ReviewFileRecord, ReviewMetadata
from claude_auto_review.stop.reviews.core.selection import find_pending_review_for_files, get_entries_covered_by_review


def _mk_edit(file: str, hash: str, reviewed: bool = False) -> EditRecord:
    return EditRecord(timestamp="2026-05-11T10:00:00+07:00", file=file, hash=hash, reviewed=reviewed)


def _mk_review(reviewId: str, status: str, files: list, timestamp: str = "2026-05-11T10:00:00+07:00") -> ReviewMetadata:
    return ReviewMetadata(
        timestamp=timestamp,
        reviewId=reviewId,
        reviewPath="/fake/r.md",
        files=files,
        clientId="test",
        status=status,
    )


class TestSelection(unittest.TestCase):
    def test_find_pending_review_for_files_returns_best_match(self):
        state = [
            _mk_review(
                "best",
                "pending",
                files=[ReviewFileRecord(file="a.ts", hash="1"), ReviewFileRecord(file="b.ts", hash="2")],
                timestamp="2026-05-11T10:00:00+07:00",
            ),
            _mk_review(
                "partial",
                "pending",
                files=[ReviewFileRecord(file="a.ts", hash="1")],
                timestamp="2026-05-11T11:00:00+07:00",
            ),
        ]
        entries = [_mk_edit("a.ts", "1"), _mk_edit("b.ts", "2")]

        best = find_pending_review_for_files(state, entries, project_root=None)

        self.assertIsNotNone(best)
        self.assertEqual(best.reviewId, "best")

    def test_find_pending_review_for_files_rejects_partial_stale_match(self):
        state = [
            _mk_review(
                "stale",
                "pending",
                files=[ReviewFileRecord(file="a.ts", hash="old-a"), ReviewFileRecord(file="b.ts", hash="b")],
                timestamp="2026-05-11T10:00:00+07:00",
            ),
        ]
        entries = [_mk_edit("a.ts", "new-a"), _mk_edit("b.ts", "b")]

        best = find_pending_review_for_files(state, entries, project_root=None)

        self.assertIsNone(best)

    def test_find_pending_review_for_files_rejects_superset_stale_match(self):
        state = [
            _mk_review(
                "stale",
                "pending",
                files=[ReviewFileRecord(file="a.ts", hash="a"), ReviewFileRecord(file="b.ts", hash="b")],
                timestamp="2026-05-11T10:00:00+07:00",
            ),
        ]
        entries = [_mk_edit("a.ts", "a")]

        best = find_pending_review_for_files(state, entries, project_root=None)

        self.assertIsNone(best)

    def test_get_entries_covered_by_review_uses_latest_state_entry(self):
        review_entry = _mk_review("r", "pending", files=[ReviewFileRecord(file="src/app.ts", hash="22222222")])
        state_entries = [
            _mk_edit("src/app.ts", "11111111"),
            _mk_edit("src/app.ts", "22222222"),
            _mk_edit("src/other.ts", "33333333"),
        ]

        covered = get_entries_covered_by_review(review_entry, state_entries)

        self.assertEqual([entry.hash for entry in covered], ["22222222"])
