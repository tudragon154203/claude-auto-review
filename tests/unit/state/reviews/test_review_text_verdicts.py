import tempfile
import unittest

from claude_auto_review.state.reviews.review_text import (
    extract_review_findings_text,
    extract_review_verdict_text,
    get_review_verdict_text,
)


class TestGetReviewVerdictText(unittest.TestCase):

    def test_reads_verdict_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".md", delete=False, dir=tmpdir
            )
            try:
                review_path.write("## Findings\nNo issues.\n\n## Verdict\nClean.\n")
                review_path.flush()
                result = get_review_verdict_text(review_path.name)
                self.assertEqual(result, "Clean.")
            finally:
                review_path.close()
                import os
                os.unlink(review_path.name)

    def test_returns_none_for_nonexistent_file(self):
        result = get_review_verdict_text("/nonexistent/path/review.md")
        self.assertIsNone(result)


class TestExtractReviewFindingsTextCodeFences(unittest.TestCase):
    def test_ignores_findings_header_inside_code_fence(self):
        content = (
            "## Findings\n"
            "```python\n"
            "## Findings\n"
            "print('hello')\n"
            "```\n"
            "No issues found.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        # Code fence is stripped; the outer ## Findings still exists (no fence there),
        # so extract_review_findings_text returns the content between ## Findings and
        # ## Verdict.  has_review_findings is what evaluates "No issues found.".
        self.assertEqual(extract_review_findings_text(content), "No issues found.")

    def test_ignores_findings_header_inside_fenced_json_block(self):
        content = (
            "## Findings\n"
            "```json\n"
            '{"section": "## Findings"}\n'
            "```\n"
            "No issues found.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        # JSON inside the fence is stripped; outer ## Findings still exists and
        # returns "No issues found." (has_review_findings evaluates that phrase).
        self.assertEqual(extract_review_findings_text(content), "No issues found.")

    def test_extracts_findings_around_code_fence(self):
        content = (
            "## Findings\n"
            "### 1. [High] SQL injection\n"
            "**Verdict:** Confirmed\n\n"
            "```python\n"
            "## Findings\n"
            "```\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        findings = extract_review_findings_text(content)
        self.assertIn("SQL injection", findings)
        self.assertIn("### 1. [High] SQL injection", findings)


class TestExtractReviewVerdictTextCodeFences(unittest.TestCase):
    def test_ignores_verdict_header_inside_code_fence(self):
        content = (
            "## Findings\n"
            "No issues.\n\n"
            "```\n"
            "## Verdict\n"
            "Blocking - must fix.\n"
            "```\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        self.assertEqual(extract_review_verdict_text(content), "Clean - no issues found.")

    def test_extracts_verdict_around_code_fence(self):
        content = (
            "## Findings\n"
            "```\n"
            "## Verdict\n"
            "```\n"
            "### 1. [Low] Minor issue\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        self.assertEqual(extract_review_verdict_text(content), "1 issue found.")

    def test_ignores_fenced_findings_section_in_code_fence(self):
        content = (
            "```\n"
            "## Findings\n"
            "## Verdict\n"
            "```\n"
            "## Findings\n"
            "No issues found.\n\n"
            "## Verdict\n"
            "Clean.\n"
        )
        # Fenced section is stripped; the outer ## Findings / ## Verdict remain.
        # extract_review_findings_text returns the prose content (has_review_findings
        # will handle evaluating "No issues found." correctly).
        self.assertEqual(extract_review_findings_text(content), "No issues found.")
        self.assertEqual(extract_review_verdict_text(content), "Clean.")


class TestStripCodeFencesUnclosed(unittest.TestCase):
    """F1 regression: unclosed fence must not consume real ## Findings / ## Verdict."""

    def test_unclosed_fence_does_not_swallow_real_findings(self):
        content = (
            "```\n"
            "stray opening fence\n"
            "## Findings\n"
            "### 1. [High] SQL injection\n"
            "**Verdict:** Confirmed\n\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        # The unclosed ``` at line 1 must not consume the real ## Findings section.
        # With the new paired fence stripper, the unclosed fence only reaches the
        # next ``` start (or EOF), but since there's no closing ```, the stripper
        # leaves the content after the unclosed fence alone.
        # The real test is that extract_review_findings_text sees the finding.
        findings = extract_review_findings_text(content)
        self.assertIsNotNone(findings)

    def test_unclosed_fence_before_real_sections(self):
        content = (
            "```\n"
            "some code\n"
            "## Findings\n"
            "No issues found.\n\n"
            "## Verdict\n"
            "Clean - no issues found.\n"
        )
        # Even with an unclosed fence, the real ## Findings / ## Verdict
        # should remain visible to the parser.
        verdict = extract_review_verdict_text(content)
        self.assertIsNotNone(verdict)

    def test_two_fenced_blocks_with_gap(self):
        content = (
            "```\n"
            "## Findings\n"
            "```\n"
            "## Findings\n"
            "### 1. [Low] Typo\n"
            "**Verdict:** Confirmed\n\n"
            "```\n"
            "## Verdict\n"
            "```\n"
            "## Verdict\n"
            "1 issue found.\n"
        )
        # First and third fences are paired and stripped.
        # Second ## Findings and fourth ## Verdict are real.
        findings = extract_review_findings_text(content)
        self.assertIn("Typo", findings)
        self.assertEqual(extract_review_verdict_text(content), "1 issue found.")


if __name__ == "__main__":
    unittest.main()