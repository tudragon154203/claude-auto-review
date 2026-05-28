import tempfile
import unittest
from pathlib import Path

from claude_auto_review.stop.orchestration.review_artifact_evaluator import classify_review_artifact_state


class TestReviewArtifactState(unittest.TestCase):
    def test_review_artifact_state_detects_clean_complete_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "review.md"
            review_path.write_text("## Verdict\nClean\n", encoding="utf-8")

            artifact_state = classify_review_artifact_state(review_path)

        self.assertEqual(artifact_state.status, "complete_clean")
        self.assertEqual(artifact_state.verdict, "Clean")

    def test_clean_verdict_with_prose_confirmed_bullet_not_blocked(self):
        """A '- Confirmed: no issues' prose bullet must not block when verdict is Clean."""
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "review.md"
            review_path.write_text(
                "## Findings\n"
                "- Skipped: file not found in snapshot.\n"
                "- Confirmed: No semantic, security, or maintainability defects were found.\n\n"
                "## Verdict\n"
                "Clean - no issues found. Claude may stop.\n",
                encoding="utf-8",
            )

            artifact_state = classify_review_artifact_state(review_path)

        self.assertEqual(artifact_state.status, "complete_clean")

    def test_review_artifact_state_allows_below_threshold_findings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "review.md"
            review_path.write_text(
                "## Findings\n"
                "### [Low] Unused import\n"
                "**Verdict:** Confirmed\n\n"
                "## Verdict\n"
                "Clean - no issues found. Claude may stop.\n",
                encoding="utf-8",
            )

            artifact_state = classify_review_artifact_state(review_path)

            self.assertEqual(artifact_state.status, "complete_clean")
            self.assertNotIn(
                "Findings present",
                review_path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
