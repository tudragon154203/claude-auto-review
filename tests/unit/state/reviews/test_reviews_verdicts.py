import unittest
from pathlib import Path

from claude_auto_review.state.reviews.completion import (
    is_completed_review_content,
    is_placeholder_review_content,
    is_review_clean,
    is_review_clean_content,
    is_review_complete,
)
from claude_auto_review.state.reviews.findings import (
    has_blocking_review_findings,
    has_review_findings,
    parse_review_findings,
)
from claude_auto_review.state.reviews.normalization import normalize_review_verdict_content
from claude_auto_review.state.reviews.review_text import extract_review_verdict_text

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


if __name__ == "__main__":
    unittest.main()
