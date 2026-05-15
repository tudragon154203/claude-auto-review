import unittest

from claude_auto_review.state.models import ReviewMetadata
from claude_auto_review.state.reviews import (
    extract_review_verdict_text,
    is_completed_review_content,
    is_placeholder_review_content,
    is_review_clean,
    is_review_clean_content,
    is_review_complete,
    is_review_expired,
)

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

    def test_is_review_clean_accepts_confirmed_clean_verdict(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nConfirmed (Clean) - no issues found.", encoding="utf-8")
        self.assertTrue(is_review_clean(path))

    def test_is_review_clean_rejects_not_clean_verdict(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nNot clean - fix src/app.ts.", encoding="utf-8")
        self.assertFalse(is_review_clean(path))

    def test_is_review_clean_rejects_clean_verdict_when_findings_exist(self):
        content = (
            "## Findings\n"
            "### [Low] Unused import\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        self.assertFalse(is_review_clean_content(content))

    def test_is_review_clean_accepts_clean_verdict_with_none_findings_summary(self):
        content = (
            "## Findings\n"
            "None. The new test is well-structured and the assertions cover the intended behavior.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertTrue(is_review_clean_content(content))

    def test_returns_true_when_verdict_is_a_fixed_message(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nAll fixes applied.", encoding="utf-8")
        self.assertTrue(is_review_complete(path))

    def test_extract_review_verdict_text_uses_first_non_empty_line(self):
        content = "## Verdict\n\nClean - no issues found.\n\nExtra notes that should be ignored.\n"
        self.assertEqual(extract_review_verdict_text(content), "Clean - no issues found.")

    def test_marks_any_non_placeholder_review_content_as_completed(self):
        content = (
            "# Review rev-1\n\n"
            "## Files Reviewed\n"
            "- README.md (hash: abc123)\n\n"
            "## Findings\n"
            "1. **Low** - Flowchart misses a stop branch.\n"
        )
        self.assertTrue(is_completed_review_content(content))

    def test_marks_placeholder_review_content_as_not_completed(self):
        content = (
            "# Review rev-1\n\n"
            "## Files Reviewed\n"
            "- README.md (hash: abc123)\n\n"
            "## Findings\n\n"
            "No findings yet. This file is a placeholder until Claude completes the review.\n\n"
            "Pending. Claude must complete this review from /tmp/review-prompt.md.\n"
        )
        self.assertTrue(is_placeholder_review_content(content))
        self.assertFalse(is_completed_review_content(content))

    def test_is_case_insensitive(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nPENDING", encoding="utf-8")
        self.assertFalse(is_review_complete(path))
        path.write_text("## Verdict\nPEnDInG.", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

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
        from datetime import datetime, timedelta
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
        from datetime import datetime, timedelta
        recent_time = (datetime.now().astimezone() - timedelta(minutes=30)).isoformat()
        entry = ReviewMetadata(
            timestamp=recent_time,
            reviewId="r1",
            reviewPath="reviews/r1.md",
            files=[],
            clientId="c",
        )
        self.assertFalse(is_review_expired(entry, 1))


