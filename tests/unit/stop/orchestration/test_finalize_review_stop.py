import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.resolution import StopFlowResolution
from claude_auto_review.stop.orchestration.finalize import finalize_review_stop


class TestFinalizeReviewStop(unittest.TestCase):
    resolution = StopFlowResolution(
        state=[], unreviewed=[],
        review={"reviewId": "r1", "reviewPath": "/fake/r.md"},
    )

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.is_review_clean", return_value=True)
    @patch("claude_auto_review.stop.orchestration.finalize.is_review_complete", return_value=True)
    @patch("claude_auto_review.stop.orchestration.finalize.apply_completed_review", return_value=[])
    def test_completed_no_remaining_returns_0(self, mock_apply, mock_complete, mock_clean, mock_covered, mock_classify):
        result = finalize_review_stop(Path("/fake"), "c", self.resolution, {}, {})
        self.assertEqual(result, 0)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.is_review_clean", return_value=True)
    @patch("claude_auto_review.stop.orchestration.finalize.is_review_complete", return_value=True)
    @patch("claude_auto_review.stop.orchestration.finalize.apply_completed_review", return_value=[{"file": "still.ts"}])
    def test_completed_with_remaining_returns_2(self, mock_apply, mock_complete, mock_clean, mock_covered, mock_classify):
        resolution = StopFlowResolution(
            state=[], unreviewed=[{"file": "still.ts", "hash": "1"}],
            review={"reviewId": "r1", "reviewPath": "/fake/r.md"},
        )
        result = finalize_review_stop(Path("/fake"), "c", resolution, {"last_assistant_message": "done"}, {"lastAssistantMessageClassifierEnabled": True})
        self.assertEqual(result, 2)
        mock_classify.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.attempt_stop_autocomplete", return_value=True)
    @patch("claude_auto_review.stop.orchestration.finalize.is_review_complete", return_value=False)
    def test_autocomplete_succeeds_returns_0(self, mock_complete, mock_auto, mock_covered, mock_classify):
        result = finalize_review_stop(Path("/fake"), "c", self.resolution, {"last_assistant_message": "done"}, {})
        self.assertEqual(result, 0)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.append_state")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.attempt_stop_autocomplete", return_value=False)
    @patch("claude_auto_review.stop.orchestration.finalize.is_review_complete", return_value=False)
    def test_autocomplete_fails_blocks_stop(self, mock_complete, mock_auto, mock_covered, mock_append, mock_classify):
        result = finalize_review_stop(Path("/fake"), "c", self.resolution, {"last_assistant_message": "done"}, {"lastAssistantMessageClassifierEnabled": True})
        self.assertEqual(result, 2)
        mock_append.assert_called_once()
        mock_classify.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.feedback.append_state")
    @patch("claude_auto_review.stop.feedback.block_response")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.is_review_clean", return_value=False)
    @patch("claude_auto_review.stop.orchestration.finalize.is_review_complete", return_value=True)
    def test_completed_review_with_findings_blocks_with_review_feedback(
        self, mock_complete, mock_clean, mock_covered, mock_block, mock_append, mock_classify,
    ):
        result = finalize_review_stop(Path("/fake"), "c", self.resolution, {"last_assistant_message": "done"}, {})
        self.assertEqual(result, 2)
        self.assertIn("found issues", mock_block.call_args.args[0])
        self.assertIn("Act on the review below", mock_block.call_args.args[1])
        mock_append.assert_called_once()
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.feedback.append_state")
    @patch("claude_auto_review.stop.feedback.block_response")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.attempt_stop_autocomplete", return_value=False)
    @patch("claude_auto_review.stop.orchestration.finalize.is_review_clean", side_effect=[False])
    @patch("claude_auto_review.stop.orchestration.finalize.is_review_complete", side_effect=[False, True])
    def test_autocomplete_findings_are_returned_to_parent_session(
        self, mock_complete, mock_clean, mock_auto, mock_covered, mock_block, mock_append, mock_classify,
    ):
        result = finalize_review_stop(Path("/fake"), "c", self.resolution, {"last_assistant_message": "done"}, {})
        self.assertEqual(result, 2)
        self.assertIn("Act on the review below", mock_block.call_args.args[1])
        mock_append.assert_called_once()
