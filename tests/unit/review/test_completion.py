import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from claude_auto_review.review.completion import _format_duration, _review_completed_entry, apply_completed_review


class TestFormatDuration(unittest.TestCase):
    def test_format_duration_uses_hours_minutes_seconds(self):
        self.assertEqual(_format_duration(4833), "1h 20m 33s")
        self.assertEqual(_format_duration(91.5), "1m 32s")
        self.assertEqual(_format_duration(0), "0s")


class TestReviewCompletedEntry(unittest.TestCase):
    def test_review_completed_entry_includes_duration(self):
        state = [
            {
                "type": "review",
                "reviewId": "rid",
                "timestamp": "2026-05-11T23:17:39.000000+07:00",
            }
        ]
        entry = _review_completed_entry(
            "rid",
            [{"file": "README.md", "hash": "5411bcbb"}],
            state,
            "2026-05-11T23:19:10.500000+07:00",
            "cid",
        )

        self.assertEqual(entry["type"], "review_completed")
        self.assertEqual(entry["duration"], "1m 32s")
        self.assertEqual(entry["durationSeconds"], 91.5)
        self.assertEqual(entry["clientId"], "cid")


class TestCompletion(unittest.TestCase):
    @patch("claude_auto_review.review.completion.mark_files_reviewed")
    @patch("claude_auto_review.review.completion.log_event")
    @patch("claude_auto_review.review.completion.append_state")
    @patch("claude_auto_review.review.completion.get_unreviewed_files", return_value=[{"file": "still.ts", "hash": "abc"}])
    @patch("claude_auto_review.review.completion.load_state", side_effect=[
        [{"type": "review", "reviewId": "rid", "timestamp": "2026-05-11T23:17:39+07:00"}],
        [],
    ])
    def test_apply_completed_review_with_remaining_files(self, mock_load, mock_unreviewed, mock_append, mock_log, mock_mark):
        remaining = apply_completed_review(Path("/fake"), "cid", "rid", [])
        self.assertTrue(len(remaining) > 0)
        mock_log.assert_any_call(Path("/fake"), "stop_approved", reason="review_completed", reviewId="rid")
        mock_log.assert_any_call(Path("/fake"), "stop_blocked_after_partial_review", remaining=["still.ts"])
        self.assertEqual(mock_append.call_count, 2)
        self.assertEqual(mock_append.call_args_list[0].args[0]["type"], "review_completed")

    @patch("claude_auto_review.review.completion.mark_files_reviewed")
    @patch("claude_auto_review.review.completion.append_state")
    @patch("claude_auto_review.review.completion.log_event")
    @patch("claude_auto_review.review.completion.get_unreviewed_files", return_value=[])
    @patch("claude_auto_review.review.completion.load_state", side_effect=[
        [{"type": "review", "reviewId": "rid", "timestamp": "2026-05-11T23:17:39+07:00"}],
        [],
    ])
    def test_apply_completed_review_no_remaining(self, mock_load, mock_unreviewed, mock_log, mock_append, mock_mark):
        remaining = apply_completed_review(Path("/fake"), "cid", "rid", [])
        self.assertEqual(remaining, [])
        mock_log.assert_called_with(Path("/fake"), "stop_approved", reason="review_completed", reviewId="rid")
        mock_append.assert_called_once()
        self.assertEqual(mock_append.call_args.args[0]["type"], "review_completed")


if __name__ == "__main__":
    unittest.main()
