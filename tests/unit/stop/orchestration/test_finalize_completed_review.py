import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.config.constants import EXIT_REVIEW_FAILED, EXIT_STOP_APPROVED
from claude_auto_review.config.models import PluginSettings
from claude_auto_review.state.models import ReviewMetadata
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.finalize import finalize_review_stop
from claude_auto_review.stop.orchestration.resolution import FinalizeAction, StopFlowResolution


def _mk_review(reviewId: str = "r1", reviewPath: str = "/fake/r.md") -> ReviewMetadata:
    return ReviewMetadata(
        timestamp="2026-05-11T10:00:00+07:00",
        reviewId=reviewId,
        reviewPath=reviewPath,
        files=[],
        clientId="c",
        status="pending",
    )


def _ctx(project_root=Path("/fake"), client_id="c", settings=None, payload=None):
    return RuntimeContext(
        project_root=project_root,
        client_id=client_id,
        settings=settings or PluginSettings(),
        payload=payload if payload is not None else {},
    )


class TestFinalizeCompletedReview(unittest.TestCase):
    def setUp(self):
        self.resolution = StopFlowResolution(
            state=[],
            unreviewed=[],
            review=_mk_review("r1"),
        )

    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.apply_completed_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.classify_review_artifact_state")
    @patch("claude_auto_review.stop.orchestration.finalize.approve_response")
    @patch("claude_auto_review.stop.orchestration.finalize.log_event")
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.log_event")
    def test_completed_no_remaining_returns_0(self, mock_plan_log, mock_log, mock_approve, mock_classify, mock_apply, mock_covered):
        mock_classify.return_value.status = "complete_clean"
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, EXIT_STOP_APPROVED)
        mock_approve.assert_called_once_with("Claude Auto Review: review r1 clean, all files covered")
        mock_plan_log.assert_any_call(
            Path("/fake"),
            "stop_approved",
            client_id="c",
            reason=FinalizeAction.APPROVED,
            reviewId="r1",
        )

    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.record_completed_review")
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.finalize.classify_review_artifact_state")
    def test_completed_with_findings_returns_2(self, mock_classify, mock_block, mock_record, mock_covered):
        mock_classify.return_value.status = "complete_findings"
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, EXIT_REVIEW_FAILED)
        mock_block.assert_called_once()
        mock_record.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.apply_completed_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.approve_response")
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.block_completed_review_findings")
    def test_completed_clean_verdict_with_low_findings_approves_at_default_threshold(
        self, mock_block, mock_approve, mock_apply, mock_covered
    ):
        # _load_and_ensure_normalized_review is intentionally NOT mocked so the real
        # normalization pipeline runs against the temp file, exercising
        # has_blocking_review_findings end-to-end through finalize_review_stop.
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            review_dir = project_root / "fake"
            review_dir.mkdir(parents=True, exist_ok=True)
            review_path = review_dir / "r.md"
            review_path.write_text(
                "## Findings\n"
                "### [Low] Unused import\n"
                "**Verdict:** Confirmed\n\n"
                "## Verdict\n"
                "Clean - no issues found. Claude may stop.\n",
                encoding="utf-8",
            )
            resolution = StopFlowResolution(state=[], unreviewed=[], review=_mk_review("r1", "fake/r.md"))
            result = finalize_review_stop(_ctx(project_root=project_root), resolution)
            self.assertEqual(result, EXIT_STOP_APPROVED)
            mock_block.assert_not_called()
            mock_apply.assert_called_once()
            mock_approve.assert_called_once_with("Claude Auto Review: review r1 clean, all files covered")
            self.assertNotIn(
                "Findings present. Claude must address all findings before stopping.",
                review_path.read_text(encoding="utf-8"),
            )

    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.record_completed_review")
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.block_completed_review_findings")
    def test_completed_clean_verdict_with_medium_findings_blocks_at_default_threshold(
        self, mock_block, mock_record, mock_covered
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            review_dir = project_root / "fake"
            review_dir.mkdir(parents=True, exist_ok=True)
            review_path = review_dir / "r.md"
            review_path.write_text(
                "## Findings\n"
                "### 1. [Medium] Unused import\n"
                "**Verdict:** Confirmed\n\n"
                "## Verdict\n"
                "Clean - no issues found. Claude may stop.\n",
                encoding="utf-8",
            )
            resolution = StopFlowResolution(state=[], unreviewed=[], review=_mk_review("r1", "fake/r.md"))
            result = finalize_review_stop(_ctx(project_root=project_root), resolution)
            self.assertEqual(result, EXIT_REVIEW_FAILED)
            mock_record.assert_called_once()
            mock_block.assert_called_once()


if __name__ == "__main__":
    unittest.main()
