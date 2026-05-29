import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestFinalizePendingReview(unittest.TestCase):
    def setUp(self):
        self.resolution = StopFlowResolution(
            state=[],
            unreviewed=[],
            review=_mk_review("r1"),
        )

    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.apply_completed_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.classify_review_artifact_state")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="output_written"))
    @patch("claude_auto_review.stop.orchestration.finalize.approve_response")
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.log_event")
    @patch("claude_auto_review.stop.orchestration.finalize.log_event")
    def test_pending_review_autocomplete_clean_returns_0(
        self, mock_log, mock_plan_log, mock_approve, mock_auto, mock_prompt, mock_classify, mock_apply, mock_covered
    ):
        mock_classify.side_effect = [
            MagicMock(status="pending"),
            MagicMock(status="complete_clean"),
        ]
        mock_prompt.return_value = "Complete the review"
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
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.apply_completed_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.classify_review_artifact_state")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    @patch("claude_auto_review.stop.orchestration.finalize.approve_response")
    def test_pending_review_autocomplete_clean_file_returns_0(
        self, mock_approve, mock_auto, mock_prompt, mock_classify, mock_apply, mock_covered
    ):
        mock_classify.side_effect = [
            MagicMock(status="pending"),
            MagicMock(status="complete_clean"),
        ]
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, EXIT_STOP_APPROVED)
        mock_apply.assert_called_once()
        mock_approve.assert_called_once_with("Claude Auto Review: review r1 clean, all files covered")

    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.record_completed_review")
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.finalize.classify_review_artifact_state")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    def test_autocomplete_completed_with_findings_blocks_completion(
        self, mock_auto, mock_prompt, mock_classify, mock_block, mock_record, mock_covered
    ):
        mock_classify.side_effect = [
            MagicMock(status="pending"),
            MagicMock(status="complete_findings"),
        ]
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, EXIT_REVIEW_FAILED)
        mock_block.assert_called_once()
        mock_record.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.block_pending_review")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    @patch("claude_auto_review.stop.orchestration.finalize.classify_review_artifact_state")
    def test_autocomplete_returns_2_on_pending(self, mock_classify, mock_auto, mock_prompt, mock_block_pending, mock_covered):
        mock_classify.side_effect = [MagicMock(status="pending"), MagicMock(status="pending")]
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, EXIT_REVIEW_FAILED)

    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.record_completed_review")
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.finalize.classify_review_artifact_state")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    def test_autocomplete_with_non_placeholder_review_blocks_with_findings(
        self, mock_auto, mock_prompt, mock_classify, mock_block, mock_record, mock_covered
    ):
        mock_classify.side_effect = [
            MagicMock(status="pending"),
            MagicMock(status="complete_findings"),
        ]
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, EXIT_REVIEW_FAILED)
        mock_block.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.block_pending_review")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize_autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    @patch("claude_auto_review.stop.orchestration.finalize.classify_review_artifact_state")
    def test_pending_review_blocks(self, mock_classify, mock_auto, mock_prompt, mock_block_pending, mock_covered):
        mock_classify.side_effect = [MagicMock(status="pending"), MagicMock(status="pending")]
        mock_block_pending.return_value = 2
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, EXIT_REVIEW_FAILED)
        mock_block_pending.assert_called_once()


if __name__ == "__main__":
    unittest.main()
