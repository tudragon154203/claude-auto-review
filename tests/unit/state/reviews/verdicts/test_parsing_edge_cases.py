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
        content = "## Findings\n" "### 1. [Medium] Missing severity field\n" "Some details here.\n"
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "medium")

    # --- Bracket verdict-severity format [Confirmed-High] ---

    def test_bracket_confirmed_high_extracts_both(self):
        content = "## Findings\n### [Confirmed-High] SQL injection\n**Location:** auth.py:42\n"
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "high")
        self.assertEqual(findings[0].verdict, "confirmed")

    def test_bracket_skipped_low_extracts_both(self):
        content = "## Findings\n### [Skipped-Low] Style nit\n\n## Verdict\nClean.\n"
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "low")
        self.assertEqual(findings[0].verdict, "skipped")

    def test_bracket_confirmed_medium_with_number_prefix(self):
        content = "## Findings\n### 2. [Confirmed-Medium] Race condition\n\n## Verdict\n1 issue.\n"
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "medium")
        self.assertEqual(findings[0].verdict, "confirmed")

    def test_bracket_confirmed_invalid_severity_not_treated_as_verdict_severity(self):
        """[Confirmed-Invalid] splits into verdict=confirmed, severity=<unrecognized>."""
        content = "## Findings\n### [Confirmed-Invalid] Something\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "confirmed")
        self.assertEqual(findings[0].severity, "<unrecognized>")

    # --- Canonical indented fields ---

    def test_canonical_severity_field_overrides_unrecognized(self):
        content = (
            "## Findings\n"
            "### [Unknown] Issue\n"
            "  Severity: Critical\n"
            "  Verdict: Confirmed\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "critical")

    def test_canonical_verdict_field_overrides_heading_verdict(self):
        content = (
            "## Findings\n"
            "### [Confirmed-High] Issue\n"
            "  Verdict: Skipped\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].verdict, "Skipped")

    def test_canonical_field_with_extra_whitespace(self):
        content = (
            "## Findings\n"
            "### 1. Issue\n"
            "    Severity:   Low\n"
            "    Verdict:   Confirmed\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "low")
        self.assertEqual(findings[0].verdict, "Confirmed")

    def test_canonical_non_verdict_fields_ignored(self):
        """Reason/Rule/Location fields should not interfere with severity/verdict extraction."""
        content = (
            "## Findings\n"
            "### 1. [High] Bug\n"
            "  Reason: Input not sanitized\n"
            "  Rule: OWASP-A1\n"
            "  Location: handler.py:15\n"
            "  Verdict: Confirmed\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "high")
        self.assertEqual(findings[0].verdict, "Confirmed")

    # --- Bullet findings ---

    def test_bullet_confirmed_finding(self):
        content = "## Findings\n- Confirmed: SQL injection in login handler.\n\n## Verdict\n1 issue found.\n"
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "confirmed")
        self.assertIn("SQL injection", findings[0].raw_text)

    def test_bullet_skipped_finding(self):
        content = "## Findings\n* Skipped: config file not in scope.\n\n## Verdict\nClean.\n"
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "skipped")

    def test_bullet_finding_severity_from_field(self):
        content = (
            "## Findings\n"
            "- Confirmed: Hardcoded secret in source.\n"
            "**Severity:** Critical\n"
            "**Location:** config.py:3\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "critical")
        self.assertEqual(findings[0].verdict, "confirmed")

    # --- Mixed formats ---

    def test_mixed_bullet_and_heading_findings(self):
        content = (
            "## Findings\n"
            "- Confirmed: Missing error handling.\n"
            "**Severity:** Medium\n\n"
            "### 1. [High] Race condition\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "2 issues found.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].severity, "medium")
        self.assertEqual(findings[0].verdict, "confirmed")
        self.assertEqual(findings[1].severity, "high")
        self.assertEqual(findings[1].verdict, "Confirmed")

    # --- Boundary conditions ---

    def test_none_input_returns_empty(self):
        self.assertEqual(parse_review_findings(None), [])

    def test_empty_string_returns_empty(self):
        self.assertEqual(parse_review_findings(""), [])

    def test_content_with_only_verdict_section_returns_empty(self):
        content = "## Verdict\nClean - no issues found.\n"
        self.assertEqual(parse_review_findings(content), [])

    def test_empty_findings_section_returns_empty(self):
        content = "## Findings\n\n## Verdict\nClean - no issues found.\n"
        self.assertEqual(parse_review_findings(content), [])

    def test_findings_section_with_only_whitespace(self):
        content = "## Findings\n   \n\n## Verdict\nClean.\n"
        self.assertEqual(parse_review_findings(content), [])

    def test_heading_severity_takes_precedence_over_field(self):
        """When heading has a valid severity, the field severity should be ignored."""
        content = "## Findings\n### [High] Bug\n**Severity:** Low\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "high")

    def test_raw_text_preserved_for_heading_finding(self):
        content = (
            "## Findings\n"
            "### 1. [Critical] Memory leak\n"
            "**Location:** cache.py:88\n"
            "**Verdict:** Confirmed\n"
        )
        findings = parse_review_findings(content)
        self.assertIn("### 1. [Critical] Memory leak", findings[0].raw_text)
        self.assertIn("**Location:** cache.py:88", findings[0].raw_text)

    def test_raw_text_preserved_for_bullet_finding(self):
        content = "## Findings\n- Confirmed: Plaintext password stored.\n**Severity:** Critical\n"
        findings = parse_review_findings(content)
        self.assertIn("- Confirmed: Plaintext password stored.", findings[0].raw_text)

    def test_multiple_findings_all_severities(self):
        content = (
            "## Findings\n"
            "### 1. [Critical] RCE\n**Verdict:** Confirmed\n\n"
            "### 2. [High] XSS\n**Verdict:** Confirmed\n\n"
            "### 3. [Medium] Info leak\n**Verdict:** Confirmed\n\n"
            "### 4. [Low] Style\n**Verdict:** Skipped\n\n"
            "### 5. [Info] Note\n**Verdict:** Confirmed\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 5)
        self.assertEqual([f.severity for f in findings], ["critical", "high", "medium", "low", "info"])
        self.assertEqual(findings[3].verdict, "Skipped")

    def test_consecutive_heading_blocks_without_blank_lines(self):
        content = (
            "## Findings\n"
            "### 1. [High] First\n**Verdict:** Confirmed\n"
            "### 2. [Low] Second\n**Verdict:** Confirmed\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].severity, "high")
        self.assertEqual(findings[1].severity, "low")

    def test_bullet_finding_with_canonical_fields_after(self):
        content = (
            "## Findings\n"
            "- Confirmed: Unsafe deserialization\n"
            "  Severity: High\n"
            "  Verdict: Confirmed\n"
            "  Location: api.py:22\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "high")
        self.assertEqual(findings[0].verdict, "Confirmed")

    def test_heading_with_no_verdict_field_extracts_from_bracket(self):
        content = "## Findings\n### [Confirmed-Medium] Logic error\n\n## Verdict\n1 issue found.\n"
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "medium")
        self.assertEqual(findings[0].verdict, "confirmed")


if __name__ == "__main__":
    unittest.main()
