import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from claude_auto_review.review.completion import apply_completed_review


class TestCompletion(unittest.TestCase):
    @patch("claude_auto_review.review.completion.mark_files_reviewed")
    @patch("claude_auto_review.review.completion.log_event")
    @patch("claude_auto_review.review.completion.append_state")
    @patch("claude_auto_review.review.completion.get_unreviewed_files", return_value=[{"file": "still.ts", "hash": "abc"}])
    @patch("claude_auto_review.review.completion.load_state")
    def test_apply_completed_review_with_remaining_files(self, mock_load, mock_unreviewed, mock_append, mock_log, mock_mark):
        remaining = apply_completed_review(Path("/fake"), "cid", "rid", [])
        self.assertTrue(len(remaining) > 0)
        mock_log.assert_any_call(Path("/fake"), "stop_approved", reason="review_completed", reviewId="rid")
        mock_log.assert_any_call(Path("/fake"), "stop_blocked_after_partial_review", remaining=["still.ts"])
        mock_append.assert_called_once()

    @patch("claude_auto_review.review.completion.mark_files_reviewed")
    @patch("claude_auto_review.review.completion.log_event")
    @patch("claude_auto_review.review.completion.get_unreviewed_files", return_value=[])
    @patch("claude_auto_review.review.completion.load_state")
    def test_apply_completed_review_no_remaining(self, mock_load, mock_unreviewed, mock_log, mock_mark):
        remaining = apply_completed_review(Path("/fake"), "cid", "rid", [])
        self.assertEqual(remaining, [])
        mock_log.assert_called_with(Path("/fake"), "stop_approved", reason="review_completed", reviewId="rid")


if __name__ == "__main__":
    unittest.main()