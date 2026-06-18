import tempfile
import unittest
from pathlib import Path

from claude_auto_review.stop.orchestration.finalize.review_artifact_evaluator import (
    _project_root_from_review_path,
    classify_review_artifact,
)


class TestReviewArtifactState(unittest.TestCase):
    def test_review_artifact_state_detects_clean_complete_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "review.md"
            review_path.write_text("## Verdict\nClean\n", encoding="utf-8")

            artifact_state = classify_review_artifact(review_path)

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

            artifact_state = classify_review_artifact(review_path)

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

            artifact_state = classify_review_artifact(review_path)

            self.assertEqual(artifact_state.status, "complete_clean")
            self.assertNotIn(
                "Findings present",
                review_path.read_text(encoding="utf-8"),
            )


class TestProjectRootFromReviewPath(unittest.TestCase):
    def test_finds_project_root_containing_claude_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "my-project"
            clients_dir = (
                project_root
                / ".claude"
                / "claude-auto-review"
                / "clients"
                / "client-123"
            )
            reviews_dir = clients_dir / "reviews"
            reviews_dir.mkdir(parents=True)
            (project_root / ".claude").mkdir(parents=True, exist_ok=True)
            review_path = reviews_dir / "review-abc.md"
            review_path.write_text("## Verdict\nClean\n", encoding="utf-8")

            result = _project_root_from_review_path(review_path)

            self.assertEqual(result, project_root.resolve())

    def test_skips_intermediate_claude_auto_review_subdir(self):
        """Must return the project root, not the .claude/claude-auto-review subdir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "my-project"
            clients_dir = (
                project_root
                / ".claude"
                / "claude-auto-review"
                / "clients"
                / "client-456"
            )
            reviews_dir = clients_dir / "reviews"
            reviews_dir.mkdir(parents=True)
            (project_root / ".claude").mkdir(parents=True, exist_ok=True)
            review_path = reviews_dir / "review-def.md"
            review_path.write_text("## Verdict\nClean\n", encoding="utf-8")

            result = _project_root_from_review_path(review_path)

            self.assertEqual(result, project_root.resolve())
            self.assertNotEqual(result, (project_root / ".claude").resolve())
            self.assertNotEqual(
                result,
                (project_root / ".claude" / "claude-auto-review").resolve(),
            )


if __name__ == "__main__":
    unittest.main()
