import unittest

from claude_auto_review.state.reviews.findings import has_blocking_review_findings
from claude_auto_review.state.reviews.parsing import parse_review_findings


class TestHasBlockingReviewFindings(unittest.TestCase):
    def _review(self, findings_text, verdict="1 issues found. Claude must address all findings before stopping."):
        return f"## Findings\n{findings_text}\n\n## Verdict\n{verdict}\n"

    def test_respects_threshold(self):
        content = (
            "## Findings\n"
            "### 1. [Info] Note\n"
            "**Verdict:** Confirmed\n\n"
            "### 2. [Low] Cleanup\n"
            "**Verdict:** Confirmed\n"
        )
        self.assertFalse(has_blocking_review_findings(content, "medium"))
        self.assertTrue(has_blocking_review_findings(content, "low"))

    def test_skipped_findings_never_block(self):
        content = "## Findings\n### 1. [Critical] Safety issue\n**Verdict:** Skipped\n"
        self.assertFalse(has_blocking_review_findings(content, "info"))

    def test_missing_severity_with_canonical_fields_is_ambiguous_not_blocking(self):
        """Missing severity with canonical fields (no contradiction) is ambiguous —
        F2 fix: treat as non-blocking rather than conservative block."""
        content = "## Findings\n### 1. Missing severity heading\n**Verdict:** Confirmed\n"
        self.assertFalse(has_blocking_review_findings(content, "medium"))
        self.assertFalse(has_blocking_review_findings(content, "info"))

    def test_unparseable_confirmed_severity_blocks(self):
        """Unrecognized severity in brackets falls back to default blocking threshold."""
        content = "## Findings\n### 1. [Mystery] Unexpected label\n**Verdict:** Confirmed\n"
        self.assertTrue(has_blocking_review_findings(content, "medium"))

    def test_mixed_severities_block_only_at_threshold(self):
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

    def test_none_threshold_defaults_to_medium(self):
        content = self._review("### 1. [Low] Nit\n**Verdict:** Confirmed\n")
        self.assertFalse(has_blocking_review_findings(content, None))

    def test_empty_threshold_defaults_to_medium(self):
        content = self._review("### 1. [Low] Nit\n**Verdict:** Confirmed\n")
        self.assertFalse(has_blocking_review_findings(content, ""))

    def test_garbage_threshold_defaults_to_medium(self):
        content = self._review("### 1. [Low] Nit\n**Verdict:** Confirmed\n")
        self.assertFalse(has_blocking_review_findings(content, "mystery"))

    def test_no_parsed_findings_falls_back_to_has_review_findings(self):
        content = self._review("No issues found.\n", "Clean - no issues found. Claude may stop.\n")
        self.assertFalse(has_blocking_review_findings(content, "low"))

    def test_no_findings_section_content(self):
        self.assertFalse(has_blocking_review_findings(None, "low"))

    def test_codex_inline_without_severity_blocks(self):
        """Codex-style inline finding without severity badge but with a
        contradiction signal in the prose still blocks."""
        content = (
            "## Findings\n"
            "1. **Confirmed - Module import is invalid however it compiles**\n"
            "**Location:** claude_auto_review/state/reviews/matching.py:7\n"
            "**Fix:** Import the correct symbol.\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found. Claude must address all findings before stopping.\n"
        )
        self.assertTrue(has_blocking_review_findings(content, "medium"))
        self.assertTrue(has_blocking_review_findings(content, "info"))

    def test_no_severity_no_canonical_fields_prose_noise_is_not_blocking(self):
        """P0/F2: A verdict-only finding without severity AND no canonical fields,
        where the prose is a no-findings line, does not block."""
        content = (
            "## Findings\n"
            "- Confirmed: No semantic, security, or maintainability defects were found.\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        # The bullet parses as a finding (verdict="Confirmed", severity=None) but
        # _is_no_findings_line correctly identifies it as a no-findings line.
        self.assertFalse(has_blocking_review_findings(content, "low"))

    def test_no_severity_no_canonical_fields_real_issue_blocks(self):
        """P0/F2: A verdict-only finding without severity AND no canonical fields,
        where the prose describes a real issue, still blocks."""
        content = (
            "## Findings\n"
            "- Confirmed: SQL injection found in the auth module.\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertTrue(has_blocking_review_findings(content, "medium"))

    def test_no_severity_but_has_canonical_fields_and_contradiction_blocks(self):
        """F2: severity=None + canonical fields + contradiction → blocks."""
        content = (
            "## Findings\n"
            "- Confirmed: Module import is invalid although tests pass\n"
            "**Location:** claude_auto_review/state/reviews/matching.py:7\n\n"
            "## Verdict\n"
            "1 issue found. Claude must address all findings before stopping.\n"
        )
        self.assertTrue(has_blocking_review_findings(content, "medium"))

    def test_f2_severity_none_with_canonical_fields_no_contradiction_skips(self):
        """F2 regression: severity=None + canonical fields + no contradiction →
        treat as ambiguous (skip), do NOT fall back to has_review_findings
        which would re-introduce 'confirmed always blocks'."""
        content = (
            "## Findings\n"
            "- Confirmed: Module import is valid; naming follows conventions\n"
            "  **Location:** claude_auto_review/state/reviews/matching.py:7\n"
            "  **Rule:** import-conventions\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        # Has canonical fields but no severity and no contradiction — should skip.
        self.assertFalse(has_blocking_review_findings(content, "medium"))

    def test_f2_severity_none_with_canonical_fields_and_contradiction_blocks(self):
        """F2 regression: severity=None + canonical fields + contradiction → blocks."""
        content = (
            "## Findings\n"
            "- Confirmed: Module import is invalid however a security bypass exists\n"
            "  **Location:** claude_auto_review/state/reviews/matching.py:7\n"
            "  **Rule:** import-security\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertTrue(has_blocking_review_findings(content, "medium"))

    def test_f2_severity_none_no_canonical_fields_prose_noise_skips(self):
        """F2 regression: severity=None + no canonical fields + no-findings prose → skip."""
        content = (
            "## Findings\n"
            "- Confirmed: No semantic, security, or maintainability defects were found.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertFalse(has_blocking_review_findings(content, "low"))

    def test_f3_severity_none_bracket_heading_is_unrecognized(self):
        """F3 regression: [None] in a bracket heading is not a valid severity;
        _normalize_severity('None') returns None so the bracket parser marks it
        as <unrecognized> via the single-word label fallback."""
        content = (
            "## Findings\n"
            "### 1. [None] Advisory note\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        findings = parse_review_findings(content)
        # [None] in brackets is a single-word non-severity → <unrecognized>
        self.assertEqual(findings[0].severity, "<unrecognized>")

    def test_f3_canonical_severity_none_field_is_absent(self):
        """F3 regression: **Severity: None** in a canonical field → treated as
        no severity assigned (normalized to None), not <unrecognized>."""
        content = (
            "## Findings\n"
            "### 1. Advisory note\n"
            "**Verdict:** Confirmed\n"
            "**Severity:** None\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        findings = parse_review_findings(content)
        self.assertIsNone(findings[0].severity)

    def test_f3_severity_unrecognized_value_gets_sentinel(self):
        """F3 regression: unrecognized severity value gets sentinel, not dropped."""
        content = (
            "## Findings\n"
            "### 1. [not-queue] Mislabelled finding\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        findings = parse_review_findings(content)
        # "not-queue" is not a valid severity → sentinel <unrecognized>
        self.assertEqual(findings[0].severity, "<unrecognized>")
        # Unrecognized severity at medium threshold should block (treated as medium).
        self.assertTrue(has_blocking_review_findings(content, "medium"))


if __name__ == "__main__":
    unittest.main()
