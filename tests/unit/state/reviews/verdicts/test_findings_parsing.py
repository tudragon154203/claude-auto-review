import unittest

from claude_auto_review.state.reviews.findings import (
    has_blocking_review_findings,
    has_review_findings,
    parse_review_findings,
)


class TestHasReviewFindings(unittest.TestCase):
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
        content = "## Findings\n" "### 1. [Critical] Safety issue\n" "**Verdict:** Skipped\n"
        self.assertFalse(has_blocking_review_findings(content, "info"))

    def test_has_blocking_review_findings_missing_severity_treated_as_info(self):
        """Missing severity is treated as info — should not block at medium+ threshold."""
        content = "## Findings\n" "### 1. Missing severity heading\n" "**Verdict:** Confirmed\n"
        self.assertFalse(has_blocking_review_findings(content, "medium"))
        self.assertTrue(has_blocking_review_findings(content, "info"))

    def test_has_blocking_review_findings_unparseable_confirmed_severity_treated_as_info(self):
        content = "## Findings\n" "### 1. [Mystery] Unexpected label\n" "**Verdict:** Confirmed\n"
        self.assertFalse(has_blocking_review_findings(content, "medium"))
        self.assertTrue(has_blocking_review_findings(content, "info"))

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
        content = "## Findings\n" "No bugs found.\n\n" "## Verdict\n" "Clean - no issues found.\n"
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_detects_clean_negations(self):
        cases = [
            "No concerns identified.",
            "No findings. The change is a mechanical visibility rename.",
            "No semantic issues found.",
        ]
        for finding_line in cases:
            with self.subTest(finding_line=finding_line):
                content = "## Findings\n" f"{finding_line}\n\n" "## Verdict\n" "Clean - no issues found.\n"
                self.assertFalse(has_review_findings(content))

    def test_has_review_findings_detects_no_issues_found_in_test_file(self):
        content = "## Findings\n" "No issues found in the test file.\n\n" "## Verdict\n" "Clean - no issues found.\n"
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

    def test_has_review_findings_basic_semantic_review_only_note(self):
        content = (
            "## Findings\n"
            "**Note:** basic semantic review only, no semantic issues found.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_no_project_rules_file_note(self):
        content = (
            "## Findings\n"
            "**Note:** no project rules file found, basic review only.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_generic_note_not_no_findings(self):
        content = "## Findings\n" "**Note:** some minor observation.\n\n" "## Verdict\n" "Clean - no issues found.\n"
        self.assertTrue(has_review_findings(content))

    def test_has_review_findings_note_with_contradiction(self):
        content = (
            "## Findings\n"
            "**Note:** basic semantic review only, but a bug exists.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        # Note special bypass: "basic semantic review only" makes it a "no findings" line
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_with_prose_contradiction(self):
        content = (
            "## Findings\n" "No issues found, but an edge case remains.\n\n" "## Verdict\n" "Clean - no issues found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_has_review_findings_no_findings_prefix_with_verb(self):
        content = "## Findings\n" "No issues found were identified.\n\n" "## Verdict\n" "Clean - no issues found.\n"
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_strict_prefix_no_punct(self):
        content = "## Findings\n" "clean\n\n" "## Verdict\n" "Clean - no issues found.\n"
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_unqualified_prefix_no_remainder(self):
        content = "## Findings\n" "Completed review from /tmp/prompt.md\n\n" "## Verdict\n" "Clean - no issues found.\n"
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_unqualified_prefix_with_contradiction(self):
        content = (
            "## Findings\n"
            "Completed review from /tmp/prompt.md but issues remain.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_parse_review_findings_heading_severity_from_numbered_heading(self):
        content = "## Findings\n### 1. [Critical] Issue\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "critical")

    def test_parse_review_findings_heading_severity_from_plain_heading(self):
        content = "## Findings\n### Major Problem\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertIsNone(findings[0].severity)

    def test_parse_review_findings_severity_fallback_to_field(self):
        content = "## Findings\n### [Unknown] Something\n**Severity:** High\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertEqual(findings[0].severity, "high")

    def test_parse_review_findings_normalizes_unknown_severity_to_none(self):
        content = "## Findings\n### [Mystery] Something\n**Verdict:** Confirmed\n"
        findings = parse_review_findings(content)
        self.assertIsNone(findings[0].severity)

    def test_parse_review_findings_ignores_non_finding_numbered_bold_lines(self):
        content = (
            "## Findings\n"
            "1. **Notes - not a finding**\n"
            "- Just prose, no verdict/severity.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings, [])

    def test_parse_review_findings_ignores_high_level_non_finding(self):
        content = (
            "## Findings\n"
            "1. **High-level architecture overview**\n"
            "- Just a description, not a finding.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings, [])

    def test_parse_review_findings_ignores_hyphenated_non_badge_labels(self):
        content = (
            "## Findings\n"
            "### [High-level] Architecture overview\n"
            "**Verdict:** Confirmed\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertIsNone(findings[0].severity)
        self.assertEqual(findings[0].verdict, "Confirmed")

    def test_parse_review_findings_ignores_hyphenated_inline_badges(self):
        content = (
            "## Findings\n"
            "1. **Confirmed - High-level architecture overview**\n"
            "- Just prose, not a severity-tagged finding.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings, [])

    def test_parse_review_findings_rejects_duplicate_confirmed_labels(self):
        content = (
            "## Findings\n"
            "1. **Confirmed Confirmed - Medium**\n"
            "- Duplicate verdict token should not be parsed as a finding.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(findings, [])


    def test_has_review_findings_bullet_confirmed_no_defects_is_clean(self):
        """'- Confirmed: No defects found' prose bullet must not trigger findings."""
        content = (
            "## Findings\n"
            "- Confirmed: No semantic, security, or maintainability defects were found.\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_bullet_skipped_is_clean(self):
        """'- Skipped: ...' prose bullet must not trigger findings."""
        content = (
            "## Findings\n"
            "- Skipped: `_get_prompt.py` is not present in the snapshot.\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_mixed_skipped_and_confirmed_no_issues(self):
        """Mixed skipped + confirmed-no-issues bullets must both be clean."""
        content = (
            "## Findings\n"
            "- Skipped: `_get_prompt.py` is referenced but does not exist in the workspace.\n"
            "- Confirmed: No semantic, security, or maintainability defects were found.\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        self.assertFalse(has_review_findings(content))

    def test_has_review_findings_bullet_confirmed_real_issue_is_finding(self):
        """'- Confirmed: SQL injection found' must still count as a finding."""
        content = (
            "## Findings\n"
            "- Confirmed: SQL injection found in the auth module.\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_has_review_findings_bullet_skipped_real_issue_is_finding(self):
        """'- Skipped: SQL injection found' with no file-unavailability reason must count as a finding."""
        content = (
            "## Findings\n"
            "- Skipped: SQL injection found in the auth module.\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_has_review_findings_bullet_skipped_ambiguous_phrase_without_qualifier_is_finding(self):
        """'not present' without 'in scope/snapshot/workspace' qualifier must not be treated as clean."""
        content = (
            "## Findings\n"
            "- Skipped: auth check not present in module.\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_has_review_findings_bullet_skipped_contradictory_prose_is_finding(self):
        """'not present in workspace, but SQL injection ...' must count as a finding despite no-content phrase."""
        content = (
            "## Findings\n"
            "- Skipped: file not present in workspace, but SQL injection found in auth.\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertTrue(has_review_findings(content))

    def test_parse_review_findings_accepts_codex_inline_confirmed_without_severity_when_fields_present(self):
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

    def test_has_blocking_review_findings_codex_inline_without_severity_uses_info_threshold(self):
        content = (
            "## Findings\n"
            "1. **Confirmed - Module import is invalid**\n"
            "**Location:** claude_auto_review/state/reviews/matching.py:7\n"
            "**Fix:** Import the correct symbol.\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found. Claude must address all findings before stopping.\n"
        )
        self.assertFalse(has_blocking_review_findings(content, "medium"))
        self.assertTrue(has_blocking_review_findings(content, "info"))

    def test_parse_review_findings_ignores_severity_field_in_prose(self):
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

    def test_parse_review_findings_ignores_field_labels_in_narrative_paragraphs(self):
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

    def test_parse_review_findings_severity_field_with_valid_level_starts_block(self):
        content = (
            "## Findings\n"
            "**Severity:** High\n"
            "**Location:** core.py:10\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found. Claude must address all findings before stopping.\n"
        )
        findings = parse_review_findings(content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "high")
        self.assertTrue(has_blocking_review_findings(content, "medium"))
