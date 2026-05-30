import unittest

from claude_auto_review.state.reviews.findings import parse_review_findings


class TestParseReviewFindings(unittest.TestCase):
    def test_extracts_structured_severity_and_verdict(self):
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

    def test_heading_severity_from_numbered_heading(self):
        content = "## Findings\n### 1. [Critical] Issue\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "critical")

    def test_heading_severity_from_plain_heading(self):
        content = "## Findings\n### Major Problem\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertIsNone(findings[0].severity)

    def test_severity_fallback_to_field(self):
        content = "## Findings\n### [Unknown] Something\n**Severity:** High\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "high")

    def test_normalizes_unknown_severity_to_sentinel(self):
        content = "## Findings\n### [Mystery] Something\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "<unrecognized>")

    def test_ignores_non_finding_numbered_bold_lines(self):
        content = (
            "## Findings\n"
            "1. **Notes - not a finding**\n"
            "- Just prose, no verdict/severity.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings, [])

    def test_ignores_high_level_non_finding(self):
        content = (
            "## Findings\n"
            "1. **High-level architecture overview**\n"
            "- Just a description, not a finding.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings, [])

    def test_ignores_hyphenated_non_badge_labels(self):
        content = (
            "## Findings\n"
            "### [High-level] Architecture overview\n"
            "**Verdict:** Confirmed\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        # "High-level" is not a valid verdict-severity badge → <unrecognized>
        self.assertEqual(findings[0].severity, "<unrecognized>")
        self.assertEqual(findings[0].verdict, "Confirmed")

    def test_ignores_hyphenated_inline_badges(self):
        content = (
            "## Findings\n"
            "1. **Confirmed - High-level architecture overview**\n"
            "- Just prose, not a severity-tagged finding.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings, [])

    def test_rejects_duplicate_confirmed_labels(self):
        content = (
            "## Findings\n"
            "1. **Confirmed Confirmed - Medium**\n"
            "- Duplicate verdict token should not be parsed as a finding.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings, [])

    def test_accepts_codex_inline_confirmed_without_severity_when_fields_present(self):
        content = (
            "## Findings\n"
            "1. **Confirmed - Module import is invalid**\n"
            "**Location:** claude_auto_review/state/reviews/matching.py:7\n"
            "**Fix:** Import the correct symbol.\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found. Claude must address all findings before stopping.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "Confirmed")
        self.assertIsNone(findings[0].severity)
        self.assertIn("Module import is invalid", findings[0].raw_text)

    def test_ignores_severity_field_in_prose(self):
        content = (
            "## Findings\n"
            "The module follows standard conventions.\n"
            "**Severity:** questionable naming in prose section.\n"
            "No further issues identified.\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 0)

    def test_ignores_field_labels_in_narrative_paragraphs(self):
        content = (
            "## Findings\n"
            "Reviewed the diff carefully. The refactoring moves helpers into\n"
            "submodules cleanly. **Severity:** not applicable for prose.\n"
            "**Verdict:** this paragraph is not a finding.\n"
            "Recommendation: consider splitting further in a future PR.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 0)

    def test_severity_field_with_valid_level_starts_block(self):
        content = (
            "## Findings\n"
            "### 1. Issue\n"
            "**Severity:** High\n"
            "**Location:** core.py:10\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found. Claude must address all findings before stopping.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "high")


if __name__ == "__main__":
    unittest.main()
