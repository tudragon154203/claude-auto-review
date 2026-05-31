import unittest

from claude_auto_review.state.reviews.detection import has_review_findings


class TestHasReviewFindings(unittest.TestCase):
    def test_detects_real_findings_after_clean_declaration(self):
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

    def test_detects_no_findings_summary_prose(self):
        content = (
            "## Findings\n"
            "No semantic bugs, security issues, or maintainability concerns identified.\n"
            "All code follows project conventions.\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_detects_real_findings_despite_negation_prefix(self):
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

    def test_detects_none_line_as_no_findings(self):
        content = (
            "## Findings\n"
            "None. The new test is well-structured and the assertions cover the intended behavior.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_ignores_notes_section(self):
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

    def test_detects_real_findings_despite_notes(self):
        content = (
            "## Findings\n"
            "### 1. Unused variable\n"
            "**Verdict:** Confirmed\n\n"
            "**Notes:** Minor observation only.\n\n"
            "## Verdict\n"
            "1 issues found. Claude must address all findings before stopping.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_detects_no_bugs_line(self):
        content = "## Findings\nNo bugs found.\n\n## Verdict\nClean - no issues found.\n"
        self.assertFalse(has_review_findings(content))

    def test_detects_clean_negations(self):
        cases = [
            "No concerns identified.",
            "No findings. The change is a mechanical visibility rename.",
            "No semantic issues found.",
        ]
        for finding_line in cases:
            with self.subTest(finding_line=finding_line):
                content = f"## Findings\n{finding_line}\n\n## Verdict\nClean - no issues found.\n"
                self.assertFalse(has_review_findings(content))

    def test_detects_no_issues_found_in_test_file(self):
        content = "## Findings\nNo issues found in the test file.\n\n## Verdict\nClean - no issues found.\n"
        self.assertFalse(has_review_findings(content))

    def test_rejects_explicit_contradiction_after_no_issues_line(self):
        content = (
            "## Findings\n"
            "No issues found in the test file, but the regression remains.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_detects_mixed_prose_with_placeholder_line(self):
        content = (
            "## Findings\n"
            "Sensitive data logged to console.\n\n"
            "Completed review from /tmp/prompt.md\n\n"
            "## Verdict\n"
            "Not Clean - security issue found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_basic_semantic_review_only_note(self):
        content = (
            "## Findings\n"
            "**Note:** basic semantic review only, no semantic issues found.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_no_project_rules_file_note(self):
        content = (
            "## Findings\n"
            "**Note:** no project rules file found, basic review only.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_generic_note_not_no_findings(self):
        content = "## Findings\n**Note:** some minor observation.\n\n## Verdict\nClean - no issues found.\n"
        self.assertTrue(has_review_findings(content))

    def test_note_with_contradiction(self):
        content = (
            "## Findings\n"
            "**Note:** basic semantic review only, but a bug exists.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        # Note with contradiction marker must not be treated as no-findings
        self.assertTrue(has_review_findings(content))

    def test_note_with_semantic_review_only_stays_clean(self):
        content = (
            "## Findings\n"
            "**Note:** basic semantic review only, no semantic issues found.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_with_prose_contradiction(self):
        content = (
            "## Findings\nNo issues found, but an edge case remains.\n\n## Verdict\nClean - no issues found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_no_findings_prefix_with_verb(self):
        content = "## Findings\nNo issues found were identified.\n\n## Verdict\nClean - no issues found.\n"
        self.assertFalse(has_review_findings(content))

    def test_strict_prefix_no_punct(self):
        content = "## Findings\nclean\n\n## Verdict\nClean - no issues found.\n"
        self.assertFalse(has_review_findings(content))

    def test_unqualified_prefix_no_remainder(self):
        content = (
            "## Findings\nCompleted review from /tmp/prompt.md\n\n## Verdict\nClean - no issues found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_unqualified_prefix_with_contradiction(self):
        content = (
            "## Findings\n"
            "Completed review from /tmp/prompt.md but issues remain.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_bullet_confirmed_no_defects_is_clean(self):
        """'- Confirmed: No defects found' prose bullet must not trigger findings."""
        content = (
            "## Findings\n"
            "- Confirmed: No semantic, security, or maintainability defects were found.\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_bullet_skipped_is_clean(self):
        """'- Skipped: ...' prose bullet must not trigger findings."""
        content = (
            "## Findings\n"
            "- Skipped: `_get_prompt.py` is not present in the snapshot.\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_mixed_skipped_and_confirmed_no_issues(self):
        """Mixed skipped + confirmed-no-issues bullets must both be clean."""
        content = (
            "## Findings\n"
            "- Skipped: `_get_prompt.py` is referenced but does not exist in the workspace.\n"
            "- Confirmed: No semantic, security, or maintainability defects were found.\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_bullet_confirmed_real_issue_is_finding(self):
        """'- Confirmed: SQL injection found' must still count as a finding."""
        content = (
            "## Findings\n"
            "- Confirmed: SQL injection found in the auth module.\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_bullet_skipped_real_issue_is_finding(self):
        """'- Skipped: SQL injection found' with no file-unavailability reason must count as a finding."""
        content = (
            "## Findings\n"
            "- Skipped: SQL injection found in the auth module.\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_bullet_skipped_ambiguous_phrase_without_qualifier_is_clean(self):
        """'- Skipped:' bullets are always clean — skipped findings never block."""
        content = (
            "## Findings\n"
            "- Skipped: auth check not present in module.\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_bullet_skipped_contradictory_prose_is_finding(self):
        """'not present in workspace, but SQL injection ...' must count as a finding despite no-content phrase."""
        content = (
            "## Findings\n"
            "- Skipped: file not present in workspace, but SQL injection found in auth.\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertTrue(has_review_findings(content))


if __name__ == "__main__":
    unittest.main()
