import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.state.models import EditRecord, ReviewMetadata
from claude_auto_review.stop.orchestration.resolution import StopFlowResolution
from claude_auto_review.stop.orchestration.finalize import finalize_review_stop


def _mk_review(reviewId: str = "r1") -> ReviewMetadata:
    return ReviewMetadata(
        timestamp="2026-05-11T10:00:00+07:00",
        reviewId=reviewId,
        reviewPath="/fake/r.md",
        files=[],
        clientId="c",
        status="pending",
    )


class TestFinalizeReviewStop(unittest.TestCase):
    resolution = StopFlowResolution(
        state=[], unreviewed=[],
        review=_mk_review("r1"),
    )

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", return_value="Clean - no issues found.")
    @patch("claude_auto_review.stop.orchestration.finalize.apply_completed_review", return_value=[])
    def test_completed_no_remaining_returns_0(self, mock_apply, mock_verdict, mock_covered, mock_classify):
        result = finalize_review_stop(Path("/fake"), "c", self.resolution, {}, {})
        self.assertEqual(result, 0)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", return_value="Clean - no issues found.")
    @patch("claude_auto_review.stop.orchestration.finalize.apply_completed_review", return_value=[EditRecord(timestamp="t", file="still.ts", hash="1")])
    def test_completed_with_remaining_returns_2(self, mock_apply, mock_verdict, mock_covered, mock_classify):
        resolution = StopFlowResolution(
            state=[], unreviewed=[EditRecord(timestamp="t", file="still.ts", hash="1")],
            review=_mk_review("r1"),
        )
        result = finalize_review_stop(Path("/fake"), "c", resolution, {"last_assistant_message": "done"}, {"lastAssistantMessageClassifierEnabled": True})
        self.assertEqual(result, 2)
        mock_classify.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.attempt_stop_autocomplete", return_value=True)
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", return_value="Pending.")
    def test_autocomplete_succeeds_returns_0(self, mock_verdict, mock_auto, mock_covered, mock_classify):
        result = finalize_review_stop(Path("/fake"), "c", self.resolution, {"last_assistant_message": "done"}, {})
        self.assertEqual(result, 0)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.response_actions.append_state")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.attempt_stop_autocomplete", return_value=False)
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", side_effect=["Pending.", "Pending."])
    def test_autocomplete_fails_blocks_stop(self, mock_verdict, mock_auto, mock_covered, mock_append, mock_classify):
        result = finalize_review_stop(Path("/fake"), "c", self.resolution, {"last_assistant_message": "done"}, {"lastAssistantMessageClassifierEnabled": True})
        self.assertEqual(result, 2)
        mock_append.assert_called_once()
        mock_classify.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.feedback.append_state")
    @patch("claude_auto_review.stop.feedback.block_response")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", return_value="Not clean - fix src/app.ts.")
    def test_completed_review_with_findings_blocks_with_review_feedback(
        self, mock_verdict, mock_covered, mock_block, mock_append, mock_classify,
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
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", side_effect=["Pending.", "Not clean."])
    def test_autocomplete_findings_are_returned_to_parent_session(
        self, mock_verdict, mock_auto, mock_covered, mock_block, mock_append, mock_classify,
    ):
        result = finalize_review_stop(Path("/fake"), "c", self.resolution, {"last_assistant_message": "done"}, {})
        self.assertEqual(result, 2)
        self.assertIn("Act on the review below", mock_block.call_args.args[1])
        mock_append.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.classify_last_assistant_message")
    @patch("claude_auto_review.stop.feedback.append_state")
    @patch("claude_auto_review.stop.feedback.block_response")
    @patch("claude_auto_review.stop.orchestration.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.attempt_stop_autocomplete", return_value=False)
    @patch("claude_auto_review.stop.orchestration.finalize._read_review_verdict", side_effect=["Pending.", "Not clean."])
    def test_autocomplete_completed_with_findings_blocks_completion(
        self, mock_verdict, mock_auto, mock_covered, mock_block, mock_append, mock_classify,
    ):
        result = finalize_review_stop(Path("/fake"), "c", self.resolution, {"last_assistant_message": "done"}, {})
        self.assertEqual(result, 2)
        self.assertIn("found issues", mock_block.call_args.args[0])
        mock_append.assert_called_once()
