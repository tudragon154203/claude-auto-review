import tempfile
import unittest
from pathlib import Path

from claude_auto_review.state.models import ReviewMetadata
from claude_auto_review.stop.orchestration.finalize import _review_artifact_state


def _mk_review(reviewId: str = "r1", reviewPath: str = "/fake/r.md") -> ReviewMetadata:
    return ReviewMetadata(
        timestamp="2026-05-11T10:00:00+07:00",
        reviewId=reviewId,
        reviewPath=reviewPath,
        files=[],
        clientId="c",
        status="pending",
    )


class TestReviewArtifactState(unittest.TestCase):

    def test_review_artifact_state_detects_clean_complete_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "review.md"
            review_path.write_text("## Verdict\nClean\n", encoding="utf-8")

            artifact_state = _review_artifact_state(review_path)

        self.assertEqual(artifact_state.status, "complete_clean")
        self.assertEqual(artifact_state.verdict, "Clean")

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

            artifact_state = _review_artifact_state(review_path)

            self.assertEqual(artifact_state.status, "complete_clean")
            self.assertNotIn(
                "Findings present",
                review_path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
