import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.review.completion import _format_duration, apply_completed_review


class TestFormatDuration(unittest.TestCase):
    def test_format_duration_uses_hours_minutes_seconds(self):
        self.assertEqual(_format_duration(4833), "1h 20m 33s")
        self.assertEqual(_format_duration(91.5), "1m 32s")
        self.assertEqual(_format_duration(0), "0s")


class TestCompletion(unittest.TestCase):
    @patch("claude_auto_review.review.completion.mark_files_reviewed")
    @patch("claude_auto_review.review.completion.append_state")
    @patch("claude_auto_review.review.completion.get_unreviewed_files", return_value=[{"file": "still.ts", "hash": "abc"}])
    @patch("claude_auto_review.review.completion.load_state", side_effect=[
        [{"type": "review", "reviewId": "rid", "timestamp": "2026-05-11T23:17:39+07:00"}],
        [],
    ])
    def test_apply_completed_review_with_remaining_files(self, mock_load, mock_unreviewed, mock_append, mock_mark):
        remaining = apply_completed_review(Path("/fake"), "cid", "rid", [])
        self.assertTrue(len(remaining) > 0)
        self.assertEqual(mock_append.call_count, 2)
        record = mock_append.call_args_list[0].args[0]
        self.assertEqual(record.type, "review_completed")
        blocked = mock_append.call_args_list[1].args[0]
        self.assertEqual(blocked.type, "stop_blocked")
        self.assertEqual(blocked.reason, "partial_review")
        mock_mark.assert_called_once()
        mark_args, mark_kwargs = mock_mark.call_args
        self.assertEqual(mark_args, ([], "rid", Path("/fake")))
        self.assertEqual(mark_kwargs["client_id"], "cid")
        self.assertIn("timestamp", mark_kwargs)

    @patch("claude_auto_review.review.completion.mark_files_reviewed")
    @patch("claude_auto_review.review.completion.append_state")
    @patch("claude_auto_review.review.completion.get_unreviewed_files", return_value=[])
    @patch("claude_auto_review.review.completion.load_state", side_effect=[
        [{"type": "review", "reviewId": "rid", "timestamp": "2026-05-11T23:17:39+07:00"}],
        [],
    ])
    def test_apply_completed_review_no_remaining(self, mock_load, mock_unreviewed, mock_append, mock_mark):
        remaining = apply_completed_review(Path("/fake"), "cid", "rid", [])
        self.assertEqual(remaining, [])
        mock_append.assert_called_once()
        self.assertEqual(mock_append.call_args.args[0].type, "review_completed")
        mock_mark.assert_called_once()

    @patch("claude_auto_review.state.store_write.log_event")
    @patch("claude_auto_review.review.completion._apply_completed_review_validated", return_value=[])
    @patch("claude_auto_review.review.completion._validate_covered_entries", return_value=[{"file": "a.ts", "hash": "1"}])
    def test_store_write_wrapper_delegates_to_canonical_completion(self, mock_validate, mock_apply, mock_log):
        from claude_auto_review.state.store_write import apply_completed_review as legacy_apply_completed_review

        remaining = legacy_apply_completed_review(Path("/fake"), "cid", "rid", [{"file": "a.ts", "hash": "1"}])

        self.assertEqual(remaining, [])
        mock_validate.assert_called_once_with([{"file": "a.ts", "hash": "1"}])
        mock_apply.assert_called_once_with(Path("/fake"), "cid", "rid", [{"file": "a.ts", "hash": "1"}])
        mock_log.assert_called_once_with(Path("/fake"), "stop_approved", reason="review_completed", reviewId="rid")

    def test_apply_completed_review_raises_on_missing_hash(self):
        with self.assertRaises(ValueError):
            apply_completed_review(Path("/fake"), "cid", "rid", [{"file": "a.ts"}])

    def test_apply_completed_review_raises_on_non_dict_entry(self):
        with self.assertRaises(ValueError):
            apply_completed_review(Path("/fake"), "cid", "rid", ["not a dict"])


if __name__ == "__main__":
    unittest.main()
