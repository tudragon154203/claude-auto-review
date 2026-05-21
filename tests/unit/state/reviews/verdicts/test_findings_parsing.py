import unittest

from claude_auto_review.state.reviews.findings import (
    has_blocking_review_findings,
    has_review_findings,
    parse_review_findings,
)


class TestHasReviewFindings(unittest.TestCase):
    def test_has_review_findings_detects_real_findings_after_clean_declaration(self):
        """A clean declaration before real headings still means findings exist."""
        content = (
            "## Findings\n"
            "Clean - no issues found.\n\n"
            "### 1. Unused import\n"
            "**Severity:** LOW\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_has_review_findings_detects_no_findings_summary_prose(self):
        content = (
            "## Findings\n"
            "No semantic bugs, security issues, or maintainability concerns identified.\n"
            "All code follows project conventions.\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_detects_real_findings_despite_negation_prefix(self):
        """A line starting with a negation phrase but containing ### findings is still findings."""
        content = (
            "## Findings\n"
            "No semantic bugs were addressed.\n\n"
            "### 1. Race condition in counter\n"
            "**Severity:** HIGH\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_parse_review_findings_extracts_structured_severity_and_verdict(self):
        content = (
            "## Findings\n"
            "### 1. [Info] Documentation note\n"
            "**Verdict:** Confirmed\n\n"
            "### 2. [Low] Optional cleanup\n"
            "**Verdict:** Skipped\n"
        )
        findings = parse_review_findings(content)

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].severity, "info")
        self.assertEqual(findings[0].verdict, "Confirmed")
        self.assertEqual(findings[1].severity, "low")
        self.assertEqual(findings[1].verdict, "Skipped")

    def test_has_blocking_review_findings_respects_threshold(self):
        content = (
            "## Findings\n"
            "### 1. [Info] Note\n"
            "**Verdict:** Confirmed\n\n"
            "### 2. [Low] Cleanup\n"
            "**Verdict:** Confirmed\n"
        )
        self.assertFalse(has_blocking_review_findings(content, "medium"))
        self.assertTrue(has_blocking_review_findings(content, "low"))

    def test_has_blocking_review_findings_skipped_findings_never_block(self):
        content = (
            "## Findings\n"
            "### 1. [Critical] Safety issue\n"
            "**Verdict:** Skipped\n"
        )
        self.assertFalse(has_blocking_review_findings(content, "info"))

    def test_has_blocking_review_findings_missing_severity_blocks(self):
        content = (
            "## Findings\n"
            "### 1. Missing severity heading\n"
            "**Verdict:** Confirmed\n"
        )
        self.assertTrue(has_blocking_review_findings(content, "critical"))

    def test_has_blocking_review_findings_unparseable_confirmed_severity_blocks(self):
        content = (
            "## Findings\n"
            "### 1. [Mystery] Unexpected label\n"
            "**Verdict:** Confirmed\n"
        )
        self.assertTrue(has_blocking_review_findings(content, "medium"))

    def test_has_blocking_review_findings_mixed_severities_block_only_at_threshold(self):
        content = (
            "## Findings\n"
            "### 1. [Info] Advisory note\n"
            "**Verdict:** Confirmed\n\n"
            "### 2. [Low] Another advisory note\n"
            "**Verdict:** Confirmed\n\n"
            "### 3. [Medium] Blocking note\n"
            "**Verdict:** Confirmed\n"
        )
        self.assertFalse(has_blocking_review_findings(content, "high"))
        self.assertTrue(has_blocking_review_findings(content, "medium"))

    def test_has_review_findings_detects_none_line_as_no_findings(self):
        content = (
            "## Findings\n"
            "None. The new test is well-structured and the assertions cover the intended behavior.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_ignores_notes_section(self):
        content = (
            "## Findings\n"
            "No issues found.\n\n"
            "**Notes:**\n"
            "- completion.py uses consistent naming\n"
            "- test coverage is comprehensive\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_detects_real_findings_despite_notes(self):
        content = (
            "## Findings\n"
            "### 1. Unused variable\n"
            "**Verdict:** Confirmed\n\n"
            "**Notes:** Minor observation only.\n\n"
            "## Verdict\n"
            "1 issues found. Claude must address all findings before stopping.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_has_review_findings_detects_no_bugs_line(self):
        content = (
            "## Findings\n"
            "No bugs found.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_detects_clean_negations(self):
        cases = [
            "No concerns identified.",
            "No findings. The change is a mechanical visibility rename.",
            "No semantic issues found.",
        ]
        for finding_line in cases:
            with self.subTest(finding_line=finding_line):
                content = (
                    "## Findings\n"
                    f"{finding_line}\n\n"
                    "## Verdict\n"
                    "Clean - no issues found.\n"
                )
                self.assertFalse(has_review_findings(content))

    def test_has_review_findings_detects_no_issues_found_in_test_file(self):
        content = (
            "## Findings\n"
            "No issues found in the test file.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_rejects_explicit_contradiction_after_no_issues_line(self):
        content = (
            "## Findings\n"
            "No issues found in the test file, but the regression remains.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_has_review_findings_detects_mixed_prose_with_placeholder_line(self):
        content = (
            "## Findings\n"
            "Sensitive data logged to console.\n\n"
            "Completed review from /tmp/prompt.md\n\n"
            "## Verdict\n"
            "Not Clean - security issue found.\n"
        )
        self.assertTrue(has_review_findings(content))


if __name__ == "__main__":
    unittest.main()
