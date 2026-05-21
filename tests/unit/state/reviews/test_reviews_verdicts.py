import unittest
from pathlib import Path

from claude_auto_review.config.utils.coercion import (
    coerce_bool,
    coerce_extensions,
    coerce_float,
    coerce_int,
)
from claude_auto_review.state.reviews.completion import (
    is_completed_review_content,
    is_placeholder_review_content,
    is_review_clean,
    is_review_clean_content,
    is_review_clean_verdict,
    is_review_complete,
    is_review_complete_verdict,
)
from claude_auto_review.state.reviews.findings import (
    has_blocking_review_findings,
    has_review_findings,
    parse_review_findings,
)
from claude_auto_review.state.reviews.normalization import normalize_review_verdict_content
from claude_auto_review.state.reviews.review_text import (
    extract_review_findings_text,
    extract_review_verdict_text,
    get_review_verdict_text,
)

from tests.unit.state.support import StateTestCase


class TestReviewsVerdicts(StateTestCase, unittest.TestCase):

    def test_returns_false_when_review_file_missing(self):
        project_root = self.temp_project()
        missing = project_root / "no-such-review.md"
        self.assertFalse(is_review_complete(missing))

    def test_returns_false_when_verdict_heading_missing(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("# Files\n\nSome notes\n", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_is_empty(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\n", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_equals_pending_uppercase(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nPending", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_equals_pending_with_period(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nPending.", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

    def test_returns_false_when_verdict_has_pending_word_in_context(self):
        # Substring checks would incorrectly fail; confirm we pass
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nAll issues addressed. No pending items.", encoding="utf-8")
        self.assertTrue(is_review_complete(path), "Should pass when 'pending' is just a word, not the literal placeholder")

    def test_returns_true_when_verdict_is_clean_message(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nClean - no issues found.", encoding="utf-8")
        self.assertTrue(is_review_complete(path))

    def test_is_review_clean_accepts_confirmed_clean_verdict(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nConfirmed (Clean) - no issues found.", encoding="utf-8")
        self.assertTrue(is_review_clean(path))

    def test_is_review_clean_rejects_not_clean_verdict(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nNot clean - fix src/app.ts.", encoding="utf-8")
        self.assertFalse(is_review_clean(path))

    def test_is_review_clean_rejects_clean_verdict_when_findings_exist(self):
        content = (
            "## Findings\n"
            "### [Low] Unused import\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        self.assertFalse(is_review_clean_content(content))

    def test_normalize_review_verdict_content_rewrites_clean_verdict_when_findings_exist(self):
        content = (
            "## Findings\n"
            "### [Low] Unused import\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        normalized = normalize_review_verdict_content(content)
        self.assertIn(
            "Findings present. Claude must address all findings before stopping.",
            normalized,
        )
        self.assertNotIn("Clean - no issues found. Claude may stop.", normalized)

    def test_normalize_review_verdict_content_keeps_clean_verdict_when_no_findings_exist(self):
        content = (
            "## Findings\n"
            "None. The new test is well-structured and the assertions cover the intended behavior.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertEqual(normalize_review_verdict_content(content), content)

    def test_is_review_clean_accepts_clean_verdict_with_none_findings_summary(self):
        content = (
            "## Findings\n"
            "None. The new test is well-structured and the assertions cover the intended behavior.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertTrue(is_review_clean_content(content))

    def test_is_review_clean_accepts_clean_verdict_with_note_preamble(self):
        content = (
            "## Findings\n"
            "**Note:** No project rules file found. Performing a basic semantic review only.\n\n"
            "Clean - no issues found. Claude may stop.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertTrue(is_review_clean_content(content))

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

    def test_returns_true_when_verdict_is_a_fixed_message(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nAll fixes applied.", encoding="utf-8")
        self.assertTrue(is_review_complete(path))

    def test_extract_review_verdict_text_uses_first_non_empty_line(self):
        content = "## Verdict\n\nClean - no issues found.\n\nExtra notes that should be ignored.\n"
        self.assertEqual(extract_review_verdict_text(content), "Clean - no issues found.")

    def test_extract_review_verdict_text_falls_back_to_findings_clean_line(self):
        content = (
            "## Findings\n"
            "Confirmed (clean)\n\n"
            "Extra notes that should be ignored.\n"
        )
        self.assertEqual(extract_review_verdict_text(content), "Confirmed (clean)")

    def test_marks_any_non_placeholder_review_content_as_completed(self):
        content = (
            "# Review rev-1\n\n"
            "## Files Reviewed\n"
            "- README.md (hash: abc123)\n\n"
            "## Findings\n"
            "1. **Low** - Flowchart misses a stop branch.\n"
        )
        self.assertTrue(is_completed_review_content(content))

    def test_marks_placeholder_review_content_as_not_completed(self):
        content = (
            "# Review rev-1\n\n"
            "## Files Reviewed\n"
            "- README.md (hash: abc123)\n\n"
            "## Findings\n\n"
            "No findings yet. This file is a placeholder until Claude completes the review.\n\n"
            "Pending. Claude must complete this review from /tmp/review-prompt.md.\n"
        )
        self.assertTrue(is_placeholder_review_content(content))
        self.assertFalse(is_completed_review_content(content))

    def test_is_case_insensitive(self):
        project_root = self.temp_project()
        path = project_root / "review.md"
        path.write_text("## Verdict\nPENDING", encoding="utf-8")
        self.assertFalse(is_review_complete(path))
        path.write_text("## Verdict\nPEnDInG.", encoding="utf-8")
        self.assertFalse(is_review_complete(path))

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

    def test_normalize_rewrites_false_positive_findings_present_to_clean(self):
        content = (
            "## Findings\n"
            "No issues found. The `pyproject.toml` is well-structured and complete.\n\n"
            "## Verdict\n"
            "Findings present. Claude must address all findings before stopping.\n"
        )
        normalized = normalize_review_verdict_content(content)
        self.assertIn("Clean - no issues found. Claude may stop.", normalized)
        self.assertNotIn("Findings present", normalized)

    def test_normalize_keeps_blocking_verdict_when_real_findings_exist(self):
        content = (
            "## Findings\n"
            "### 1. [Low] Unused import\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "Findings present. Claude must address all findings before stopping.\n"
        )
        normalized = normalize_review_verdict_content(content)
        self.assertIn("Findings present. Claude must address all findings before stopping.", normalized)
        self.assertTrue(has_review_findings(normalized))
        self.assertFalse(is_review_clean_content(normalized))

    def test_normalize_produces_consistent_clean_state(self):
        """After normalization, is_review_clean_content and has_review_findings should agree."""
        # Case: clean verdict but real findings exist -> should rewrite to findings present
        content_with_findings_and_clean_verdict = (
            "## Findings\n"
            "### [Low] Unused import\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        normalized = normalize_review_verdict_content(content_with_findings_and_clean_verdict)
        self.assertTrue(has_review_findings(normalized))
        self.assertFalse(is_review_clean_content(normalized))

        # Case: blocking verdict but no real findings -> should rewrite to clean
        content_with_no_findings_and_blocking_verdict = (
            "## Findings\n"
            "No semantic bugs, security issues, or maintainability concerns identified.\n\n"
            "## Verdict\n"
            "Findings present. Claude must address all findings before stopping.\n"
        )
        normalized = normalize_review_verdict_content(content_with_no_findings_and_blocking_verdict)
        self.assertFalse(has_review_findings(normalized))
        self.assertTrue(is_review_clean_content(normalized))


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


class TestHasBlockingReviewFindings(unittest.TestCase):
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


class TestIsReviewCleanContent(unittest.TestCase):
    def test_clean_verdict_no_findings(self):
        content = "## Findings\nNo issues found.\n\n## Verdict\nClean - no issues found. Claude may stop.\n"
        self.assertTrue(is_review_clean_content(content))

    def test_clean_verdict_with_findings_rejected(self):
        content = (
            "## Findings\n### 1. [Low] Nit\n**Verdict:** Confirmed\n\n"
            "## Verdict\nClean - no issues found. Claude may stop.\n"
        )
        self.assertFalse(is_review_clean_content(content))

    def test_blocking_verdict_rejected(self):
        content = (
            "## Findings\n### 1. [Medium] Bug\n**Verdict:** Confirmed\n\n"
            "## Verdict\n1 issues found. Claude must address all findings before stopping.\n"
        )
        self.assertFalse(is_review_clean_content(content))

    def test_none_returns_false(self):
        self.assertFalse(is_review_clean_content(None))

    def test_empty_returns_false(self):
        self.assertFalse(is_review_clean_content(""))

    def test_pending_verdict_returns_false(self):
        content = "## Verdict\nPending.\n"
        self.assertFalse(is_review_clean_content(content))


class TestCoercionHelpers(unittest.TestCase):
    def test_coerce_bool_none_returns_default(self):
        self.assertFalse(coerce_bool(None, False))
        self.assertTrue(coerce_bool(None, True))

    def test_coerce_bool_truthy(self):
        self.assertTrue(coerce_bool(1, False))
        self.assertTrue(coerce_bool("yes", False))
        self.assertTrue(coerce_bool([1], False))

    def test_coerce_bool_falsy(self):
        self.assertFalse(coerce_bool(0, True))
        self.assertFalse(coerce_bool("", True))
        self.assertFalse(coerce_bool([], True))

    def test_coerce_float_valid(self):
        self.assertAlmostEqual(coerce_float("3.14", 0.0), 3.14)
        self.assertAlmostEqual(coerce_float(2, 0.0), 2.0)

    def test_coerce_float_invalid_returns_default(self):
        self.assertAlmostEqual(coerce_float("bad", 1.0), 1.0)
        self.assertAlmostEqual(coerce_float(None, 5.0), 5.0)

    def test_coerce_int_valid(self):
        self.assertEqual(coerce_int("42", 0), 42)
        self.assertEqual(coerce_int(7, 0), 7)

    def test_coerce_int_float_returns_default(self):
        self.assertEqual(coerce_int("3.9", 0), 0)

    def test_coerce_int_invalid_returns_default(self):
        self.assertEqual(coerce_int("bad", 5), 5)
        self.assertEqual(coerce_int(None, 10), 10)

    def test_coerce_extensions_list(self):
        self.assertEqual(coerce_extensions([".py", ".ts"]), (".py", ".ts"))

    def test_coerce_extensions_tuple(self):
        self.assertEqual(coerce_extensions((".py",)), (".py",))

    def test_coerce_extensions_non_sequence_returns_empty(self):
        self.assertEqual(coerce_extensions(".py"), ())
        self.assertEqual(coerce_extensions(None), ())
        self.assertEqual(coerce_extensions(42), ())

    def test_coerce_extensions_converts_ints(self):
        self.assertEqual(coerce_extensions([1, 2]), ("1", "2"))


if __name__ == "__main__":
    unittest.main()
