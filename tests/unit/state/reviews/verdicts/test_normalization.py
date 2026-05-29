import unittest
from unittest.mock import patch

from claude_auto_review.state.reviews.findings import has_blocking_review_findings
from claude_auto_review.state.reviews.normalization import normalize_review_verdict_content


class TestHasBlockingReviewFindingsThresholds(unittest.TestCase):
    def _review(self, findings_text, verdict="1 issues found. Claude must address all findings before stopping."):
        return f"## Findings\n{findings_text}\n\n## Verdict\n{verdict}\n"

    def test_confirmed_low_does_not_block_at_medium(self):
        content = self._review("### 1. [Low] Nit\n**Verdict:** Confirmed\n")
        self.assertFalse(has_blocking_review_findings(content, "medium"))

    def test_confirmed_low_blocks_at_low(self):
        content = self._review("### 1. [Low] Nit\n**Verdict:** Confirmed\n")
        self.assertTrue(has_blocking_review_findings(content, "low"))

    def test_confirmed_medium_blocks_at_medium(self):
        content = self._review("### 1. [Medium] Bug\n**Verdict:** Confirmed\n")
        self.assertTrue(has_blocking_review_findings(content, "medium"))

    def test_confirmed_high_does_not_block_at_critical(self):
        content = self._review("### 1. [High] Bug\n**Verdict:** Confirmed\n")
        self.assertFalse(has_blocking_review_findings(content, "critical"))

    def test_skipped_finding_never_blocks(self):
        content = self._review("### 1. [Critical] Bug\n**Verdict:** Skipped\n")
        self.assertFalse(has_blocking_review_findings(content, "low"))

    def test_unconfirmed_finding_blocks(self):
        content = self._review("### 1. [Low] Nit\n**Verdict:** Maybe\n")
        self.assertTrue(has_blocking_review_findings(content, "critical"))

    def test_finding_with_no_verdict_blocks(self):
        content = self._review("### 1. [Low] Nit\nSome details.\n")
        self.assertTrue(has_blocking_review_findings(content, "critical"))

    def test_finding_with_unknown_severity_blocks(self):
        content = self._review("### 1. [Unknown] Weird\n**Verdict:** Confirmed\n")
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


class TestNormalizeReviewVerdictContent(unittest.TestCase):
    def test_none_content_returns_none(self):
        self.assertIsNone(normalize_review_verdict_content(None))

    def test_empty_content_returns_unchanged(self):
        self.assertEqual(normalize_review_verdict_content(""), "")

    def test_no_verdict_section_unchanged(self):
        content = "## Findings\nNo issues.\n"
        self.assertEqual(normalize_review_verdict_content(content), content)

    def test_no_findings_section_unchanged(self):
        content = "## Verdict\nClean.\n"
        self.assertEqual(normalize_review_verdict_content(content), content)

    def test_client_id_none_no_crash(self):
        content = "## Findings\nNo issues.\n\n## Verdict\nFindings present.\n"
        normalized = normalize_review_verdict_content(content, client_id=None)
        self.assertIn("Clean - no issues found", normalized)

    def test_consistent_clean_verdict_unchanged(self):
        content = "## Findings\nNo issues found.\n\n## Verdict\nClean - no issues found. Claude may stop.\n"
        normalized = normalize_review_verdict_content(content)
        self.assertEqual(normalized, content)

    def test_consistent_blocking_verdict_unchanged(self):
        content = (
            "## Findings\n### 1. [Medium] Bug\n**Verdict:** Confirmed\n\n"
            "## Verdict\n1 issues found. Claude must address all findings before stopping.\n"
        )
        normalized = normalize_review_verdict_content(content)
        self.assertEqual(normalized, content)

    @patch("claude_auto_review.state.reviews.normalization.log_event")
    def test_logs_event_when_rewriting_clean_to_findings(self, mock_log):
        content = (
            "## Findings\n### 1. [Medium] Bug\n**Verdict:** Confirmed\n\n"
            "## Verdict\nClean - no issues found. Claude may stop.\n"
        )
        rewritten = normalize_review_verdict_content(content, client_id="c1")
        self.assertIn("Findings present", rewritten)
        self.assertNotIn("Clean - no issues found. Claude may stop.", rewritten)
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args[1]
        self.assertEqual(call_kwargs["original_verdict"], "Clean - no issues found. Claude may stop.")
        self.assertIn("Findings present", call_kwargs["normalized_verdict"])

    @patch("claude_auto_review.state.reviews.normalization.log_event")
    def test_logs_event_when_rewriting_findings_to_clean(self, mock_log):
        content = (
            "## Findings\nNo issues found.\n\n"
            "## Verdict\nFindings present. Claude must address all findings before stopping.\n"
        )
        rewritten = normalize_review_verdict_content(content, client_id="c1")
        self.assertIn("Clean - no issues found", rewritten)
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args[1]
        self.assertIn("Findings present", call_kwargs["original_verdict"])
        self.assertIn("Clean - no issues found", call_kwargs["normalized_verdict"])


if __name__ == "__main__":
    unittest.main()
