import unittest

from claude_auto_review.state.reviews import is_review_complete, is_review_expired

from tests.unit.state.support import StateTestCase


class TestReviewCompletion(StateTestCase, unittest.TestCase):

    def test_returns_false_when_review_file_missing(self):
        project_root = self.temp_project()
        missing = project_root / "no-such-review.md"
        self.assertFalse(is_review_complete(missing))

    def test_returns_false_when_verdict_heading_missing(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("# Files\n\nSome notes\n", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_is_empty(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\n", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_equals_pending_uppercase(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nPending", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_equals_pending_with_period(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nPending.", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_has_pending_word_in_context(self):
        # Substring checks would incorrectly fail; confirm we pass
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nAll issues addressed. No pending items.", encoding="utf-8")
        self.assertTrue(is_review_complete(path), "Should pass when 'pending' is just a word, not the literal placeholder")

    def test_returns_true_when_verdict_is_clean_message(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nClean - no issues found.", encoding="utf-8")
        self.assertTrue(is_review_complete(path))

    def test_returns_true_when_verdict_is_a_fixed_message(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nAll fixes applied.", encoding="utf-8")
        self.assertTrue(is_review_complete(path))

    def test_is_case_insensitive(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nPENDING", encoding="utf-8")
        self.assertFalse(is_review_complete(path))
        path.write_text("## Verdict\nPEnDInG.", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_is_review_expired_with_timeout_zero(self):
        entry = {"timestamp": "2024-01-01T00:00:00Z"}
        self.assertFalse(is_review_expired(entry, 0))

    def test_is_review_expired_missing_timestamp(self):
        entry = {"reviewId": "r1"}
        self.assertFalse(is_review_expired(entry, 1))

    def test_is_review_expired_invalid_timestamp(self):
        entry = {"timestamp": "not-a-date"}
        self.assertFalse(is_review_expired(entry, 1))

    def test_is_review_expired_old_review(self):
        from datetime import datetime, timedelta, timezone
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        entry = {"timestamp": old_time}
        self.assertTrue(is_review_expired(entry, 1))

    def test_is_review_expired_recent_review(self):
        from datetime import datetime, timedelta, timezone
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
        entry = {"timestamp": recent_time}
        self.assertFalse(is_review_expired(entry, 1))


