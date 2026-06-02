import unittest

from claude_auto_review.state.reviews.completion import (
    is_completed_review_content,
    is_placeholder_review_content,
    is_review_complete,
)
from tests.unit.state.support import StateTestCase


class TestReviewCompleteness(StateTestCase, unittest.TestCase):
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
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nAll issues addressed. No pending items.", encoding="utf-8")
        self.assertTrue(
            is_review_complete(path), "Should pass when 'pending' is just a word, not the literal placeholder"
        )

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


class TestCompletedReviewContent(unittest.TestCase):
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

    def test_unstructured_short_output_not_marked_completed(self):
        """Stray codex fallback text or stderr leaks must not be classified
        as a completed review just because they bypass the placeholder markers.
        """
        self.assertFalse(is_completed_review_content(" found. Claude may stop.\n"))
        self.assertFalse(is_completed_review_content("Error: model not available\n"))
        self.assertFalse(is_completed_review_content("```\n\n[1m[31mfatal[0m runtime error\n```\n"))

    def test_completed_review_with_only_findings_heading_recognized(self):
        content = (
            "# Review rev-1\n\n"
            "## Files Reviewed\n"
            "- README.md (hash: abc123)\n\n"
            "## Findings\n"
            "1. **Low** - Flowchart misses a stop branch.\n"
        )
        self.assertTrue(is_completed_review_content(content))


if __name__ == "__main__":
    unittest.main()
