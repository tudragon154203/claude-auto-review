import unittest
from pathlib import Path

from claude_auto_review.state.reviews.completion import (
    is_review_clean,
    is_review_clean_content,
)
from claude_auto_review.state.reviews.normalization import normalize_review_verdict_content

from tests.unit.state.support import StateTestCase


class TestReviewCleanVerdict(StateTestCase, unittest.TestCase):
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


class TestNormalizeCleanContradictions(unittest.TestCase):
    def test_normalize_keeps_clean_verdict_when_only_low_findings_exist(self):
        content = (
            "## Findings\n"
            "### [Low] Unused import\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        normalized = normalize_review_verdict_content(content)
        self.assertIn("Clean - no issues found. Claude may stop.", normalized)
        self.assertNotIn("Findings present", normalized)

    def test_normalize_rewrites_clean_verdict_when_medium_findings_exist(self):
        content = (
            "## Findings\n"
            "### [Medium] Bug\n"
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

    def test_normalize_keeps_clean_verdict_when_no_findings_exist(self):
        content = (
            "## Findings\n"
            "None. The new test is well-structured and the assertions cover the intended behavior.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertEqual(normalize_review_verdict_content(content), content)

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

    def test_normalize_keeps_blocking_verdict_when_medium_findings_exist(self):
        content = (
            "## Findings\n"
            "### 1. [Medium] Bug\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "Findings present. Claude must address all findings before stopping.\n"
        )
        normalized = normalize_review_verdict_content(content)
        self.assertIn("Findings present. Claude must address all findings before stopping.", normalized)

    def test_normalize_produces_consistent_clean_state(self):
        """After normalization, is_review_clean_content and has_review_findings should agree."""
        from claude_auto_review.state.reviews.findings import (
            has_blocking_review_findings,
            has_review_findings,
        )

        content_with_low_findings_and_clean_verdict = (
            "## Findings\n"
            "### [Low] Unused import\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        normalized = normalize_review_verdict_content(content_with_low_findings_and_clean_verdict)
        self.assertTrue(has_review_findings(normalized))
        self.assertFalse(has_blocking_review_findings(normalized))

        content_with_medium_findings_and_clean_verdict = (
            "## Findings\n"
            "### [Medium] Bug\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
        )
        normalized = normalize_review_verdict_content(content_with_medium_findings_and_clean_verdict)
        self.assertTrue(has_review_findings(normalized))
        self.assertTrue(has_blocking_review_findings(normalized))

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
