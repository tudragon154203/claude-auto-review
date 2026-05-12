import unittest

from claude_auto_review.stop.reviews.selection import find_pending_review_for_files, get_entries_covered_by_review


class TestSelection(unittest.TestCase):
    def test_find_pending_review_for_files_returns_best_match(self):
        state = [
            {
                "type": "review",
                "status": "pending",
                "reviewId": "best",
                "timestamp": "2026-05-11T10:00:00+07:00",
                "files": [{"file": "a.ts", "hash": "1"}, {"file": "b.ts", "hash": "2"}],
            },
            {
                "type": "review",
                "status": "pending",
                "reviewId": "partial",
                "timestamp": "2026-05-11T11:00:00+07:00",
                "files": [{"file": "a.ts", "hash": "1"}],
            },
        ]
        entries = [{"file": "a.ts", "hash": "1"}, {"file": "b.ts", "hash": "2"}]

        best = find_pending_review_for_files(state, entries, project_root=None)

        self.assertEqual(best["reviewId"], "best")

    def test_find_pending_review_for_files_rejects_partial_stale_match(self):
        state = [
            {
                "type": "review",
                "status": "pending",
                "reviewId": "stale",
                "timestamp": "2026-05-11T10:00:00+07:00",
                "files": [{"file": "a.ts", "hash": "old-a"}, {"file": "b.ts", "hash": "b"}],
            },
        ]
        entries = [{"file": "a.ts", "hash": "new-a"}, {"file": "b.ts", "hash": "b"}]

        best = find_pending_review_for_files(state, entries, project_root=None)

        self.assertIsNone(best)

    def test_get_entries_covered_by_review_uses_latest_state_entry(self):
        review_entry = {"files": [{"file": "src/app.ts", "hash": "22222222"}]}
        state_entries = [
            {"type": "edit", "file": "src/app.ts", "hash": "11111111", "timestamp": "2026-05-11T09:00:00+07:00"},
            {"type": "edit", "file": "src/app.ts", "hash": "22222222", "timestamp": "2026-05-11T10:00:00+07:00"},
            {"type": "edit", "file": "src/other.ts", "hash": "33333333", "timestamp": "2026-05-11T10:00:00+07:00"},
        ]

        covered = get_entries_covered_by_review(review_entry, state_entries)

        self.assertEqual([entry["hash"] for entry in covered], ["22222222"])
