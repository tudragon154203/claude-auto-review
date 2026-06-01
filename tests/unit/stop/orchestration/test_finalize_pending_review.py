import unittest
from unittest.mock import MagicMock, patch

from tests.support_paths import FAKE_ROOT

from claude_auto_review.config.constants.exit_codes import EXIT_REVIEW_FAILED, EXIT_STOP_APPROVED
from claude_auto_review.config.settings.models import PluginSettings
from claude_auto_review.state.records.review import ReviewMetadata
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.orchestration.deps import build_default_eval_deps
from claude_auto_review.stop.orchestration.finalize.core import finalize_review_stop
from claude_auto_review.stop.orchestration.types.resolution import FinalizeAction, ReviewResolution


def _mk_review(reviewId: str = "r1", reviewPath: str = "/fake/r.md") -> ReviewMetadata:
    return ReviewMetadata(
        timestamp="2026-05-11T10:00:00+07:00",
        reviewId=reviewId,
        reviewPath=reviewPath,
        files=[],
        clientId="c",
        status="pending",
    )


def _ctx(project_root=FAKE_ROOT, client_id="c", settings=None, payload=None):
    return RuntimeContext(
        project_root=project_root,
        client_id=client_id,
        settings=settings or PluginSettings(),
        payload=payload if payload is not None else {},
    )


def _mock_emitter():
    return MagicMock()


class TestFinalizePendingReview(unittest.TestCase):
    def setUp(self):
        self.resolution = ReviewResolution(
            state=[],
            unreviewed=[],
            review=_mk_review("r1"),
        )
        self.emitter = _mock_emitter()

    @patch("claude_auto_review.stop.orchestration.finalize.core.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.plan_executor.apply_completed_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.review_artifact_evaluator.classify_review_artifact")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="output_written"))
    @patch("claude_auto_review.stop.orchestration.finalize.plan_executor.log_event")
    def test_pending_review_autocomplete_clean_returns_0(
        self, mock_plan_log, mock_auto, mock_prompt, mock_classify, mock_apply, mock_covered
    ):
        mock_classify.side_effect = [
            MagicMock(status="pending"),
            MagicMock(status="complete_clean"),
        ]
        mock_prompt.return_value = "Complete the review"
        result = finalize_review_stop(_ctx(), self.resolution, deps=build_default_eval_deps(emitter=self.emitter))
        self.assertEqual(result, EXIT_STOP_APPROVED)
        self.emitter.approve.assert_called_once_with("Claude Auto Review: review r1 clean, all files covered")
        mock_plan_log.assert_any_call(
            FAKE_ROOT,
            "stop_approved",
            client_id="c",
            reason=FinalizeAction.APPROVED,
            reviewId="r1",
        )

    @patch("claude_auto_review.stop.orchestration.finalize.core.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.plan_executor.apply_completed_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.review_artifact_evaluator.classify_review_artifact")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    def test_pending_review_autocomplete_clean_file_returns_0(
        self, mock_auto, mock_prompt, mock_classify, mock_apply, mock_covered
    ):
        mock_classify.side_effect = [
            MagicMock(status="pending"),
            MagicMock(status="complete_clean"),
        ]
        result = finalize_review_stop(_ctx(), self.resolution, deps=build_default_eval_deps(emitter=self.emitter))
        self.assertEqual(result, EXIT_STOP_APPROVED)
        mock_apply.assert_called_once()
        self.emitter.approve.assert_called_once_with("Claude Auto Review: review r1 clean, all files covered")

    @patch("claude_auto_review.stop.orchestration.finalize.core.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.plan_executor.record_completed_review")
    @patch("claude_auto_review.stop.orchestration.finalize.plan_executor.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.finalize.review_artifact_evaluator.classify_review_artifact")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    def test_autocomplete_completed_with_findings_blocks_completion(
        self, mock_auto, mock_prompt, mock_classify, mock_block, mock_record, mock_covered
    ):
        mock_classify.side_effect = [
            MagicMock(status="pending"),
            MagicMock(status="complete_findings"),
        ]
        result = finalize_review_stop(_ctx(), self.resolution, deps=build_default_eval_deps(emitter=self.emitter))
        self.assertEqual(result, EXIT_REVIEW_FAILED)
        mock_block.assert_called_once()
        mock_record.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.core.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.core.block_pending_review")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    @patch("claude_auto_review.stop.orchestration.finalize.review_artifact_evaluator.classify_review_artifact")
    def test_autocomplete_returns_2_on_pending(self, mock_classify, mock_auto, mock_prompt, mock_block_pending, mock_covered):
        mock_classify.side_effect = [MagicMock(status="pending"), MagicMock(status="pending")]
        result = finalize_review_stop(_ctx(), self.resolution, deps=build_default_eval_deps(emitter=self.emitter))
        self.assertEqual(result, EXIT_REVIEW_FAILED)

    @patch("claude_auto_review.stop.orchestration.finalize.core.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.plan_executor.record_completed_review")
    @patch("claude_auto_review.stop.orchestration.finalize.plan_executor.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.finalize.review_artifact_evaluator.classify_review_artifact")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    def test_autocomplete_with_non_placeholder_review_blocks_with_findings(
        self, mock_auto, mock_prompt, mock_classify, mock_block, mock_record, mock_covered
    ):
        mock_classify.side_effect = [
            MagicMock(status="pending"),
            MagicMock(status="complete_findings"),
        ]
        result = finalize_review_stop(_ctx(), self.resolution, deps=build_default_eval_deps(emitter=self.emitter))
        self.assertEqual(result, EXIT_REVIEW_FAILED)
        mock_block.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.core.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.core.block_pending_review")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    @patch("claude_auto_review.stop.orchestration.finalize.review_artifact_evaluator.classify_review_artifact")
    def test_pending_review_blocks(self, mock_classify, mock_auto, mock_prompt, mock_block_pending, mock_covered):
        mock_classify.side_effect = [MagicMock(status="pending"), MagicMock(status="pending")]
        mock_block_pending.return_value = 2
        result = finalize_review_stop(_ctx(), self.resolution, deps=build_default_eval_deps(emitter=self.emitter))
        self.assertEqual(result, EXIT_REVIEW_FAILED)
        mock_block_pending.assert_called_once()


if __name__ == "__main__":
    unittest.main()
