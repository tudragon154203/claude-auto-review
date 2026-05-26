import unittest

from claude_auto_review.state.reviews.parsing import parse_review_findings


class TestParseReviewFindingsEdgeCases(unittest.TestCase):

    def test_parse_finding_block_extracts_severity_from_bracket_heading(self):
        content = "## Findings\n### [High] Security issue\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "high")

    def test_parse_finding_block_extracts_severity_from_numbered_heading(self):
        content = "## Findings\n### 1. Issue\n**Severity:** Medium\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "medium")  # Pulled from field when not in heading

    def test_parse_finding_block_fallback_to_field_severity(self):
        content = "## Findings\n### 1. Issue\n**Severity:** Low\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "low")

    def test_parse_finding_block_extracts_verdict_from_field(self):
        content = "## Findings\n### 1. Issue\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].verdict, "Confirmed")

    def test_parse_finding_block_with_severity_in_heading_no_field_severity(self):
        content = (
            "## Findings\n"
            "### 1. [Medium] Missing severity field\n"
            "Some details here.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "medium")


if __name__ == "__main__":
    unittest.main()