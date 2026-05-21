import unittest
from unittest.mock import patch

from claude_auto_review.state.reviews.completion import (
    is_review_clean_verdict,
    is_review_complete_verdict,
)
from claude_auto_review.state.reviews.findings import has_blocking_review_findings
from claude_auto_review.state.reviews.normalization import normalize_review_verdict_content
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
        content = (
            "## Findings\n"
            "Confirmed (clean)\n\n"
            "Extra notes that should be ignored.\n"
        )
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
            "## Findings\n### 1. [Low] Bug\n**Verdict:** Confirmed\n\n"
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
