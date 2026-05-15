import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.state.models import EditRecord, ReviewMetadata
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.finalize import finalize_review_stop
from claude_auto_review.stop.orchestration.resolution import StopFlowResolution


def _mk_review(reviewId: str = "r1") -> ReviewMetadata:
    return ReviewMetadata(
        timestamp="2026-05-11T10:00:00+07:00",
        reviewId=reviewId,
        reviewPath="/fake/r.md",
        files=[],
        clientId="c",
        status="pending",
    )


def _ctx(project_root=Path("/fake"), client_id="c", settings=None, payload=None):
    return RuntimeContext(
        project_root=project_root,
        client_id=client_id,
        settings=settings if settings is not None else {},
        payload=payload if payload is not None else {},
    )


class TestFinalizeReviewStop(unittest.TestCase):
    resolution = StopFlowResolution(
        state=[], unreviewed=[],
        review=_mk_review("r1"),
    )

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", return_value="Clean")
    def test_completed_no_remaining_returns_0(self, mock_verdict, mock_covered, mock_classify):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 0)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", return_value="Has findings")
    def test_completed_with_findings_returns_2(self, mock_verdict, mock_block, mock_covered, mock_classify):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize.attempt_stop_autocomplete", return_value=True)
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict")
    def test_pending_review_autocomplete_clean_returns_0(self, mock_verdict, mock_auto, mock_prompt, mock_covered, mock_classify):
        mock_verdict.return_value = "Pending."
        mock_prompt.return_value = "Complete the review"
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 0)

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.finalize.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize.attempt_stop_autocomplete", return_value=False)
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", side_effect=["Pending.", "Not clean."])
    def test_autocomplete_completed_with_findings_blocks_completion(self, mock_verdict, mock_auto, mock_prompt, mock_block, mock_covered, mock_classify):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize.attempt_stop_autocomplete", return_value=False)
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", side_effect=["Pending.", None])
    def test_autocomplete_returns_2_on_pending(self, mock_verdict, mock_auto, mock_prompt, mock_covered, mock_classify):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.finalize._review_has_completed_artifact", side_effect=[False, True])
    @patch("claude_auto_review.stop.orchestration.finalize.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize.attempt_stop_autocomplete", return_value=False)
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", side_effect=["Pending.", None])
    def test_autocomplete_with_non_placeholder_review_blocks_with_findings(
        self, mock_verdict, mock_auto, mock_prompt, mock_completed, mock_block, mock_covered, mock_classify
    ):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)
        mock_block.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", return_value=None)
    def test_missing_review_file_blocks(self, mock_verdict, mock_covered, mock_classify):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
