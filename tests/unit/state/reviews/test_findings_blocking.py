import unittest

from claude_auto_review.state.reviews.findings import has_blocking_review_findings


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

    def test_missing_severity_blocks(self):
        """Missing severity (no field at all) defaults to blocking threshold."""
        content = "## Findings\n### 1. Missing severity heading\n**Verdict:** Confirmed\n"
        self.assertTrue(has_blocking_review_findings(content, "medium"))

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

    def test_codex_inline_without_severity_uses_info_threshold(self):
        content = (
            "## Findings\n"
            "1. **Confirmed - Module import is invalid**\n"
            "**Location:** claude_auto_review/state/reviews/matching.py:7\n"
            "**Fix:** Import the correct symbol.\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found. Claude must address all findings before stopping.\n"
        )
        self.assertTrue(has_blocking_review_findings(content, "medium"))
        self.assertTrue(has_blocking_review_findings(content, "info"))


if __name__ == "__main__":
    unittest.main()
