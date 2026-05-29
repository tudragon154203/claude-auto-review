import unittest

from claude_auto_review.state.reviews.completion import (
    is_review_clean_verdict,
    is_review_complete_verdict,
)


class TestIsReviewCompleteVerdict(unittest.TestCase):
    def test_clean_is_complete(self):
        self.assertTrue(is_review_complete_verdict("Clean - no issues found."))

    def test_confirmed_clean_is_complete(self):
        self.assertTrue(is_review_complete_verdict("Confirmed (Clean)"))

    def test_not_clean_is_complete(self):
        self.assertTrue(is_review_complete_verdict("Not clean - fix bugs"))

    def test_findings_present_is_complete(self):
        self.assertTrue(is_review_complete_verdict("Findings present. Claude must address all findings."))

    def test_has_findings_is_complete(self):
        self.assertTrue(is_review_complete_verdict("Has findings"))

    def test_n_issues_is_complete(self):
        self.assertTrue(is_review_complete_verdict("3 issues found. Claude must fix."))

    def test_issue_found_is_complete(self):
        self.assertTrue(is_review_complete_verdict("Issue found"))

    def test_all_fixed_is_complete(self):
        self.assertTrue(is_review_complete_verdict("All fixes applied"))

    def test_all_addressed_is_complete(self):
        self.assertTrue(is_review_complete_verdict("All issues addressed"))

    def test_pending_is_not_complete(self):
        self.assertFalse(is_review_complete_verdict("pending"))

    def test_pending_with_dot_is_not_complete(self):
        self.assertFalse(is_review_complete_verdict("pending."))

    def test_none_is_not_complete(self):
        self.assertFalse(is_review_complete_verdict(None))

    def test_empty_string_is_not_complete(self):
        self.assertFalse(is_review_complete_verdict(""))

    def test_strips_whitespace(self):
        self.assertTrue(is_review_complete_verdict("  Clean  "))

    def test_case_insensitive(self):
        self.assertTrue(is_review_complete_verdict("FINDINGS PRESENT"))


class TestIsReviewCleanVerdict(unittest.TestCase):
    def test_clean_prefix(self):
        self.assertTrue(is_review_clean_verdict("Clean - no issues found. Claude may stop."))

    def test_clean_case_insensitive(self):
        self.assertTrue(is_review_clean_verdict("clean"))

    def test_confirmed_clean_with_parens(self):
        self.assertTrue(is_review_clean_verdict("Confirmed (Clean)"))

    def test_confirmed_clean_no_spaces(self):
        self.assertTrue(is_review_clean_verdict("Confirmed(Clean)"))

    def test_confirmed_clean_with_trailing_text(self):
        self.assertTrue(is_review_clean_verdict("Confirmed (Clean) - no issues"))

    def test_not_clean_rejected(self):
        self.assertFalse(is_review_clean_verdict("Not clean - fix src/app.ts"))

    def test_not_clean_uppercase_rejected(self):
        self.assertFalse(is_review_clean_verdict("Not Clean"))

    def test_findings_present_rejected(self):
        self.assertFalse(is_review_clean_verdict("Findings present. Claude must address."))

    def test_none_returns_false(self):
        self.assertFalse(is_review_clean_verdict(None))

    def test_empty_string_returns_false(self):
        self.assertFalse(is_review_clean_verdict(""))

    def test_n_issues_rejected(self):
        self.assertFalse(is_review_clean_verdict("2 issues found"))


if __name__ == "__main__":
    unittest.main()
