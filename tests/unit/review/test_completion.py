import unittest
from unittest.mock import patch

from claude_auto_review.review.completion import apply_completed_review
from claude_auto_review.timestamps import format_duration
from claude_auto_review.state.edit_record import EditRecord, StopBlockedRecord
from claude_auto_review.state.review_records import ReviewCompletedRecord, ReviewMetadata
from tests.support_paths import FAKE_ROOT


class TestFormatDuration(unittest.TestCase):
    def test_format_duration_uses_hours_minutes_seconds(self):
        self.assertEqual(format_duration(4833), "1h 20m 33s")
        self.assertEqual(format_duration(91.5), "1m 32s")
        self.assertEqual(format_duration(0), "0s")


class TestCompletion(unittest.TestCase):
    @patch("claude_auto_review.review.completion.mark_files_reviewed")
    @patch("claude_auto_review.review.completion.append_state_event")
    @patch(
        "claude_auto_review.review.completion.get_unreviewed_files",
        return_value=[EditRecord(timestamp="t", file="still.ts", hash="abc")],
    )
    @patch(
        "claude_auto_review.review.completion.load_state",
        side_effect=[
            [
                ReviewMetadata(
                    timestamp="2026-05-11T23:17:39+07:00",
                    reviewId="rid",
                    reviewPath="/fake/r.md",
                    files=[],
                    clientId="cid",
                )
            ],
            [],
        ],
    )
    def test_apply_completed_review_with_remaining_files(self, mock_load, mock_unreviewed, mock_append, mock_mark):
        remaining = apply_completed_review(FAKE_ROOT, "cid", "rid", [])
        self.assertTrue(len(remaining) > 0)
        self.assertEqual(mock_append.call_count, 3)

        completed_status = mock_append.call_args_list[0].args[0]
        self.assertEqual(completed_status.type, "review")
        self.assertEqual(completed_status.status, "completed")
        self.assertEqual(completed_status.reviewId, "rid")

        record = mock_append.call_args_list[1].args[0]
        self.assertIsInstance(record, ReviewCompletedRecord)
        self.assertEqual(record.reviewId, "rid")

        blocked = mock_append.call_args_list[2].args[0]
        self.assertIsInstance(blocked, StopBlockedRecord)
        self.assertEqual(blocked.reason, "partial_review")

    @patch("claude_auto_review.review.completion.mark_files_reviewed")
    @patch("claude_auto_review.review.completion.append_state_event")
    @patch("claude_auto_review.review.completion.get_unreviewed_files", return_value=[])
    @patch(
        "claude_auto_review.review.completion.load_state",
        side_effect=[
            [
                ReviewMetadata(
                    timestamp="2026-05-11T23:17:39+07:00",
                    reviewId="rid",
                    reviewPath="/fake/r.md",
                    files=[],
                    clientId="cid",
                )
            ],
            [],
        ],
    )
    def test_apply_completed_review_with_no_remaining_files(self, mock_load, mock_unreviewed, mock_append, mock_mark):
        remaining = apply_completed_review(FAKE_ROOT, "cid", "rid", [])
        self.assertEqual(len(remaining), 0)
        self.assertEqual(mock_append.call_count, 2)

    @patch("claude_auto_review.review.completion.mark_files_reviewed")
    @patch("claude_auto_review.review.completion.append_state_event")
    @patch("claude_auto_review.review.completion.get_unreviewed_files", return_value=[])
    @patch(
        "claude_auto_review.review.completion.load_state",
        side_effect=[
            [
                ReviewMetadata(
                    timestamp="2026-05-11T23:17:39+07:00",
                    reviewId="rid",
                    reviewPath="/fake/r.md",
                    files=[],
                    clientId="cid",
                )
            ],
            [],
        ],
    )
    def test_apply_completed_review_raises_on_missing_hash(self, mock_load, mock_unreviewed, mock_append, mock_mark):
        with self.assertRaises(ValueError):
            apply_completed_review(FAKE_ROOT, "cid", "rid", [{"file": "a.ts"}])

    def test_apply_completed_review_raises_on_non_dict_entry(self):
        with self.assertRaises(ValueError):
            apply_completed_review(FAKE_ROOT, "cid", "rid", [{"reviewId": "x"}])

    def test_apply_completed_review_raises_on_missing_file(self):
        with self.assertRaises(ValueError):
            apply_completed_review(FAKE_ROOT, "cid", "rid", [{"hash": "123"}])
