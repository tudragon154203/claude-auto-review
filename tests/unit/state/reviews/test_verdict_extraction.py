import unittest

from claude_auto_review.state.reviews.review_text import (
    extract_review_findings_text,
    extract_review_verdict_text,
)


class TestExtractReviewVerdictText(unittest.TestCase):
    def test_returns_verdict_line_from_verdict_section(self):
        content = "## Findings\nNone\n\n## Verdict\nClean - no issues found. Claude may stop.\n"
        self.assertEqual(extract_review_verdict_text(content), "Clean - no issues found. Claude may stop.")

    def test_skips_blank_lines_after_heading(self):
        content = "## Verdict\n\n\nClean.\n"
        self.assertEqual(extract_review_verdict_text(content), "Clean.")

    def test_returns_none_when_no_verdict_or_findings(self):
        content = "## Summary\nAll good.\n"
        self.assertIsNone(extract_review_verdict_text(content))

    def test_returns_none_for_none(self):
        self.assertIsNone(extract_review_verdict_text(None))

    def test_returns_none_for_empty_string(self):
        self.assertIsNone(extract_review_verdict_text(""))

    def test_fallback_to_clean_in_findings_when_no_verdict_section(self):
        content = "## Findings\nclean - no issues\n\n## Other\nstuff\n"
        self.assertEqual(extract_review_verdict_text(content), "clean - no issues")

    def test_fallback_to_confirmed_clean_in_findings(self):
        content = "## Findings\nconfirmed (Clean)\n"
        self.assertEqual(extract_review_verdict_text(content), "confirmed (Clean)")

    def test_fallback_returns_none_if_findings_has_no_clean_line(self):
        content = "## Findings\n### 1. Bug\n\n## Other\n"
        self.assertIsNone(extract_review_verdict_text(content))

    def test_uses_first_non_empty_line(self):
        content = "## Verdict\n\nClean - no issues found.\n\nExtra notes that should be ignored.\n"
        self.assertEqual(extract_review_verdict_text(content), "Clean - no issues found.")

    def test_falls_back_to_findings_clean_line(self):
        content = "## Findings\nConfirmed (clean)\n\nExtra notes that should be ignored.\n"
        self.assertEqual(extract_review_verdict_text(content), "Confirmed (clean)")


class TestExtractReviewFindingsText(unittest.TestCase):
    def test_extracts_text_between_findings_and_verdict(self):
        content = "## Findings\n### 1. Bug\nDetails here.\n\n## Verdict\n1 issues found.\n"
        result = extract_review_findings_text(content)
        self.assertIn("### 1. Bug", result)
        self.assertNotIn("## Verdict", result)

    def test_returns_none_when_no_findings_section(self):
        content = "## Verdict\nClean.\n"
        self.assertIsNone(extract_review_findings_text(content))

    def test_returns_none_for_none_content(self):
        self.assertIsNone(extract_review_findings_text(None))

    def test_returns_none_for_empty_content(self):
        self.assertIsNone(extract_review_findings_text(""))

    def test_returns_findings_when_no_verdict_section(self):
        content = "## Findings\nNo issues found.\n"
        result = extract_review_findings_text(content)
        self.assertEqual(result.strip(), "No issues found.")

    def test_returns_none_for_whitespace_only_findings(self):
        content = "## Findings\n  \n\n## Verdict\nClean.\n"
        self.assertIsNone(extract_review_findings_text(content))

    def test_strips_whitespace(self):
        content = "## Findings\n  \n### 1. Issue\n  \n\n## Verdict\n1 issues found.\n"
        result = extract_review_findings_text(content)
        self.assertTrue(result.startswith("### 1. Issue"))


if __name__ == "__main__":
    unittest.main()
